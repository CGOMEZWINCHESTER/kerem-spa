"""Notificaciones in-app y correos de aviso para eventos de citas."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Session

from app.mailer import send_mail
from app.models import Appointment, AppointmentStatus, Service, User


def fmt_dt(dt: datetime) -> str:
    """Formatea una fecha/hora (UTC) de forma legible en hora local del spa."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    local = dt.astimezone()  # usa la zona del servidor (ajustable via TZ)
    return local.strftime("%d/%m/%Y a las %H:%M")


def create_notification(
    session: Session, user_id: int, title: str, message: str
) -> None:
    """Inserta una notificacion in-app para un usuario."""
    # Import local para evitar dependencias circulares en el arranque.
    from app.models import Notification

    session.add(Notification(user_id=user_id, title=title, message=message))


def notify_status_change(
    session: Session,
    appointment: Appointment,
    service: Service,
) -> None:
    """Notifica al cliente y envia correo cuando cambia el estado de su cita.

    Usa el nombre/espejo de estado para decidir titulo y mensaje. Se invoca
    tras crear o actualizar una cita. Nota: el `commit` lo hace el llamador.
    """
    statuses: dict[AppointmentStatus, tuple[str, str]] = {
        AppointmentStatus.PENDING: (
            "Cita pendiente de confirmación",
            f"Tu cita de {service.name} el {fmt_dt(appointment.starts_at)} "
            "está pendiente. Te notificaremos al confirmarse.",
        ),
        AppointmentStatus.APPROVED: (
            "¡Tu cita fue confirmada!",
            f"Tu cita de {service.name} el {fmt_dt(appointment.starts_at)} "
            "fue aprobada. ¡Te esperamos!",
        ),
        AppointmentStatus.CANCELLED: (
            "Cita cancelada",
            f"Tu cita de {service.name} el {fmt_dt(appointment.starts_at)} "
            "fue cancelada. Si fue un error, contáctanos.",
        ),
        AppointmentStatus.COMPLETED: (
            "Cita completada",
            f"Gracias por tu visita. Tu sesión de {service.name} está "
            "completada. ¡Vuelve pronto!",
        ),
    }

    title, message = statuses.get(appointment.status, ("Notificación", ""))
    create_notification(session, appointment.user_id, title, message)

    if appointment.user is not None and appointment.user.email:
        send_mail(
            appointment.user.email,
            f"[KEREM] {title}",
            f"Hola {appointment.user.full_name or ''},\n\n{message}\n\n"
            "- Equipo KEREM Spa",
        )


def notify_admin_new_appointment(
    session: Session,
    appointment: Appointment,
    service: Service,
    admins: list[User],
) -> None:
    """Avisa a los administradores de una cita nueva pendiente."""
    title = "Nueva cita por confirmar"
    text = (
        f"El cliente {appointment.user.full_name or appointment.user.email} "
        f"agendó {service.name} para el {fmt_dt(appointment.starts_at)}."
    )
    for admin in admins:
        create_notification(session, admin.id, title, text)
