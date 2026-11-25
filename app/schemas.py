"""Schemas de entrada/salida para la API (tipados con SQLModel/Pydantic)."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import EmailStr, Field
from sqlmodel import SQLModel

from app.models import AppointmentStatus, Role


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------
class UserRegister(SQLModel):
    """Datos para registrar un cliente."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    birth_date: date | None = None
    address: str | None = Field(default=None, max_length=255)
    occupation: str | None = Field(default=None, max_length=120)


class UserLogin(SQLModel):
    """Credenciales de inicio de sesion."""

    email: EmailStr
    password: str


class Token(SQLModel):
    """Respuesta de login/registro autenticado."""

    access_token: str
    token_type: str = "bearer"


class UserRead(SQLModel):
    """Representacion publica de un usuario."""

    id: int
    email: EmailStr
    full_name: str
    phone: str | None
    birth_date: date | None
    address: str | None
    occupation: str | None
    role: Role
    created_at: datetime


class UserUpdate(SQLModel):
    """Actualizacion de datos de un paciente por el administrador."""

    email: EmailStr | None = None
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=30)
    birth_date: date | None = None
    address: str | None = Field(default=None, max_length=255)
    occupation: str | None = Field(default=None, max_length=120)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    is_active: bool | None = None


# --------------------------------------------------------------------------
# Servicios
# --------------------------------------------------------------------------
class ServiceCreate(SQLModel):
    name: str = Field(min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=400)
    price: float = Field(ge=0)
    duration_minutes: int = Field(ge=5, le=600)
    is_active: bool = True


class ServiceUpdate(SQLModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = Field(default=None, max_length=400)
    price: float | None = Field(default=None, ge=0)
    duration_minutes: int | None = Field(default=None, ge=5, le=600)
    is_active: bool | None = None


class ServiceRead(SQLModel):
    id: int
    name: str
    description: str | None
    price: float
    duration_minutes: int
    is_active: bool


# --------------------------------------------------------------------------
# Citas
# --------------------------------------------------------------------------
class AppointmentCreate(SQLModel):
    """Crear una cita (el servicio ya determina duracion)."""

    service_id: int
    starts_at: datetime
    notes: str | None = Field(default=None, max_length=400)


class AppointmentRead(SQLModel):
    id: int
    user_id: int
    service_id: int
    starts_at: datetime
    ends_at: datetime
    status: AppointmentStatus
    notes: str | None
    service_name: str | None = None
    service_price: float | None = None
    client_name: str | None = None
    client_phone: str | None = None
    client_email: str | None = None
    created_at: datetime


class AdminAppointmentUpdate(SQLModel):
    """Actualizaciones de administrador sobre una cita."""

    starts_at: datetime | None = None
    status: AppointmentStatus | None = None
    notes: str | None = None


class Slot(SQLModel):
    """Franja horaria disponible."""

    starts_at: datetime
    ends_at: datetime


# --------------------------------------------------------------------------
# Reportes admin
# --------------------------------------------------------------------------
class ReportSummary(SQLModel):
    total_appointments: int
    completed_appointments: int
    pending_appointments: int
    approved_appointments: int
    cancelled_appointments: int
    total_revenue: float
    completed_revenue: float
    expected_revenue: float


class ReportDay(SQLModel):
    date: str
    total_appointments: int
    completed_appointments: int
    pending_appointments: int
    approved_appointments: int
    cancelled_appointments: int
    total_revenue: float
    completed_revenue: float
    expected_revenue: float


class ReportResponse(SQLModel):
    period: str
    start_date: str
    end_date: str
    summary: ReportSummary
    days: list[ReportDay]


# --------------------------------------------------------------------------
# Pacientes / registros
# --------------------------------------------------------------------------
class PatientRecordRead(SQLModel):
    id: int
    user_id: int
    weight_kg: float | None
    height_cm: float | None
    waist_cm: float | None
    hip_cm: float | None
    abdomen_cm: float | None
    right_leg_cm: float | None
    left_leg_cm: float | None
    session_type: str | None
    techniques: str | None
    oils_lotions: str | None
    contraindications: str | None
    duration_minutes: int | None
    measurements_date: date
    clinical_notes: str | None


class PatientRecordCreate(SQLModel):
    weight_kg: float | None = Field(default=None, gt=0)
    height_cm: float | None = Field(default=None, gt=0)
    waist_cm: float | None = Field(default=None, gt=0)
    hip_cm: float | None = Field(default=None, gt=0)
    abdomen_cm: float | None = Field(default=None, gt=0)
    right_leg_cm: float | None = Field(default=None, gt=0)
    left_leg_cm: float | None = Field(default=None, gt=0)
    session_type: str | None = Field(default=None, max_length=40)
    techniques: str | None = Field(default=None, max_length=400)
    oils_lotions: str | None = Field(default=None, max_length=400)
    contraindications: str | None = Field(default=None, max_length=400)
    duration_minutes: int | None = Field(default=None, gt=0, le=600)
    measurements_date: date = Field(default_factory=date.today)
    clinical_notes: str | None = Field(default=None, max_length=800)


class ClinicalHistoryBase(SQLModel):
    """Campos compartidos de la ficha clinica del paciente."""

    reason_for_consultation: str | None = Field(default=None, max_length=800)
    treatment_objective: str | None = Field(default=None, max_length=800)

    surgeries: bool = False
    surgeries_detail: str | None = Field(default=None, max_length=400)
    surgeries_date: date | None = None
    cesarean: bool = False
    cesarean_detail: str | None = Field(default=None, max_length=400)
    cesarean_date: date | None = None
    pregnancy: bool = False
    lactation: bool = False
    menstruation: bool = False
    diu: str | None = Field(default=None, max_length=120)
    menopause: bool = False
    chronic_diabetes: bool = False
    chronic_hypertension: bool = False
    chronic_thyroid: bool = False
    chronic_heart: bool = False
    chronic_other: str | None = Field(default=None, max_length=400)
    current_medications: str | None = Field(default=None, max_length=800)

    weight_kg: float | None = Field(default=None, gt=0)
    height_cm: float | None = Field(default=None, gt=0)
    waist_cm: float | None = Field(default=None, gt=0)
    hip_cm: float | None = Field(default=None, gt=0)
    abdomen_cm: float | None = Field(default=None, gt=0)
    right_leg_cm: float | None = Field(default=None, gt=0)
    left_leg_cm: float | None = Field(default=None, gt=0)
    areas_fat: bool = False
    areas_cellulite: bool = False
    areas_retention: bool = False
    areas_other: str | None = Field(default=None, max_length=400)
    silhouette_notes: str | None = Field(default=None, max_length=800)

    sessions_recommended: int = Field(default=0, ge=0, le=100)
    sessions_completed: int = Field(default=0, ge=0, le=100)
    progress_notes: str | None = Field(default=None, max_length=800)
    consent_given: bool = False
    consent_signature: str | None = Field(default=None, max_length=255)
    consent_date: date | None = None


class ClinicalHistoryRead(ClinicalHistoryBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime


class ClinicalHistoryCreate(ClinicalHistoryBase):
    """Todo opcional: la ficha se crea vacia si el admin lo desea."""


class ClinicalHistoryUpdate(ClinicalHistoryBase):
    """Todos los campos explicitamente opcionales / editables."""
    pass


# --------------------------------------------------------------------------
# Notificaciones
# --------------------------------------------------------------------------
class NotificationRead(SQLModel):
    id: int
    user_id: int
    title: str
    message: str
    is_read: bool
    created_at: datetime
