"""Configuracion central de la aplicacion.

Lee las variables de entorno desde un archivo `.env` en la raiz del
proyecto (ver `.env.example`).
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracion tipada de la aplicacion."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Cadena de conexion PostgreSQL (Supabase).
    # En Vercel usa el Transaction Pooler (puerto 6543) y sslmode=require.
    database_url: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/kerem"
    )

    # JWT.
    secret_key: str = "change-me"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 horas

    # Admin inicial (sembrado por `app.seed`).
    admin_email: str = "admin@keremspa.com"
    admin_password: str = "CambiaEstaClave123!"
    admin_name: str = "Administrador KEREM"

    # Agenda diaria (hora en formato "HH:MM", hora local del spa).
    # Franja de almuerzo (None desactiva la pausa).
    agenda_start: str = "09:00"
    agenda_end: str = "20:00"
    agenda_step_minutes: int = 30
    agenda_lunch_start: str | None = "13:00"
    agenda_lunch_end: str | None = "14:00"

    # SMTP para confirmaciones. MAIL_ENABLED=False desactiva el envio.
    mail_enabled: bool = False
    mail_host: str = "smtp.gmail.com"
    mail_port: int = 587
    mail_username: str = ""  # email del remitente
    mail_password: str = ""  # app password / API key
    mail_from: str = "KEREM Spa <no-reply@keremspa.com>"
    mail_use_tls: bool = True

    # Google OAuth 2.0 (login con cuenta de Google).
    # Vacio = funcion desactivada (el boton se oculta).
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""


@lru_cache
def get_settings() -> Settings:
    """Devuelve la configuracion, cacheada para toda la vida del proceso."""
    return Settings()


settings = get_settings()
