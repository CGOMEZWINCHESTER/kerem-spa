"""Rutas de notificaciones in-app (cliente y administrador)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.models import Notification, User
from app.schemas import NotificationRead
from app.security import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationRead])
def my_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    only_unread: bool = False,
) -> list[Notification]:
    """Notificaciones del usuario autenticado (mas nuevas primero)."""
    stmt = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
    )
    if only_unread:
        stmt = stmt.where(Notification.is_read == False)  # noqa: E712
    return list(session.exec(stmt).all())


@router.get("/unread-count", response_model=dict[str, int])
def unread_count(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, int]:
    """Cantidad de notificaciones sin leer del usuario actual."""
    stmt = select(Notification).where(
        Notification.user_id == current_user.id,
        Notification.is_read == False,  # noqa: E712
    )
    return {"count": len(session.exec(stmt).all())}


@router.patch("/{notification_id}/read", response_model=NotificationRead)
def mark_as_read(
    notification_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Notification:
    """Marca como leida una notificacion propia."""
    note = session.get(Notification, notification_id)
    if note is None or note.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notificacion no encontrada.",
        )
    note.is_read = True
    session.add(note)
    session.commit()
    session.refresh(note)
    return note


@router.patch("/read-all", response_model=dict[str, int])
def mark_all_read(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, int]:
    """Marca todas las notificaciones del usuario como leidas."""
    stmt = select(Notification).where(
        Notification.user_id == current_user.id,
        Notification.is_read == False,  # noqa: E712
    )
    notes = list(session.exec(stmt).all())
    for note in notes:
        note.is_read = True
        session.add(note)
    session.commit()
    return {"updated": len(notes)}


@router.delete("", response_model=dict[str, int])
def clear_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> dict[str, int]:
    """Elimina todas las notificaciones del usuario actual."""
    stmt = select(Notification).where(Notification.user_id == current_user.id)
    notes = list(session.exec(stmt).all())
    for note in notes:
        session.delete(note)
    session.commit()
    return {"deleted": len(notes)}
