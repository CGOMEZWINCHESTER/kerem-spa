"""Modelos de base de datos para KEREM (SQLModel / PostgreSQL en Supabase).

Relaciones:
    - User 1:N Appointment
    - User 1:N PatientRecord (historial de medidas/evolucion)
    - Service 1:N Appointment
"""
from datetime import date, datetime, timezone
from enum import Enum
from typing import List

from sqlalchemy import Column, DateTime, Index
from sqlmodel import Field, Relationship, SQLModel


class Role(str, Enum):
    """Rol de un usuario en el sistema."""

    CLIENT = "client"
    ADMIN = "admin"


class AppointmentStatus(str, Enum):
    """Estado de una cita."""

    PENDING = "pending"
    APPROVED = "approved"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


def utc_now() -> datetime:
    """Devuelve la fecha/hora actual en UTC (timezone-aware)."""
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    """Usuario (cliente o administrador)."""

    __tablename__ = "user"

    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True, max_length=255)
    hashed_password: str = Field(max_length=255)
    full_name: str = Field(max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    birth_date: date | None = Field(default=None)
    address: str | None = Field(default=None, max_length=255)
    occupation: str | None = Field(default=None, max_length=120)
    role: Role = Field(default=Role.CLIENT)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utc_now)

    appointments: List["Appointment"] = Relationship(
        back_populates="user", cascade_delete=True
    )
    records: List["PatientRecord"] = Relationship(
        back_populates="user", cascade_delete=True
    )
    notifications: List["Notification"] = Relationship(
        back_populates="user", cascade_delete=True
    )
    clinical_history: "ClinicalHistory" = Relationship(
        back_populates="user",
        cascade_delete=True,
        sa_relationship_kwargs={"uselist": False},
    )


class Service(SQLModel, table=True):
    """Tipo de servicio ofrecido (p. ej. Masaje Reductivo / Relajante)."""

    __tablename__ = "service"

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, max_length=120)
    description: str | None = Field(default=None, max_length=400)
    price: float = Field(default=0.0)
    duration_minutes: int = Field(default=60)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=utc_now)

    appointments: List["Appointment"] = Relationship(
        back_populates="service", cascade_delete=True
    )


class Appointment(SQLModel, table=True):
    """Cita de un cliente con un servicio en una franja horaria."""

    __tablename__ = "appointment"
    __table_args__ = (
        Index("ix_appointment_starts_at", "starts_at"),
        Index("ix_appointment_service_starts", "service_id", "starts_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    service_id: int = Field(foreign_key="service.id", index=True)
    starts_at: datetime = Field(sa_column=Column(DateTime(timezone=True)))
    ends_at: datetime = Field(sa_column=Column(DateTime(timezone=True)))
    status: AppointmentStatus = Field(default=AppointmentStatus.PENDING)
    notes: str | None = Field(default=None, max_length=400)
    created_at: datetime = Field(default_factory=utc_now)

    user: User = Relationship(back_populates="appointments")
    service: Service = Relationship(back_populates="appointments")


class PatientRecord(SQLModel, table=True):
    """Registro clinico/antropometrico (historial de medidas evolutivas)."""

    __tablename__ = "patient_record"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    weight_kg: float | None = None
    height_cm: float | None = None
    waist_cm: float | None = None
    hip_cm: float | None = None
    abdomen_cm: float | None = None
    right_leg_cm: float | None = None
    left_leg_cm: float | None = None
    session_type: str | None = Field(default=None, max_length=40)
    techniques: str | None = Field(default=None, max_length=400)
    oils_lotions: str | None = Field(default=None, max_length=400)
    contraindications: str | None = Field(default=None, max_length=400)
    duration_minutes: int | None = None
    measurements_date: date = Field(default_factory=date.today)
    clinical_notes: str | None = Field(default=None, max_length=800)
    created_at: datetime = Field(default_factory=utc_now)

    user: User = Relationship(back_populates="records")


class ClinicalHistory(SQLModel, table=True):
    """Ficha clinica del paciente (historia, evaluacion y consentimiento)."""

    __tablename__ = "clinical_history"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(
        foreign_key="user.id", unique=True, index=True
    )
    reason_for_consultation: str | None = Field(default=None, max_length=800)
    treatment_objective: str | None = Field(default=None, max_length=800)

    surgeries: bool = Field(default=False)
    surgeries_detail: str | None = Field(default=None, max_length=400)
    surgeries_date: date | None = None
    cesarean: bool = Field(default=False)
    cesarean_detail: str | None = Field(default=None, max_length=400)
    cesarean_date: date | None = None
    pregnancy: bool = Field(default=False)
    lactation: bool = Field(default=False)
    menstruation: bool = Field(default=False)
    diu: str | None = Field(default=None, max_length=120)
    menopause: bool = Field(default=False)
    chronic_diabetes: bool = Field(default=False)
    chronic_hypertension: bool = Field(default=False)
    chronic_thyroid: bool = Field(default=False)
    chronic_heart: bool = Field(default=False)
    chronic_other: str | None = Field(default=None, max_length=400)
    current_medications: str | None = Field(default=None, max_length=800)

    weight_kg: float | None = None
    height_cm: float | None = None
    waist_cm: float | None = None
    hip_cm: float | None = None
    abdomen_cm: float | None = None
    right_leg_cm: float | None = None
    left_leg_cm: float | None = None
    areas_fat: bool = Field(default=False)
    areas_cellulite: bool = Field(default=False)
    areas_retention: bool = Field(default=False)
    areas_other: str | None = Field(default=None, max_length=400)
    silhouette_notes: str | None = Field(default=None, max_length=800)

    sessions_recommended: int = Field(default=0)
    sessions_completed: int = Field(default=0)
    progress_notes: str | None = Field(default=None, max_length=800)
    consent_given: bool = Field(default=False)
    consent_signature: str | None = Field(default=None, max_length=255)
    consent_date: date | None = None

    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    user: User = Relationship(back_populates="clinical_history")


class Notification(SQLModel, table=True):
    """Notificacion in-app dirigida a un usuario (cliente o admin)."""

    __tablename__ = "notification"

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    title: str = Field(max_length=120)
    message: str = Field(max_length=400)
    is_read: bool = Field(default=False)
    created_at: datetime = Field(default_factory=utc_now)

    user: User = Relationship(back_populates="notifications")


class AgendaSettings(SQLModel, table=True):
    """Configuración singleton de agenda/horarios disponibles."""

    __tablename__ = "agenda_settings"

    id: int | None = Field(default=1, primary_key=True)
    start_time: str = Field(default="09:00", max_length=5)
    end_time: str = Field(default="20:00", max_length=5)
    step_minutes: int = Field(default=30)
    lunch_start: str | None = Field(default="13:00", max_length=5)
    lunch_end: str | None = Field(default="14:00", max_length=5)
    working_days: str = Field(default="0,1,2,3,4,5", max_length=32)  # lunes=0 ... domingo=6
    updated_at: datetime = Field(default_factory=utc_now)
