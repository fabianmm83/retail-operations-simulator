"""Router principal de la API v1.

Agrupa todos los sub-routers de v1. Se incluye en app.main.
"""

from fastapi import APIRouter

from app.api.v1 import (
    catalog,
    customers,
    geography,
    health,
    inventory,
    sales,
    simulation,
    suppliers,
)


router = APIRouter()

router.include_router(health.router)
router.include_router(catalog.router)
router.include_router(geography.router)
router.include_router(customers.router)
router.include_router(inventory.router)
router.include_router(suppliers.router)
router.include_router(sales.router)
router.include_router(simulation.router)