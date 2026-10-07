"""Endpoints de health check."""

from fastapi import APIRouter
from sqlalchemy import text

from app.db.session import engine


router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    """Verifica que el servicio esté vivo."""
    return {
        "status": "ok",
        "service": "retail-operations-simulator",
    }


@router.get("/health/database")
def database_health_check() -> dict[str, str]:
    """Verifica que la conexión a PostgreSQL funcione."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))

    return {
        "status": "ok",
        "database": "postgresql",
    }