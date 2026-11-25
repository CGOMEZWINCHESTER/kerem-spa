"""Migracion ligera para SQLite: crea tablas nuevas y agrega columnas.

Uso:  python -m app.migrate
"""
from sqlalchemy import inspect, text

from app import models  # noqa: F401  (registra las tablas en el metadata)
from app.database import engine


ADD_USER_COLUMNS = {
    "birth_date": "DATE",
    "address": "VARCHAR(255)",
    "occupation": "VARCHAR(120)",
}

ADD_PATIENT_RECORD_COLUMNS = {
    "abdomen_cm": "FLOAT",
    "right_leg_cm": "FLOAT",
    "left_leg_cm": "FLOAT",
    "session_type": "VARCHAR(40)",
    "techniques": "VARCHAR(400)",
    "oils_lotions": "VARCHAR(400)",
    "contraindications": "VARCHAR(400)",
    "duration_minutes": "INTEGER",
}


def _apply_column_alter(
    table: str, column_defs: dict[str, str]
) -> None:
    inspector = inspect(engine)
    existing = {col["name"] for col in inspector.get_columns(table)}
    with engine.begin() as conn:
        for name, coltype in column_defs.items():
            if name in existing:
                print(f"[migrate] {table}.{name}: ya existe (omitido).")
                continue
            conn.execute(
                text(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {coltype}')
            )
            print(f"[migrate] {table}.{name} agregada.")


def migrate() -> None:
    """Aplica los cambios de esquema sin perder datos."""
    models.SQLModel.metadata.create_all(engine)
    print("[migrate] Tablas nuevas creadas.")

    _apply_column_alter("user", ADD_USER_COLUMNS)
    _apply_column_alter("patient_record", ADD_PATIENT_RECORD_COLUMNS)
    print("[migrate] Listo.")


if __name__ == "__main__":
    migrate()