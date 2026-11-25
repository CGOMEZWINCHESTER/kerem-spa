"""Rutas de autenticacion: registro, login y perfil."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.database import get_session
from app.models import Role, User
from app.schemas import Token, UserLogin, UserRead, UserRegister
from app.security import (
    create_access_token,
    get_current_user,
    get_user_by_email,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=Token,
    status_code=status.HTTP_201_CREATED,
)
def register(
    payload: UserRegister,
    session: Annotated[Session, Depends(get_session)],
) -> Token:
    """Registra un nuevo cliente y devuelve el token de acceso."""
    if get_user_by_email(session, payload.email) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ya existe una cuenta con ese correo.",
        )

    user = User(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name.strip(),
        phone=payload.phone,
        role=Role.CLIENT,
    )
    session.add(user)
    session.commit()
    session.refresh(user)

    token = create_access_token(str(user.id), user.role.value)
    return Token(access_token=token)


@router.post("/login", response_model=Token)
def login(
    payload: UserLogin,
    session: Annotated[Session, Depends(get_session)],
) -> Token:
    """Inicia sesion con correo y contrasena."""
    user = get_user_by_email(session, payload.email)
    valid = user is not None and verify_password(
        payload.password, user.hashed_password
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Correo o contrasena incorrectos.",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La cuenta esta desactivada.",
        )

    token = create_access_token(str(user.id), user.role.value)
    return Token(access_token=token)


@router.get("/me", response_model=UserRead)
def me(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Devuelve el perfil del usuario autenticado."""
    return current_user
