"""Seed de clientes (M3).

Genera:
- 10,000 clientes iniciales con distribución por perfil (Bloque C)
- ~25,000 preferencias de categoría (2–3 por cliente)

Distribución por perfil:
    NEW         4%   →    400
    ONE_TIME   18%   →  1,800
    OCCASIONAL 25%   →  2,500
    REGULAR    30%   →  3,000
    LOYAL      13%   →  1,300
    INACTIVE   10%   →  1,000

Uso:
    python -m app.seed.customers
"""

from __future__ import annotations

import random
import uuid
from datetime import date, timedelta
from decimal import Decimal

from faker import Faker
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import (
    ChannelPreference,
    CustomerProfile,
    GenderType,
    PriceSensitivity,
    RecordStatus,
    SegmentType,
)
from app.db.session import SessionLocal
from app.models.catalog import Category
from app.models.customers import Customer, CustomerCategoryPreference
from app.models.geography import State


# =============================================================================
# CONFIGURACIÓN
# =============================================================================

TOTAL_CUSTOMERS = 10_000
SIMULATION_START = date(2026, 1, 1)

# Distribución de perfiles (suma = 1.00)
PROFILE_DISTRIBUTION = {
    CustomerProfile.NEW:        0.04,
    CustomerProfile.ONE_TIME:   0.18,
    CustomerProfile.OCCASIONAL: 0.25,
    CustomerProfile.REGULAR:    0.30,
    CustomerProfile.LOYAL:      0.13,
    CustomerProfile.INACTIVE:   0.10,
}

# Distribución de estados (share de población relativo, renormalizado)
STATE_DISTRIBUTION = {
    "CDMX":   0.15,
    "EDOMEX": 0.21,
    "JAL":    0.14,
    "NL":     0.09,
    "PUE":    0.10,
    "CHIS":   0.08,
    "OAX":    0.07,
    "BC":     0.06,
    "QRO":    0.05,
    "GRO":    0.05,
}

# Ciudades por estado (una lista pequeña por estado, para dar variedad)
CITIES_BY_STATE = {
    "CDMX":   ["Ciudad de México"],
    "EDOMEX": ["Naucalpan", "Tlalnepantla", "Toluca", "Ecatepec"],
    "JAL":    ["Guadalajara", "Zapopan", "Tlaquepaque", "Tonalá"],
    "NL":     ["Monterrey", "San Pedro Garza García", "Guadalupe", "Apodaca"],
    "PUE":    ["Puebla", "San Andrés Cholula", "Tehuacán"],
    "CHIS":   ["Tuxtla Gutiérrez", "San Cristóbal de las Casas", "Tapachula"],
    "OAX":    ["Oaxaca de Juárez", "Salina Cruz", "Tuxtepec"],
    "BC":     ["Tijuana", "Mexicali", "Ensenada"],
    "QRO":    ["Querétaro", "San Juan del Río", "Corregidora"],
    "GRO":    ["Acapulco", "Chilpancingo", "Iguala"],
}

# Distribución de género
GENDER_DISTRIBUTION = {
    GenderType.FEMALE: 0.52,
    GenderType.MALE:   0.46,
    GenderType.OTHER:  0.02,
}

# Distribución de segmento preferido según género (Bloque C9.1)
PREFERRED_SEGMENT_BY_GENDER = {
    GenderType.FEMALE: [
        (SegmentType.WOMEN,  0.70),
        (SegmentType.MEN,    0.05),
        (SegmentType.KIDS,   0.20),
        (SegmentType.UNISEX, 0.05),
    ],
    GenderType.MALE: [
        (SegmentType.WOMEN,  0.05),
        (SegmentType.MEN,    0.70),
        (SegmentType.KIDS,   0.20),
        (SegmentType.UNISEX, 0.05),
    ],
    GenderType.OTHER: [
        (SegmentType.WOMEN,  0.35),
        (SegmentType.MEN,    0.35),
        (SegmentType.KIDS,   0.25),
        (SegmentType.UNISEX, 0.05),
    ],
}


# =============================================================================
# HELPERS
# =============================================================================


def _weighted_choice(options: dict) -> str:
    """Elige una clave de un dict {valor: peso}."""
    values = list(options.keys())
    weights = list(options.values())
    return random.choices(values, weights=weights, k=1)[0]


def _choose_segment(gender: GenderType) -> SegmentType:
    """Elige segmento preferido según género."""
    options = PREFERRED_SEGMENT_BY_GENDER[gender]
    segments = [s for s, _ in options]
    weights = [w for _, w in options]
    return random.choices(segments, weights=weights, k=1)[0]


def _choose_age_segment(segment: SegmentType) -> int:
    """Edad coherente con el segmento preferido."""
    if segment == SegmentType.KIDS:
        return random.randint(25, 50)  # el adulto que compra para niños
    if segment == SegmentType.UNISEX:
        return random.randint(40, 65)
    return random.randint(18, 55)


def _choose_channel(state_online_penetration: Decimal) -> ChannelPreference:
    """Asigna canal preferido según penetración online del estado (Bloque C6)."""
    p_online = float(state_online_penetration)

    if random.random() < p_online:
        return ChannelPreference.ONLINE if random.random() < 0.75 else ChannelPreference.OMNICHANNEL
    return ChannelPreference.STORE if random.random() < 0.70 else ChannelPreference.OMNICHANNEL


def _choose_price_sensitivity(state_income_index: Decimal) -> PriceSensitivity:
    """Sensibilidad al precio según ingreso relativo del estado (Bloque C8.2)."""
    income = float(state_income_index)

    if income >= 1.10:
        weights = {PriceSensitivity.LOW: 0.40, PriceSensitivity.MEDIUM: 0.50, PriceSensitivity.HIGH: 0.10}
    elif income >= 0.90:
        weights = {PriceSensitivity.LOW: 0.15, PriceSensitivity.MEDIUM: 0.60, PriceSensitivity.HIGH: 0.25}
    else:
        weights = {PriceSensitivity.LOW: 0.10, PriceSensitivity.MEDIUM: 0.45, PriceSensitivity.HIGH: 0.45}

    return _weighted_choice(weights)


def _choose_signup_date(profile: CustomerProfile) -> date:
    """Fecha de registro simulada según perfil."""
    if profile == CustomerProfile.NEW:
        # Recientes, en los últimos 90 días
        return SIMULATION_START - timedelta(days=random.randint(1, 90))

    # El resto se registró en los 2 años previos al inicio
    days_back = random.randint(90, 730)
    return SIMULATION_START - timedelta(days=days_back)


def _choose_preferred_categories(n: int = 3) -> list[tuple[uuid.UUID, Decimal]]:
    """Elige n categorías preferidas (con pesos)."""
    # Se llena en el seed con las categorías reales
    return []


# =============================================================================
# SEED
# =============================================================================


def seed_customers(db: Session) -> int:
    """Crea los 10,000 clientes si no existen. Devuelve total creado."""
    existing_count = db.scalar(select(func.count()).select_from(Customer)) or 0
    if existing_count > 0:
        print(f"  Customers:   {existing_count} already exist, skipping")
        return 0

    # Cargar estados y categorías
    states = {s.code: s for s in db.scalars(select(State)).all()}
    categories = db.scalars(select(Category).order_by(Category.code)).all()
    if not states:
        raise RuntimeError("No hay estados. Corre el seed de geografía primero.")
    if not categories:
        raise RuntimeError("No hay categorías. Corre el seed de catálogo primero.")

    faker = Faker("es_MX")
    faker.seed_instance(42)

    # Normalizar distribución de estados
    state_codes = list(STATE_DISTRIBUTION.keys())
    state_weights = list(STATE_DISTRIBUTION.values())

    created = 0
    for i in range(1, TOTAL_CUSTOMERS + 1):
        # Estado
        state_code = random.choices(state_codes, weights=state_weights, k=1)[0]
        state = states[state_code]

        # Perfil
        profile = _weighted_choice(PROFILE_DISTRIBUTION)

        # Género
        gender = _weighted_choice(GENDER_DISTRIBUTION)

        # Segmento preferido según género
        preferred_segment = _choose_segment(gender)

        # Edad coherente con el segmento
        age = _choose_age_segment(preferred_segment)
        birth_date = SIMULATION_START - timedelta(days=age * 365 + random.randint(0, 364))

        # Fechas
        signup_date = _choose_signup_date(profile)
        first_order_date = None
        last_order_date = None
        total_orders = 0
        total_revenue = Decimal("0")
        total_units = 0

        # Coherencia por perfil
        if profile == CustomerProfile.NEW:
            pass  # sin órdenes
        elif profile == CustomerProfile.ONE_TIME:
            first_order_date = signup_date + timedelta(days=random.randint(1, 30))
            last_order_date = first_order_date
            total_orders = 1
            total_units = random.randint(1, 2)
            total_revenue = Decimal(str(round(random.uniform(300, 800), 2)))
        elif profile == CustomerProfile.OCCASIONAL:
            first_order_date = signup_date + timedelta(days=random.randint(1, 30))
            total_orders = random.randint(2, 3)
            last_order_date = min(
                first_order_date + timedelta(days=random.randint(30, 60) * total_orders),
                SIMULATION_START - timedelta(days=1),
            )
            total_units = total_orders * 2
            total_revenue = Decimal(str(round(random.uniform(600, 1200), 2)))
        elif profile == CustomerProfile.REGULAR:
            first_order_date = signup_date + timedelta(days=random.randint(1, 30))
            total_orders = random.randint(4, 9)
            last_order_date = min(
                first_order_date + timedelta(days=random.randint(30, 60) * total_orders),
                SIMULATION_START - timedelta(days=1),
            )
            total_units = total_orders * 2
            total_revenue = Decimal(str(round(random.uniform(1500, 3500), 2)))
        elif profile == CustomerProfile.LOYAL:
            first_order_date = signup_date + timedelta(days=random.randint(1, 15))
            total_orders = random.randint(10, 25)
            last_order_date = min(
                first_order_date + timedelta(days=random.randint(15, 30) * total_orders),
                SIMULATION_START - timedelta(days=1),
            )
            total_units = total_orders * 3
            total_revenue = Decimal(str(round(random.uniform(5000, 12000), 2)))
        elif profile == CustomerProfile.INACTIVE:
            first_order_date = signup_date + timedelta(days=random.randint(1, 30))
            total_orders = random.randint(1, 8)
            last_order_date = SIMULATION_START - timedelta(days=random.randint(200, 500))
            total_units = total_orders * 2
            total_revenue = Decimal(str(round(random.uniform(500, 2000), 2)))

        # Asegurar coherencia de fechas
        if last_order_date and last_order_date < first_order_date:
            last_order_date = first_order_date

        # Construir cliente
        customer = Customer(
            id=uuid.uuid4(),
            customer_code=f"CUST-{i:06d}",
            first_name=faker.first_name(),
            last_name=faker.last_name(),
            email=f"customer{i:06d}@example.com",
            phone=f"+52{random.randint(1000000000, 9999999999)}",
            birth_date=birth_date,
            gender=gender,
            state_id=state.id,
            city=random.choice(CITIES_BY_STATE[state_code]),
            postal_code=f"{random.randint(1000, 99999):05d}",
            profile=profile,
            channel_preference=_choose_channel(state.online_penetration),
            preferred_segment=preferred_segment,
            price_sensitivity=_choose_price_sensitivity(state.income_index),
            signup_date=signup_date,
            first_order_date=first_order_date,
            last_order_date=last_order_date,
            total_orders=total_orders,
            total_revenue=total_revenue,
            total_units=total_units,
            status=RecordStatus.ACTIVE,
        )
        db.add(customer)

        # 2–3 preferencias de categoría
        n_prefs = random.randint(2, 3)
        cat_choices = random.sample(list(categories), k=n_prefs)
        for cat in cat_choices:
            pref = CustomerCategoryPreference(
                id=uuid.uuid4(),
                customer_id=customer.id,
                category_id=cat.id,
                preference_weight=Decimal(str(round(random.uniform(0.8, 1.5), 4))),
            )
            db.add(pref)

        created += 1

        if created % 1000 == 0:
            print(f"  ... {created} customers")

    db.flush()
    return created


def run() -> None:
    """Entry point del seed de clientes."""
    print("Seeding customers...")

    with SessionLocal() as db:
        created = seed_customers(db)
        print(f"  Customers:   {created} new")
        db.commit()

    print("Customers seed done.")


if __name__ == "__main__":
    run()