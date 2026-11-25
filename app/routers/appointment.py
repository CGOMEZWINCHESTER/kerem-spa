"""Rutas de citas para el cliente autenticado (agendar, historial, slots)."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.config import settings
from app.database import get_session
from app.models import (
    Appointment,
    AppointmentStatus,
    Role,
    Service,
    User,
)
from app.notifications import (
    notify_admin_new_appointment,
    notify_status_change,
)
from app.schemas import (
    AppointmentCreate,
    AppointmentRead,
    ServiceRead,
    Slot,
)
from app.security import get_current_user

router = APIRouter(tags=["appointments"])


def _parse_time(value: str) -> time:
    """Convierte 'HH:MM' en un objeto time; fallback 09:00 si es invalido."""
    try:
        hh, mm = value.strip().split(":")
        return time(int(hh), int(mm))
    except (ValueError, AttributeError):
        return time(9, 0)


def _to_appointment_read(appt: Appointment) -> AppointmentRead:
    """Serializa una cita incluyendo datos del servicio y cliente."""
    return AppointmentRead(
        id=appt.id,
        user_id=appt.user_id,
        service_id=appt.service_id,
        starts_at=appt.starts_at,
        ends_at=appt.ends_at,
        status=appt.status,
        notes=appt.notes,
        service_name=appt.service.name if appt.service else None,
        service_price=appt.service.price if appt.service else None,
        client_name=appt.user.full_name if appt.user else None,
        client_phone=appt.user.phone if appt.user else None,
        client_email=appt.user.email if appt.user else None,
        created_at=appt.created_at,
    )


def _overlapping(
    candidate_start: datetime,
    candidate_end: datetime,
    session: Session,
    exclude_appointment_id: int | None = None,
) -> bool:
    """Devuelve True si la franja cruza con alguna cita activa existente.

    Una cita activa es pending o approved; las canceladas/completadas no
    bloquean el horario.
    """
    active = (AppointmentStatus.PENDING, AppointmentStatus.APPROVED)
    stmt = select(Appointment).where(
        Appointment.status.in_(active),
        Appointment.starts_at < candidate_end,
        Appointment.ends_at > candidate_start,
    )
    if exclude_appointment_id is not None:
        stmt = stmt.where(Appointment.id != exclude_appointment_id)
    return session.exec(stmt).first() is not None


def _build_slots_for_day(
    day: date,
    service: Service,
    session: Session,
) -> list[Slot]:
    """Genera franjas libres para un dia teniendo en cuenta la duracion.

    La agenda esta abierta de 09:00 a 20:00. Se genera un slot cada 30 min
    y se excluyen los que cruzan con citas activas o con la franja de
    almuerzo (13:00-14:00).
    """
    if service.duration_minutes <= 0:
        return []

    day_start = datetime.combine(
        day, _parse_time(settings.agenda_start), tzinfo=timezone.utc
    )
    day_end = datetime.combine(
        day, _parse_time(settings.agenda_end), tzinfo=timezone.utc
    )
    lunch_start = (
        datetime.combine(
            day,
            _parse_time(settings.agenda_lunch_start),
            tzinfo=timezone.utc,
        )
        if settings.agenda_lunch_start
        else None
    )
    lunch_end = (
        datetime.combine(
            day,
            _parse_time(settings.agenda_lunch_end),
            tzinfo=timezone.utc,
        )
        if settings.agenda_lunch_end
        else None
    )

    step = timedelta(minutes=settings.agenda_step_minutes)
    duration = timedelta(minutes=service.duration_minutes)
    slots: list[Slot] = []
    cursor = day_start

    while cursor + duration <= day_end:
        slot_end = cursor + duration
        # Omitir franjas que caigan dentro del horario de almuerzo (si existe).
        if (
            lunch_start is not None
            and lunch_end is not None
            and slot_end > lunch_start
            and cursor < lunch_end
        ):
            cursor += step
            continue
        if not _overlapping(cursor, slot_end, session):
            slots.append(Slot(starts_at=cursor, ends_at=slot_end))
        cursor += step

    return slots


@router.get("/services", response_model=list[ServiceRead])
def list_services(
    session: Annotated[Session, Depends(get_session)],
) -> list[Service]:
    """Lista los servicios activos disponibles para agendar."""
    stmt = select(Service).where(Service.is_active == True)  # noqa: E712
    return list(session.exec(stmt).all())


@router.get("/services/{service_id}", response_model=ServiceRead)
def get_service(
    service_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> Service:
    service = session.get(Service, service_id)
    if service is None or not service.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Servicio no encontrado.",
        )
    return service


@router.get("/appointments/slots", response_model=list[Slot])
def available_slots(
    service_id: int,
    day: date,
    session: Annotated[Session, Depends(get_session)],
) -> list[Slot]:
    """Devuelve los horarios disponibles para un servicio y dia concretos."""
    service = session.get(Service, service_id)
    if service is None or not service.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Servicio no encontrado.",
        )
    if day < date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes agendar en una fecha pasada.",
        )
    return _build_slots_for_day(day, service, session)


@router.get("/appointments", response_model=list[AppointmentRead])
def my_appointments(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[AppointmentRead]:
    """Historial de citas del cliente autenticado (mas recientes primero)."""
    stmt = (
        select(Appointment)
        .options(selectinload(Appointment.service))
        .where(Appointment.user_id == current_user.id)
        .order_by(Appointment.starts_at.desc())
    )
    return [_to_appointment_read(a) for a in session.exec(stmt).all()]


@router.post(
    "/appointments",
    response_model=AppointmentRead,
    status_code=status.HTTP_201_CREATED,
)
def create_appointment(
    payload: AppointmentCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> AppointmentRead:
    """Crea una cita validando en el backend que no cruce horarios."""
    service = session.get(Service, payload.service_id)
    if service is None or not service.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Servicio no encontrado.",
        )

    starts_at = payload.starts_at
    if starts_at.tzinfo is None:
        starts_at = starts_at.replace(tzinfo=timezone.utc)
    if starts_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No puedes agendar en el pasado.",
        )

    ends_at = starts_at + timedelta(minutes=service.duration_minutes)

    # Lanzamos dentro de una transaccion para evitar condiciones de carrera
    # en entornos concurrentes: el check + insert deben ser atomicos.
    if _overlapping(starts_at, ends_at, session):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La franja elegida ya no esta disponible. Elige otra hora.",
        )

    appointment = Appointment(
        user_id=current_user.id,
        service_id=service.id,
        starts_at=starts_at,
        ends_at=ends_at,
        status=AppointmentStatus.PENDING,
        notes=payload.notes,
    )
    session.add(appointment)
    session.commit()
    session.refresh(appointment, ["service"])
    appointment.user = current_user

    # Notificaciones in-app + correo: al cliente (pendiente) y a los admins.
    notify_status_change(session, appointment, service)
    admins = session.exec(select(User).where(User.role == Role.ADMIN)).all()
    notify_admin_new_appointment(session, appointment, service, admins)
    session.commit()

    return _to_appointment_read(appointment)


@router.patch(
    "/appointments/{appointment_id}/cancel",
    response_model=AppointmentRead,
)
def cancel_my_appointment(
    appointment_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> AppointmentRead:
    """El cliente cancela su propia cita si esta pendiente o aprobada."""
    appointment = session.get(Appointment, appointment_id)
    if appointment is None or appointment.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cita no encontrada."
        )
    if appointment.status in (
        AppointmentStatus.CANCELLED,
        AppointmentStatus.COMPLETED,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Esta cita ya no puede cancelarse.",
        )
    appointment.status = AppointmentStatus.CANCELLED
    session.add(appointment)
    session.commit()
    session.refresh(appointment, ["service", "user"])
    notify_status_change(session, appointment, appointment.service)
    session.commit()
    return _to_appointment_read(appointment)
