"""Seed del catálogo (M1).

Genera:
- 12 categorías
- 30 productos (incluyendo los 3 Rikochet branded)
- ~250 variantes (SKUs)

Idempotente: si una categoría/producto ya existe (por code/style_code),
no lo duplica.

Uso:
    python -m app.seed.01_catalog
"""

from __future__ import annotations

import random
import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import (
    AgeGroupType,
    ColorCode,
    DemandProfileType,
    DepartmentType,
    LifecycleStageType,
    RecordStatus,
    SeasonalityType,
    SegmentType,
    SportType,
)
from app.db.session import SessionLocal
from app.models.catalog import Category, Product, ProductVariant


# =============================================================================
# DATOS DE CATEGORÍAS (12)
# =============================================================================

CATEGORIES_DATA = [
    # code,                    name,                     department,                     seasonality
    ("PLAYERAS",              "Playeras",               DepartmentType.APPAREL,         SeasonalityType.NONE),
    ("SUDADERAS",             "Sudaderas",              DepartmentType.APPAREL,         SeasonalityType.WINTER),
    ("PANTS",                 "Pants",                  DepartmentType.APPAREL,         SeasonalityType.WINTER),
    ("SHORTS",                "Shorts",                 DepartmentType.APPAREL,         SeasonalityType.SUMMER),
    ("LEGGINGS",              "Leggings",               DepartmentType.APPAREL,         SeasonalityType.NEW_YEAR),
    ("TENIS",                 "Tenis",                  DepartmentType.FOOTWEAR,        SeasonalityType.NONE),
    ("BALONES",               "Balones",                DepartmentType.EQUIPMENT,       SeasonalityType.NONE),
    ("EQUIPO_ENTRENAMIENTO",  "Equipo de Entrenamiento", DepartmentType.EQUIPMENT,      SeasonalityType.NEW_YEAR),
    ("GORRAS",                "Gorras",                 DepartmentType.ACCESSORIES,     SeasonalityType.SUMMER),
    ("MOCHILAS",              "Mochilas",               DepartmentType.ACCESSORIES,     SeasonalityType.NONE),
    ("BOTELLAS",              "Botellas",               DepartmentType.ACCESSORIES,     SeasonalityType.SUMMER),
    ("CALCETINES",            "Calcetines",             DepartmentType.ACCESSORIES,     SeasonalityType.NONE),
]


# =============================================================================
# TALLAS POR SEGMENTO Y CATEGORÍA
# =============================================================================

SIZES_BY_SEGMENT = {
    SegmentType.WOMEN:  ["XS", "S", "M", "L", "XL"],
    SegmentType.MEN:    ["S", "M", "L", "XL", "XXL"],
    SegmentType.KIDS:   ["4", "6", "8", "10", "12", "14"],
    SegmentType.UNISEX: ["OS"],
}

SIZES_TENIS_ADULT = ["24", "25", "26", "27", "28", "29", "30"]
SIZES_TENIS_KIDS  = ["20", "21", "22", "23", "24"]
SIZES_BALONES     = ["3", "4", "5"]
SIZES_BOTELLAS    = ["500ML", "750ML", "1L"]
SIZES_CALCETINES  = ["S", "M", "L"]


# =============================================================================
# COLORES POR SEGMENTO
# =============================================================================

COLORS_BY_SEGMENT = {
    SegmentType.WOMEN:  [ColorCode.BLK, ColorCode.WHT, ColorCode.GRY, ColorCode.PNK, ColorCode.NVY],
    SegmentType.MEN:    [ColorCode.BLK, ColorCode.NVY, ColorCode.GRY, ColorCode.RED, ColorCode.BLU],
    SegmentType.KIDS:   [ColorCode.PNK, ColorCode.BLU, ColorCode.GRN, ColorCode.YLW, ColorCode.RED],
    SegmentType.UNISEX: [ColorCode.BLK, ColorCode.NVY, ColorCode.GRY, ColorCode.WHT],
}


# =============================================================================
# DEFINICIÓN DE LOS 30 PRODUCTOS
# =============================================================================
# Formato:
#   (style_code, name, segment, category_code, sport, branded, price, cost, demand)
#
# Los precios y costos ya están precalculados siguiendo las reglas de A4.

PRODUCTS_DATA = [
    # --- PLAYERAS (6) -------------------------------------------------------
    ("PLY-W-0001", "Playera Rikochet Training Mujer",  SegmentType.WOMEN, "PLAYERAS", SportType.TRAINING, True,  Decimal("599.00"), Decimal("251.58"), DemandProfileType.HIGH),
    ("PLY-M-0001", "Playera Rikochet Training Hombre", SegmentType.MEN,   "PLAYERAS", SportType.TRAINING, True,  Decimal("599.00"), Decimal("251.58"), DemandProfileType.HIGH),
    ("PLY-K-0001", "Playera Rikochet Kids",            SegmentType.KIDS,  "PLAYERAS", SportType.GENERAL,  True,  Decimal("449.00"), Decimal("188.58"), DemandProfileType.HIGH),
    ("PLY-W-0002", "Playera Training Mujer",           SegmentType.WOMEN, "PLAYERAS", SportType.TRAINING, False, Decimal("399.00"), Decimal("151.62"), DemandProfileType.MEDIUM),
    ("PLY-M-0002", "Playera Training Hombre",          SegmentType.MEN,   "PLAYERAS", SportType.TRAINING, False, Decimal("399.00"), Decimal("151.62"), DemandProfileType.MEDIUM),
    ("PLY-K-0002", "Playera Deportiva Kids",           SegmentType.KIDS,  "PLAYERAS", SportType.GENERAL,  False, Decimal("299.00"), Decimal("125.58"), DemandProfileType.MEDIUM),

    # --- SUDADERAS (4) ------------------------------------------------------
    ("SUD-W-0001", "Sudadera Training Mujer",          SegmentType.WOMEN, "SUDADERAS", SportType.TRAINING, False, Decimal("699.00"), Decimal("286.59"), DemandProfileType.MEDIUM),
    ("SUD-M-0001", "Sudadera Training Hombre",         SegmentType.MEN,   "SUDADERAS", SportType.TRAINING, False, Decimal("699.00"), Decimal("286.59"), DemandProfileType.MEDIUM),
    ("SUD-K-0001", "Sudadera Deportiva Kids",          SegmentType.KIDS,  "SUDADERAS", SportType.GENERAL,  False, Decimal("499.00"), Decimal("214.57"), DemandProfileType.MEDIUM),
    ("SUD-M-0002", "Sudadera con Capucha Hombre",      SegmentType.MEN,   "SUDADERAS", SportType.CASUAL,   False, Decimal("799.00"), Decimal("327.59"), DemandProfileType.LOW),

    # --- PANTS (2) ----------------------------------------------------------
    ("PNT-W-0001", "Pants Training Mujer",             SegmentType.WOMEN, "PANTS", SportType.TRAINING, False, Decimal("799.00"), Decimal("327.59"), DemandProfileType.MEDIUM),
    ("PNT-M-0001", "Pants Training Hombre",            SegmentType.MEN,   "PANTS", SportType.TRAINING, False, Decimal("799.00"), Decimal("327.59"), DemandProfileType.MEDIUM),

    # --- SHORTS (2) ---------------------------------------------------------
    ("SHT-W-0001", "Shorts Training Mujer",            SegmentType.WOMEN, "SHORTS", SportType.TRAINING, False, Decimal("449.00"), Decimal("184.09"), DemandProfileType.MEDIUM),
    ("SHT-M-0001", "Shorts Training Hombre",           SegmentType.MEN,   "SHORTS", SportType.TRAINING, False, Decimal("449.00"), Decimal("184.09"), DemandProfileType.MEDIUM),

    # --- LEGGINGS (2) -------------------------------------------------------
    ("LEG-W-0001", "Leggings Training Mujer",          SegmentType.WOMEN, "LEGGINGS", SportType.YOGA,     False, Decimal("649.00"), Decimal("266.09"), DemandProfileType.MEDIUM),
    ("LEG-W-0002", "Leggings Yoga Mujer",              SegmentType.WOMEN, "LEGGINGS", SportType.YOGA,     False, Decimal("699.00"), Decimal("286.59"), DemandProfileType.LOW),

    # --- TENIS (4) ----------------------------------------------------------
    ("TEN-W-0001", "Tenis Running Mujer",              SegmentType.WOMEN, "TENIS", SportType.RUNNING, False, Decimal("1299.00"), Decimal("675.48"), DemandProfileType.MEDIUM),
    ("TEN-M-0001", "Tenis Running Hombre",             SegmentType.MEN,   "TENIS", SportType.RUNNING, False, Decimal("1299.00"), Decimal("675.48"), DemandProfileType.MEDIUM),
    ("TEN-M-0002", "Tenis Training Hombre",            SegmentType.MEN,   "TENIS", SportType.TRAINING, False, Decimal("1099.00"), Decimal("571.48"), DemandProfileType.LOW),
    ("TEN-K-0001", "Tenis Deportivo Kids",             SegmentType.KIDS,  "TENIS", SportType.GENERAL,  False, Decimal("899.00"),  Decimal("467.48"), DemandProfileType.LOW),

    # --- BALONES (2) --------------------------------------------------------
    ("BAL-U-0001", "Balón Fútbol Profesional",         SegmentType.UNISEX, "BALONES", SportType.FUTBOL, False, Decimal("499.00"), Decimal("274.45"), DemandProfileType.LOW),
    ("BAL-U-0002", "Balón Basket Oficial",             SegmentType.UNISEX, "BALONES", SportType.BASKET, False, Decimal("599.00"), Decimal("329.45"), DemandProfileType.NICHE),

    # --- EQUIPO_ENTRENAMIENTO (2) -------------------------------------------
    ("EQP-U-0001", "Kit Bandas de Resistencia",        SegmentType.UNISEX, "EQUIPO_ENTRENAMIENTO", SportType.TRAINING, False, Decimal("399.00"), Decimal("219.45"), DemandProfileType.LOW),
    ("EQP-U-0002", "Mat de Yoga Premium",              SegmentType.UNISEX, "EQUIPO_ENTRENAMIENTO", SportType.YOGA,     False, Decimal("699.00"), Decimal("384.45"), DemandProfileType.NICHE),

    # --- GORRAS (2) ---------------------------------------------------------
    ("GOR-U-0001", "Gorra Deportiva Rikochet",         SegmentType.UNISEX, "GORRAS", SportType.CASUAL, False, Decimal("349.00"), Decimal("157.05"), DemandProfileType.LOW),
    ("GOR-U-0002", "Gorra Running",                    SegmentType.UNISEX, "GORRAS", SportType.RUNNING, False, Decimal("299.00"), Decimal("134.55"), DemandProfileType.NICHE),

    # --- MOCHILAS (2) -------------------------------------------------------
    ("MOC-U-0001", "Mochila Training 25L",             SegmentType.UNISEX, "MOCHILAS", SportType.TRAINING, False, Decimal("799.00"), Decimal("359.55"), DemandProfileType.LOW),
    ("MOC-U-0002", "Mochila Casual 15L",               SegmentType.UNISEX, "MOCHILAS", SportType.CASUAL,   False, Decimal("599.00"), Decimal("269.55"), DemandProfileType.NICHE),

    # --- BOTELLAS (2) -------------------------------------------------------
    ("BOT-U-0001", "Botella Deportiva 750ml",          SegmentType.UNISEX, "BOTELLAS", SportType.GENERAL, False, Decimal("249.00"), Decimal("112.05"), DemandProfileType.LOW),
    ("BOT-U-0002", "Botella Térmica 1L",               SegmentType.UNISEX, "BOTELLAS", SportType.GENERAL, False, Decimal("349.00"), Decimal("157.05"), DemandProfileType.NICHE),

    # --- CALCETINES (2) -----------------------------------------------------
    ("CAL-W-0001", "Calcetines Training Mujer (3-pack)", SegmentType.WOMEN, "CALCETINES", SportType.TRAINING, False, Decimal("199.00"), Decimal("89.55"), DemandProfileType.MEDIUM),
    ("CAL-M-0001", "Calcetines Training Hombre (3-pack)", SegmentType.MEN,  "CALCETINES", SportType.TRAINING, False, Decimal("199.00"), Decimal("89.55"), DemandProfileType.MEDIUM),
]


# =============================================================================
# HELPERS
# =============================================================================


def _build_sizes(product_data: tuple, segment: SegmentType, category_code: str) -> list[str]:
    """Determina las tallas disponibles según segmento y categoría."""
    if category_code == "TENIS":
        if segment == SegmentType.KIDS:
            return SIZES_TENIS_KIDS
        return SIZES_TENIS_ADULT
    if category_code == "BALONES":
        return SIZES_BALONES
    if category_code == "BOTELLAS":
        return SIZES_BOTELLAS
    if category_code == "CALCETINES":
        return SIZES_CALCETINES
    # Apparel y accesorios tallados / OS
    return SIZES_BY_SEGMENT.get(segment, ["OS"])


def _build_colors(segment: SegmentType) -> list[ColorCode]:
    """Devuelve la paleta de colores del segmento."""
    return COLORS_BY_SEGMENT.get(segment, [ColorCode.BLK])


def _build_barcode() -> str:
    """Genera un EAN-13 simulado (13 dígitos)."""
    return "".join(str(random.randint(0, 9)) for _ in range(13))


# =============================================================================
# SEED
# =============================================================================


def seed_categories(db: Session) -> dict[str, Category]:
    """Crea las 12 categorías si no existen. Devuelve dict code → Category."""
    result: dict[str, Category] = {}

    for code, name, department, seasonality in CATEGORIES_DATA:
        existing = db.scalar(select(Category).where(Category.code == code))
        if existing is not None:
            result[code] = existing
            continue

        category = Category(
            id=uuid.uuid4(),
            code=code,
            name=name,
            department=department,
            seasonality=seasonality,
            status=RecordStatus.ACTIVE,
        )
        db.add(category)
        result[code] = category

    db.flush()
    return result


def seed_products(db: Session, categories: dict[str, Category]) -> dict[str, Product]:
    """Crea los 30 productos si no existen. Devuelve dict style_code → Product."""
    result: dict[str, Product] = {}

    for (
        style_code,
        name,
        segment,
        category_code,
        sport,
        branded,
        price,
        cost,
        demand,
    ) in PRODUCTS_DATA:
        existing = db.scalar(select(Product).where(Product.style_code == style_code))
        if existing is not None:
            result[style_code] = existing
            continue

        category = categories[category_code]
        age_group = AgeGroupType.KIDS if segment == SegmentType.KIDS else AgeGroupType.ADULT

        product = Product(
            id=uuid.uuid4(),
            style_code=style_code,
            name=name,
            segment=segment,
            age_group=age_group,
            category_id=category.id,
            sport=sport,
            branded=branded,
            base_price=price,
            base_cost=cost,
            demand_profile=demand,
            lifecycle_stage=LifecycleStageType.MATURE,
            launch_date=date(2026, 1, 1),
            status=RecordStatus.ACTIVE,
        )
        db.add(product)
        result[style_code] = product

    db.flush()
    return result


def seed_variants(db: Session, products: dict[str, Product]) -> int:
    """Crea las variantes (SKUs) para cada producto. Devuelve total creadas."""
    created = 0

    for (
        style_code,
        _name,
        segment,
        category_code,
        _sport,
        _branded,
        _price,
        _cost,
        _demand,
    ) in PRODUCTS_DATA:
        product = products[style_code]
        sizes = _build_sizes((), segment, category_code)
        colors = _build_colors(segment)

        for size in sizes:
            for color in colors:
                sku = f"{style_code}-{size}-{color.value}"

                existing = db.scalar(
                    select(ProductVariant).where(ProductVariant.sku == sku)
                )
                if existing is not None:
                    continue

                variant = ProductVariant(
                    id=uuid.uuid4(),
                    sku=sku,
                    product_id=product.id,
                    size=size,
                    color=color,
                    barcode=_build_barcode(),
                    status=RecordStatus.ACTIVE,
                )
                db.add(variant)
                created += 1

    db.flush()
    return created


def run() -> None:
    """Entry point del seed."""
    print("Seeding catalog...")

    with SessionLocal() as db:
        categories = seed_categories(db)
        print(f"  Categories: {len(categories)} (idempotent)")

        products = seed_products(db, categories)
        print(f"  Products:   {len(products)} (idempotent)")

        variants_created = seed_variants(db, products)
        total_variants = db.scalar(
            select(ProductVariant).with_only_columns(
                __import__("sqlalchemy").func.count()
            )
        )
        print(f"  Variants:   {total_variants} total ({variants_created} new)")

        db.commit()

    print("Catalog seed done.")


if __name__ == "__main__":
    run()