"""Aplicación FastAPI del simulador de operaciones retail."""

from fastapi import FastAPI

from app.api.v1.router import router as v1_router
from app.core.config import settings


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "Stateful retail operations simulator for the "
        "Cuidado con Rikochet data ecosystem."
    ),
)

# Registrar rutas v1 (health + catalog + futuros)
app.include_router(v1_router)