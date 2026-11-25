"""Google OAuth 2.0.

Permite a los clientes iniciar sesion con su cuenta de Google.
Requiere las variables GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET /
GOOGLE_REDIRECT_URI en el archivo .env. Si no estan definidas, el inicio de
sesion con Google queda desactivado (el frontend oculta el boton).

Flujo (Authorization Code + PKCE no usado por simplicidad de una SPA
en un unico origen):
  1. GET /auth/google -> redirige al usuario a Google.
  2. Google redirige a /auth/google/callback?code=...&state=...
  3. El callback intercambia el codigo por tokens, valida el id_token,
     encuentra o crea el usuario y devuelve un HTML minimo que guarda
     el token de KEREM en localStorage y redirige a "/".
"""
from __future__ import annotations

import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests

from app.config import settings
from app.database import get_session
from app.models import Role, User
from app.security import create_access_token, get_user_by_email
from sqlmodel import Session

router = APIRouter(prefix="/auth/google", tags=["auth"])

# Guarda los valores de "state" emitidos y no consumidos (para validar
# la respuesta del callback y evitar CSRF). Suficiente para una instancia.
_STATE_STORE: set[str] = set()

_GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


def _google_enabled() -> bool:
    """True si la configuracion de Google esta completa."""
    return bool(
        settings.google_client_id
        and settings.google_client_secret
        and settings.google_redirect_uri
    )


@router.get("/status")
def google_status() -> dict:
    """Indica si el login con Google esta habilitado."""
    return {"enabled": _google_enabled()}


@router.get("", include_in_schema=False)
def google_login() -> RedirectResponse:
    """Redirige al usuario a Google para autorizar la aplicacion."""
    if not _google_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Inicio de sesion con Google no configurado.",
        )

    state = secrets.token_urlsafe(16)
    _STATE_STORE.add(state)

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "online",
        "prompt": "select_account",
        "state": state,
    }
    return RedirectResponse(f"{_GOOGLE_AUTH_URL}?{urlencode(params)}")


@router.get("/callback", response_class=HTMLResponse, include_in_schema=False)
def google_callback(code: str, state: str) -> HTMLResponse:
    """Recibe el codigo de Google, valida y crea/autentica al usuario."""
    if not _google_enabled():
        return HTMLResponse(_page_html("error", "Google no esta configurado."))

    if state not in _STATE_STORE:
        return HTMLResponse(
            _page_html("error", "Solicitud invalida (state no coincide).")
        )
    _STATE_STORE.discard(state)

    token_data = _exchange_code_for_token(code)
    idinfo = _verify_id_token(token_data)
    email = idinfo.get("email")
    if not email:
        return HTMLResponse(
            _page_html("error", "Google no devolvio un correo.")
        )

    session = next(get_session())
    try:
        user = get_user_by_email(session, email)
        if user is None:
            user = User(
                email=email.lower(),
                hashed_password="",  # solo acceso via Google
                full_name=(idinfo.get("name") or "").strip(),
                phone=None,
                role=Role.CLIENT,
            )
            session.add(user)
            session.commit()
            session.refresh(user)
        elif not user.is_active:
            return HTMLResponse(
                _page_html("error", "La cuenta esta desactivada.")
            )

        token = create_access_token(str(user.id), user.role.value)
    finally:
        session.close()

    # Pagina minima que guarda el token y redirige a la SPA.
    import json

    safe_token = json.dumps(token)
    safe_user = json.dumps(_user_summary(user))
    page = f"""
<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Ingresando...</title></head>
<body style="font-family:system-ui;background:#14110f;color:#f5efe7;display:grid;place-items:center;
height:100vh;margin:0;text-align:center">
  <p>Iniciando sesión con Google...</p>
  <script>
    sessionStorage.setItem('kerem_token', {safe_token});
    sessionStorage.setItem('kerem_user', JSON.stringify({safe_user}));
    location.href = '/';
  </script>
  <noscript><a href="/" style="color:#d4af7a">Continuar</a></noscript>
</body>
</html>
"""
    return HTMLResponse(page)


def _exchange_code_for_token(code: str) -> dict:
    """Intercambia el codigo de autorizacion por tokens de Google."""
    payload = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.google_redirect_uri,
        "grant_type": "authorization_code",
    }
    try:
        resp = httpx.post(_GOOGLE_TOKEN_URL, data=payload, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="No se pudo intercambiar el codigo con Google.",
        ) from exc


def _verify_id_token(token_data: dict) -> dict:
    """Valida el id_token de Google y devuelve sus claims."""
    idt = token_data.get("id_token")
    if not idt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google no devolvio un id_token.",
        )
    try:
        info = id_token.verify_oauth2_token(
            idt,
            google_requests.Request(),
            settings.google_client_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="El token de Google no es valido.",
        ) from exc
    return info


def _user_summary(user: User) -> dict:
    return {"id": user.id, "email": user.email, "full_name": user.full_name,
            "role": user.role.value}


def _page_html(status_label: str, message: str) -> str:
    """Pagina HTML de resultado de error."""
    import html as _html

    msg = _html.escape(message)
    return f"""
<!doctype html>
<html lang="es"><head><meta charset="utf-8"><title>KEREM</title></head>
<body style="font-family:system-ui;display:grid;place-items:center;
height:100vh;margin:0;text-align:center">
  <div>
    <h2>{status_label.upper()}</h2>
    <p>{msg}</p>
    <a href="/">Volver al inicio</a>
  </div>
</body></html>
"""
