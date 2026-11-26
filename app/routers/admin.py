"""Rutas de administracion: pacientes, citas y servicios (CRUD)."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.database import get_session
from app.models import (
    AgendaSettings,
    Appointment,
    AppointmentStatus,
    ClinicalHistory,
    PatientRecord,
    Service,
    User,
    utc_now,
)
from app.notifications import notify_status_change
from app.routers.appointment import _to_appointment_read
from app.schemas import (
    AdminAppointmentUpdate,
    AgendaSettingsRead,
    AgendaSettingsUpdate,
    AppointmentRead,
    ClinicalHistoryCreate,
    ClinicalHistoryRead,
    ClinicalHistoryUpdate,
    PatientRecordCreate,
    PatientRecordRead,
    ReportResponse,
    ReportSummary,
    ReportDay,
    ServiceCreate,
    ServiceRead,
    ServiceUpdate,
    UserRead,
    UserRegister,
    UserUpdate,
)
from app.security import get_user_by_email, hash_password, require_admin

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


# --------------------------------------------------------------------------
# Pacientes
# --------------------------------------------------------------------------
@router.get("/patients", response_model=list[UserRead])
def list_patients(
    session: Annotated[Session, Depends(get_session)],
    q: str | None = None,
) -> list[User]:
    """Lista clientes, opcionalmente filtrando por nombre o correo."""
    stmt = select(User).where(User.role == "client")
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            User.full_name.ilike(like) | User.email.ilike(like)
        )
    stmt = stmt.order_by(User.full_name)
    return list(session.exec(stmt).all())


@router.get("/patients/{patient_id}", response_model=UserRead)
def get_patient(
    patient_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> User:
    """Devuelve un paciente por su id."""
    return _get_patient_or_404(patient_id, session)


@router.post(
    "/patients",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def create_patient(
    payload: UserRegister,
    session: Annotated[Session, Depends(get_session)],
) -> User:
    """Registra un paciente manualmente desde el dashboard."""
    if get_user_by_email(session, payload.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe un paciente con ese correo.",
        )
    user = User(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        phone=payload.phone,
        birth_date=payload.birth_date,
        address=payload.address,
        occupation=payload.occupation,
        role="client",
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.patch("/patients/{patient_id}", response_model=UserRead)
def update_patient(
    patient_id: int,
    payload: UserUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> User:
    """Actualiza datos de un cliente."""
    user = _get_patient_or_404(patient_id, session)
    data = payload.model_dump(exclude_unset=True)
    if "password" in data and data["password"]:
        user.hashed_password = hash_password(data.pop("password"))
    data.pop("password", None)
    for field, value in data.items():
        setattr(user, field, value)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.delete(
    "/patients/{patient_id}", status_code=status.HTTP_204_NO_CONTENT
)
def delete_patient(
    patient_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> None:
    """Elimina un paciente (borra en cascada citas y registros)."""
    user = _get_patient_or_404(patient_id, session)
    session.delete(user)
    session.commit()


def _get_patient_or_404(patient_id: int, session: Session) -> User:
    user = session.get(User, patient_id)
    if user is None or user.role != "client":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Paciente no encontrado.",
        )
    return user


# --------------------------------------------------------------------------
# Registros de medidas / evolucion del paciente
# --------------------------------------------------------------------------
@router.get(
    "/patients/{patient_id}/records",
    response_model=list[PatientRecordRead],
)
def list_patient_records(
    patient_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> list[PatientRecord]:
    """Historial de medidas corporales de un paciente."""
    _get_patient_or_404(patient_id, session)
    stmt = (
        select(PatientRecord)
        .where(PatientRecord.user_id == patient_id)
        .order_by(PatientRecord.measurements_date.desc())
    )
    return list(session.exec(stmt).all())


@router.post(
    "/patients/{patient_id}/records",
    response_model=PatientRecordRead,
    status_code=status.HTTP_201_CREATED,
)
def add_patient_record(
    patient_id: int,
    payload: PatientRecordCreate,
    session: Annotated[Session, Depends(get_session)],
) -> PatientRecord:
    """Agrega una entrada al historial de medidas del paciente."""
    _get_patient_or_404(patient_id, session)
    record = PatientRecord(user_id=patient_id, **payload.model_dump())
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


# --------------------------------------------------------------------------
# Ficha clinica del paciente
# --------------------------------------------------------------------------
def _get_ficha_or_none(patient_id: int, session: Session):
    stmt = select(ClinicalHistory).where(ClinicalHistory.user_id == patient_id)
    return session.exec(stmt).first()


@router.get(
    "/patients/{patient_id}/ficha",
    response_model=ClinicalHistoryRead,
)
def get_patient_ficha(
    patient_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> ClinicalHistory:
    """Devuelve la ficha clinica del paciente (404 si aun no existe)."""
    _get_patient_or_404(patient_id, session)
    ficha = _get_ficha_or_none(patient_id, session)
    if ficha is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La ficha clinica aun no ha sido creada.",
        )
    return ficha


@router.post(
    "/patients/{patient_id}/ficha",
    response_model=ClinicalHistoryRead,
    status_code=status.HTTP_201_CREATED,
)
def create_patient_ficha(
    patient_id: int,
    payload: ClinicalHistoryCreate,
    session: Annotated[Session, Depends(get_session)],
) -> ClinicalHistory:
    """Crea la ficha clinica del paciente (conflicto si ya existe)."""
    _get_patient_or_404(patient_id, session)
    if _get_ficha_or_none(patient_id, session) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La ficha clinica ya existe.",
        )
    ficha = ClinicalHistory(
        user_id=patient_id, **payload.model_dump(exclude_unset=True)
    )
    session.add(ficha)
    session.commit()
    session.refresh(ficha)
    return ficha


@router.put(
    "/patients/{patient_id}/ficha",
    response_model=ClinicalHistoryRead,
)
def update_patient_ficha(
    patient_id: int,
    payload: ClinicalHistoryUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> ClinicalHistory:
    """Crea o actualiza (upsert) la ficha clinica del paciente."""
    _get_patient_or_404(patient_id, session)
    ficha = _get_ficha_or_none(patient_id, session)
    if ficha is None:
        ficha = ClinicalHistory(user_id=patient_id)
        session.add(ficha)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(ficha, field, value)
    ficha.updated_at = utc_now()
    session.commit()
    session.refresh(ficha)
    return ficha


# --------------------------------------------------------------------------
# Citas (panel de administracion)
# --------------------------------------------------------------------------
@router.get("/appointments", response_model=list[AppointmentRead])
def list_all_appointments(
    session: Annotated[Session, Depends(get_session)],
    status_filter: AppointmentStatus | None = None,
) -> list[AppointmentRead]:
    """Lista todas las citas, opcionalmente filtradas por estado."""
    stmt = (
        select(Appointment)
        .options(selectinload(Appointment.service), selectinload(Appointment.user))
        .order_by(Appointment.starts_at)
    )
    if status_filter is not None:
        stmt = stmt.where(Appointment.status == status_filter)
    return [
        _to_appointment_read(a) for a in session.exec(stmt).all()
    ]


@router.patch("/appointments/{appointment_id}", response_model=AppointmentRead)
def update_appointment(
    appointment_id: int,
    payload: AdminAppointmentUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> AppointmentRead:
    """Aprueba, reagenda o cancela una cita.

    Al reagendar (cambiar starts_at) se recalcula ends_at segun la duracion
    del servicio y se valida de nuevo contra cruces de horario.
    """
    stmt = (
        select(Appointment)
        .where(Appointment.id == appointment_id)
        .options(selectinload(Appointment.service), selectinload(Appointment.user))
    )
    appointment = session.exec(stmt).first()
    if appointment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cita no encontrada."
        )

    data = payload.model_dump(exclude_unset=True)

    # Reagendar: validar nueva franja.
    if data.get("starts_at") is not None:
        from datetime import timedelta, timezone

        starts_at = data["starts_at"]
        if starts_at.tzinfo is None:
            starts_at = starts_at.replace(tzinfo=timezone.utc)
        ends_at = starts_at + timedelta(
            minutes=appointment.service.duration_minutes
        )
        # Import local para evitar ciclo.
        from app.routers.appointment import _overlapping

        if _overlapping(
            starts_at, ends_at, session, exclude_appointment_id=appointment.id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="La nueva franja cruza con otra cita activa.",
            )
        appointment.starts_at = starts_at
        appointment.ends_at = ends_at

    prev_status = appointment.status
    if "status" in data and data["status"] is not None:
        appointment.status = data["status"]
    if "notes" in data and data["notes"] is not None:
        appointment.notes = data["notes"]

    session.add(appointment)
    session.commit()
    session.refresh(appointment, ["service", "user"])
    # Notificar al cliente si su cita cambio de estado.
    if appointment.status != prev_status:
        notify_status_change(session, appointment, appointment.service)
        session.commit()
    return _to_appointment_read(appointment)


# --------------------------------------------------------------------------
# Reportes / caja
# --------------------------------------------------------------------------
def _period_bounds(period: str, ref: date) -> tuple[datetime, datetime, date, date]:
    if period == "daily":
        start_d = ref
        end_d = ref
    elif period == "weekly":
        start_d = ref - timedelta(days=ref.weekday())
        end_d = start_d + timedelta(days=6)
    elif period == "monthly":
        start_d = ref.replace(day=1)
        if start_d.month == 12:
            next_month = start_d.replace(year=start_d.year + 1, month=1, day=1)
        else:
            next_month = start_d.replace(month=start_d.month + 1, day=1)
        end_d = next_month - timedelta(days=1)
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Periodo inválido. Usa daily, weekly o monthly.")
    start_dt = datetime.combine(start_d, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(end_d + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return start_dt, end_dt, start_d, end_d


@router.get("/reports", response_model=ReportResponse)
def get_reports(
    session: Annotated[Session, Depends(get_session)],
    period: str = "daily",
    date_ref: str | None = None,
) -> ReportResponse:
    """Reporte de citas e ingresos por día/semana/mes."""
    try:
        ref = date.fromisoformat(date_ref) if date_ref else utc_now().date()
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="date_ref inválida. Usa YYYY-MM-DD.")
    start_dt, end_dt, start_d, end_d = _period_bounds(period, ref)

    stmt = (
        select(Appointment)
        .options(selectinload(Appointment.service))
        .where(Appointment.starts_at >= start_dt, Appointment.starts_at < end_dt)
        .order_by(Appointment.starts_at)
    )
    appts = list(session.exec(stmt).all())

    days: dict[str, dict] = {}
    cur = start_d
    while cur <= end_d:
        k = cur.isoformat()
        days[k] = {
            "date": k,
            "total_appointments": 0,
            "completed_appointments": 0,
            "pending_appointments": 0,
            "approved_appointments": 0,
            "cancelled_appointments": 0,
            "total_revenue": 0.0,
            "completed_revenue": 0.0,
            "expected_revenue": 0.0,
        }
        cur += timedelta(days=1)

    for a in appts:
        day_key = a.starts_at.astimezone(timezone.utc).date().isoformat()
        if day_key not in days:
            continue
        d = days[day_key]
        price = float(a.service.price) if a.service and a.service.price is not None else 0.0
        d["total_appointments"] += 1
        d["total_revenue"] += price
        if a.status == AppointmentStatus.COMPLETED:
            d["completed_appointments"] += 1
            d["completed_revenue"] += price
        elif a.status == AppointmentStatus.PENDING:
            d["pending_appointments"] += 1
            d["expected_revenue"] += price
        elif a.status == AppointmentStatus.APPROVED:
            d["approved_appointments"] += 1
            d["expected_revenue"] += price
        elif a.status == AppointmentStatus.CANCELLED:
            d["cancelled_appointments"] += 1

    day_list = [ReportDay(**v) for v in days.values()]
    summary = ReportSummary(
        total_appointments=sum(d.total_appointments for d in day_list),
        completed_appointments=sum(d.completed_appointments for d in day_list),
        pending_appointments=sum(d.pending_appointments for d in day_list),
        approved_appointments=sum(d.approved_appointments for d in day_list),
        cancelled_appointments=sum(d.cancelled_appointments for d in day_list),
        total_revenue=round(sum(d.total_revenue for d in day_list), 2),
        completed_revenue=round(sum(d.completed_revenue for d in day_list), 2),
        expected_revenue=round(sum(d.expected_revenue for d in day_list), 2),
    )
    return ReportResponse(
        period=period,
        start_date=start_d.isoformat(),
        end_date=end_d.isoformat(),
        summary=summary,
        days=day_list,
    )


# --------------------------------------------------------------------------
# Agenda / horarios disponibles
# --------------------------------------------------------------------------
def _get_or_create_agenda(session: Session) -> AgendaSettings:
    try:
        agenda = session.get(AgendaSettings, 1)
        if agenda is None:
            from app.config import settings

            agenda = AgendaSettings(
                id=1,
                start_time=settings.agenda_start,
                end_time=settings.agenda_end,
                step_minutes=settings.agenda_step_minutes,
                lunch_start=settings.agenda_lunch_start,
                lunch_end=settings.agenda_lunch_end,
                working_days="0,1,2,3,4,5",
            )
            session.add(agenda)
            session.commit()
            session.refresh(agenda)
        return agenda
    except Exception:
        session.rollback()
        from app.config import settings
        return AgendaSettings(
            id=1,
            start_time=settings.agenda_start,
            end_time=settings.agenda_end,
            step_minutes=settings.agenda_step_minutes,
            lunch_start=settings.agenda_lunch_start,
            lunch_end=settings.agenda_lunch_end,
            working_days="0,1,2,3,4,5",
        )


def _agenda_to_read(agenda: AgendaSettings) -> AgendaSettingsRead:
    days = [int(x) for x in agenda.working_days.split(",") if x.strip().lstrip("-").isdigit()]
    days = [d for d in days if 0 <= d <= 6]
    if not days:
        days = [0, 1, 2, 3, 4, 5]
    return AgendaSettingsRead(
        start_time=agenda.start_time,
        end_time=agenda.end_time,
        step_minutes=agenda.step_minutes,
        lunch_start=agenda.lunch_start,
        lunch_end=agenda.lunch_end,
        working_days=sorted(set(days)),
        updated_at=agenda.updated_at,
    )


@router.get("/agenda", response_model=AgendaSettingsRead)
def get_agenda_settings(session: Annotated[Session, Depends(get_session)]) -> AgendaSettingsRead:
    return _agenda_to_read(_get_or_create_agenda(session))


@router.put("/agenda", response_model=AgendaSettingsRead)
def update_agenda_settings(
    payload: AgendaSettingsUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> AgendaSettingsRead:
    agenda = _get_or_create_agenda(session)
    days = sorted({int(d) for d in payload.working_days if 0 <= int(d) <= 6})
    if not days:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Selecciona al menos un día laboral.")
    start = datetime.strptime(payload.start_time, "%H:%M").time()
    end = datetime.strptime(payload.end_time, "%H:%M").time()
    if end <= start:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La hora de fin debe ser mayor que la de inicio.")
    lunch_start = lunch_end = None
    if payload.lunch_start or payload.lunch_end:
        if not (payload.lunch_start and payload.lunch_end):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Define inicio y fin de comida, o deja ambos vacíos.")
        lunch_start = datetime.strptime(payload.lunch_start, "%H:%M").time()
        lunch_end = datetime.strptime(payload.lunch_end, "%H:%M").time()
        if lunch_end <= lunch_start:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El fin de comida debe ser mayor que el inicio.")
        if lunch_start < start or lunch_end > end:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La comida debe estar dentro del horario laboral.")

    agenda.start_time = payload.start_time
    agenda.end_time = payload.end_time
    agenda.step_minutes = payload.step_minutes
    agenda.lunch_start = payload.lunch_start
    agenda.lunch_end = payload.lunch_end
    agenda.working_days = ",".join(str(d) for d in days)
    agenda.updated_at = utc_now()
    session.add(agenda)
    session.commit()
    session.refresh(agenda)
    return _agenda_to_read(agenda)


# --------------------------------------------------------------------------
# Servicios (control de precios/duracion)
# --------------------------------------------------------------------------
@router.get("/services", response_model=list[ServiceRead])
def list_all_services(
    session: Annotated[Session, Depends(get_session)],
) -> list[Service]:
    """Lista todos los servicios (activos e inactivos)."""
    return list(session.exec(select(Service).order_by(Service.name)).all())


@router.post(
    "/services",
    response_model=ServiceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_service(
    payload: ServiceCreate,
    session: Annotated[Session, Depends(get_session)],
) -> Service:
    service = Service(**payload.model_dump())
    session.add(service)
    session.commit()
    session.refresh(service)
    return service


@router.patch("/services/{service_id}", response_model=ServiceRead)
def update_service(
    service_id: int,
    payload: ServiceUpdate,
    session: Annotated[Session, Depends(get_session)],
) -> Service:
    service = session.get(Service, service_id)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Servicio no encontrado.",
        )
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(service, field, value)
    session.add(service)
    session.commit()
    session.refresh(service)
    return service


@router.delete(
    "/services/{service_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_service(
    service_id: int,
    session: Annotated[Session, Depends(get_session)],
) -> None:
    service = session.get(Service, service_id)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Servicio no encontrado.",
        )
    session.delete(service)
    session.commit()
