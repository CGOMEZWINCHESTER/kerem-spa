"""Conexion a la base de datos PostgreSQL (Supabase) usando SQLModel."""
from collections.abc import Generator

from sqlalchemy.pool import NullPool
from sqlmodel import Session, create_engine

from app.config import settings

_db_url = settings.database_url
_connect_args = {"check_same_thread": False} if _db_url.startswith("sqlite") else {}

_engine_kwargs = {
    "echo": False,
    "pool_pre_ping": True,
    "connect_args": _connect_args,
}

# En Vercel/serverless con Supabase transaction pooler, NullPool evita agotar conexiones.
if not _db_url.startswith("sqlite"):
    _engine_kwargs["poolclass"] = NullPool

engine = create_engine(_db_url, **_engine_kwargs)


def get_session() -> Generator[Session, None, None]:
    """Dependency de FastAPI que provee una sesion por request."""
    with Session(engine) as session:
        yield session
