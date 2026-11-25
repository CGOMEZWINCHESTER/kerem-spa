"""Rutas de administracion: pacientes, citas y servicios (CRUD)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from app.database import get_session
from app.models import (
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
    AppointmentRead,
    ClinicalHistoryCreate,
    ClinicalHistoryRead,
    ClinicalHistoryUpdate,
    PatientRecordCreate,
    PatientRecordRead,
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
        .options(selectinload(Appointment.service))
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
    appointment = session.get(Appointment, appointment_id)
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
