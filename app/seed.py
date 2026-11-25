"""Crea las tablas, el administrador inicial y los servicios por defecto.

Uso:  python -m app.seed
"""
from sqlmodel import Session, select

from app.config import settings
from app.database import engine
from app.models import Role, Service, User
from app.security import get_user_by_email, hash_password
from app import models  # noqa: F401  (garantiza el registro de las tablas)


def seed() -> None:
    """Crea tablas si no existen y siembra datos iniciales."""
    models.SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        # Administrador inicial.
        admin = get_user_by_email(session, settings.admin_email)
        if admin is None:
            session.add(
                User(
                    email=settings.admin_email.lower(),
                    hashed_password=hash_password(settings.admin_password),
                    full_name=settings.admin_name,
                    role=Role.ADMIN,
                    phone=None,
                )
            )
            print(f"[seed] Administrador creado: {settings.admin_email}")
        else:
            print("[seed] Administrador ya existe (omitido).")

        # Servicios por defecto.
        defaults = [
            Service(
                name="Masaje Reductivo",
                description=(
                    "Tecnicas profundas para reducir medidas y mejorar el "
                    "tono corporal."
                ),
                price=450.0,
                duration_minutes=60,
            ),
            Service(
                name="Masaje Relajante",
                description=(
                    "Movimientos suaves y envolventes para liberar tension y "
                    "promover el bienestar."
                ),
                price=350.0,
                duration_minutes=50,
            ),
        ]
        for svc in defaults:
            exists = session.exec(
                select(Service).where(Service.name == svc.name)
            ).first()
            if exists is None:
                session.add(svc)
                print(f"[seed] Servicio creado: {svc.name}")

        session.commit()
        print("[seed] Listo.")


if __name__ == "__main__":
    seed()
