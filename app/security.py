"""Seguridad: hashing de contrasenas, JWT y dependencias de autorizacion."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from jose import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt
from sqlmodel import Session, select

from app.config import settings
from app.database import get_session
from app.models import Role, User

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login",
    auto_error=False,
)

# --------------------------------------------------------------------------
# Hashing
# --------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """Devuelve el hash bcrypt de la contrasena (bytes como str)."""
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica una contrasena contra su hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


# --------------------------------------------------------------------------
# JWT
# --------------------------------------------------------------------------
def create_access_token(
    subject: str,
    role: str,
    expires_delta: timedelta | None = None,
) -> str:
    """Crea un token JWT firmado con el rol del usuario."""
    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload = {
        "sub": subject,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(
        payload, settings.secret_key, algorithm=settings.algorithm
    )


def decode_token(token: str) -> dict:
    """Decodifica y valida un JWT; lanza HTTP 401 si es invalido o expiro."""
    try:
        return jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
    except jwt.JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesion invalida o expirada.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# --------------------------------------------------------------------------
# Dependencias
# --------------------------------------------------------------------------
def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    session: Annotated[Session, Depends(get_session)],
) -> User:
    """Resuelve el usuario autenticado a partir del token Bearer."""
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autenticado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(token)
    user_id = int(payload.get("sub", 0))
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o inactivo.",
        )
    return user


def require_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Restringe el acceso a usuarios con rol administrador."""
    if current_user.role != Role.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Requiere permisos de administrador.",
        )
    return current_user


def get_user_by_email(session: Session, email: str) -> User | None:
    """Busca un usuario por su correo (case-insensitive)."""
    stmt = select(User).where(
        User.email.ilike(email.strip())
    )
    return session.exec(stmt).first()
