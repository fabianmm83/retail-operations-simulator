"""Endpoints read-only del catálogo.

En V1 solo exponemos lectura. Las escrituras vienen del seed y
del motor de simulación, no de la API.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.catalog import Category, Product, ProductVariant
from app.schemas.catalog import (
    CategoryRead,
    ProductRead,
    ProductReadWithVariants,
    ProductVariantRead,
)


router = APIRouter(prefix="/api/v1/catalog", tags=["catalog"])


# =============================================================================
# CATEGORIES
# =============================================================================


@router.get(
    "/categories",
    response_model=list[CategoryRead],
    summary="Listar categorías",
)
def list_categories(
    db: Session = Depends(get_db),
) -> list[Category]:
    stmt = select(Category).order_by(Category.code)
    return list(db.scalars(stmt).all())


@router.get(
    "/categories/{category_id}",
    response_model=CategoryRead,
    summary="Obtener una categoría por ID",
)
def get_category(
    category_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Category:
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )
    return category


# =============================================================================
# PRODUCTS
# =============================================================================


@router.get(
    "/products",
    response_model=list[ProductRead],
    summary="Listar productos",
)
def list_products(
    db: Session = Depends(get_db),
    category_id: uuid.UUID | None = Query(default=None),
    segment: str | None = Query(default=None),
    branded: bool | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[Product]:
    stmt = select(Product).order_by(Product.style_code)

    if category_id is not None:
        stmt = stmt.where(Product.category_id == category_id)
    if segment is not None:
        stmt = stmt.where(Product.segment == segment)
    if branded is not None:
        stmt = stmt.where(Product.branded == branded)

    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


@router.get(
    "/products/{product_id}",
    response_model=ProductReadWithVariants,
    summary="Obtener un producto con sus variantes",
)
def get_product(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Product:
    product = db.get(Product, product_id)
    if product is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found",
        )
    return product


# =============================================================================
# PRODUCT VARIANTS (SKUs)
# =============================================================================


@router.get(
    "/variants",
    response_model=list[ProductVariantRead],
    summary="Listar variantes (SKUs)",
)
def list_variants(
    db: Session = Depends(get_db),
    product_id: uuid.UUID | None = Query(default=None),
    color: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[ProductVariant]:
    stmt = select(ProductVariant).order_by(ProductVariant.sku)

    if product_id is not None:
        stmt = stmt.where(ProductVariant.product_id == product_id)
    if color is not None:
        stmt = stmt.where(ProductVariant.color == color)

    stmt = stmt.limit(limit).offset(offset)
    return list(db.scalars(stmt).all())


@router.get(
    "/variants/{variant_id}",
    response_model=ProductVariantRead,
    summary="Obtener una variante por ID",
)
def get_variant(
    variant_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ProductVariant:
    variant = db.get(ProductVariant, variant_id)
    if variant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ProductVariant not found",
        )
    return variant