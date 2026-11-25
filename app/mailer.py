"""Servicio de correo electronico (SMTP) para confirmaciones de KEREM.

Si el envio esta deshabilitado (MAIL_ENABLED=False) o faltan credenciales,
los correos se registran en el log en lugar de enviarse, para que el flujo
de la app no falle en desarrollo.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from typing import Sequence

from app.config import settings

logger = logging.getLogger("kerem.mailer")


def _mail_ready() -> bool:
    """True si el envio de correo esta habilitado y configurado."""
    return bool(
        settings.mail_enabled
        and settings.mail_username
        and settings.mail_password
    )


def send_mail(to: str | Sequence[str], subject: str, body: str) -> bool:
    """Envia un correo de texto plano. Devuelve True si se envio o se logueo.

    Nunca lanza excepciones: los errores de SMTP se registran y se retornan
    como False para no interrumpir la operacion principal.
    """
    recipients = [to] if isinstance(to, str) else list(to)
    if not _mail_ready():
        logger.info("[mailer:disabled] To=%s | Subject=%s | Body=%s",
                    recipients, subject, body[:200])
        return True

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.mail_from
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)

    try:
        with smtplib.SMTP(
            settings.mail_host, settings.mail_port, timeout=10
        ) as smtp:
            if settings.mail_use_tls:
                smtp.starttls()
            smtp.login(settings.mail_username, settings.mail_password)
            smtp.send_message(msg)
        logger.info("[mailer:ok] To=%s Subject=%s", recipients, subject)
        return True
    except Exception as exc:  # noqa: BLE001 - no interrumpir el flujo
        logger.warning(
            "[mailer:error] To=%s Subject=%s: %s", recipients, subject, exc
        )
        return False
