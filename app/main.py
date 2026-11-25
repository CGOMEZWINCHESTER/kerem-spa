"""Punto de entrada de la aplicacion FastAPI para KEREM.

Incluye los routers, CORS y el servido de archivos estaticos del frontend.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.routers import admin, appointment, auth, auth_google, notifications

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(
    title="KEREM Spa API",
    description=(
        "Gestion del spa de masajes reductivos y relajantes. Autenticacion, "
        "agendamiento de citas y dashboard de administracion."
    ),
    version="1.0.0",
)


@app.middleware("http")
async def log_admin_bodies(request, call_next):
    """Diagnostico temporal: registra el cuerpo de escritura del panel admin.

    Permite ver en consola exactamente que datos llegan al guardar ficha,
    evolucion, paciente/cita/servicio (para depurar guardados en blanco).
    """
    if request.method in ("POST", "PUT", "PATCH") and request.url.path.startswith(
        "/admin"
    ):
        raw = (await request.body()).decode("utf-8", "replace")
        response = await call_next(request)
        print(
            f"[BODY] {request.method} {request.url.path} -> {response.status_code} "
            f"cuerpo={raw[:800]}"
        )
        return response
    return await call_next(request)


@app.middleware("http")
async def frontend_cache_control(request, call_next):
    """Control de cache para PWA: shell sin cache agresivo, assets versionados cacheables."""
    response = await call_next(request)
    path = request.url.path
    if path in ("/", "/dashboard", "/privacy", "/terms", "/static/index.html", "/static/dashboard.html", "/static/privacy.html", "/static/terms.html"):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    elif path == "/static/sw.js":
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    elif path == "/static/manifest.json":
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    elif path.startswith("/static/"):
        response.headers.setdefault("Cache-Control", "public, max-age=3600")
    return response

# CORS: permitir el frontend servido por nosotros mismos y clientes externos.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(auth_google.router)
app.include_router(appointment.router)
app.include_router(admin.router)
app.include_router(notifications.router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Endpoint de comprobacion de estado."""
    return {"status": "ok"}


# Servir el frontend estatico.
app.mount("/static", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")


@app.get("/", include_in_schema=False)
def root() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/dashboard", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(STATIC_DIR / "dashboard.html")


@app.get("/sw.js", include_in_schema=False)
def service_worker() -> FileResponse:
    return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript")


@app.get("/manifest.json", include_in_schema=False)
def manifest() -> FileResponse:
    return FileResponse(STATIC_DIR / "manifest.json", media_type="application/manifest+json")


@app.get("/privacy", include_in_schema=False)
def privacy() -> FileResponse:
    return FileResponse(STATIC_DIR / "privacy.html")


@app.get("/terms", include_in_schema=False)
def terms() -> FileResponse:
    return FileResponse(STATIC_DIR / "terms.html")
