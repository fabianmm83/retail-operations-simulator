"""Motor de eventos de simulación.

Responsabilidades:

1. Definir el catálogo de eventos: scheduled, random y cascadas.
2. Decidir qué eventos ocurren en un día (scheduled + random).
3. Calcular el `event_factor` que aplica a cada producto/estado en un día.
4. Gestionar cascadas hasta 2 niveles de profundidad.

Este módulo NO escribe a la DB. El engine (engine.py) se encarga de
persistir los eventos detectados como filas en simulation_events.

Tablas internas:

- SCHEDULED_EVENTS : calendario estático de eventos predecibles
- RANDOM_EVENTS    : probabilidad diaria + cooldown + rango de impacto
- CASCADE_RULES    : evento A dispara evento B con probabilidad X
- SCOPE_RESOLUTION : cómo aplicar un evento a un producto concreto
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date

from app.core.enums import (
    SimulationEventScope,
    SimulationEventTrigger,
    SimulationEventType,
)


# =============================================================================
# STRUCTS
# =============================================================================


@dataclass
class EventSpec:
    """Especificación de un evento detectado en un día.

    No incluye scope ni factor resuelto. Eso se calcula después en
    el motor de demanda.
    """

    event_type: SimulationEventType
    trigger: SimulationEventTrigger
    start_date: date
    end_date: date
    scope_type: SimulationEventScope
    scope_value: str | None
    impact_factor: float
    metadata: dict = field(default_factory=dict)


@dataclass
class RandomEventConfig:
    """Configuración de un evento aleatorio."""

    event_type: SimulationEventType
    probability: float              # probabilidad diaria
    cooldown_days: int              # días mínimos entre ocurrencias
    duration_min: int               # duración mínima en días
    duration_max: int               # duración máxima en días
    factor_min: float               # factor de impacto mínimo
    factor_max: float               # factor de impacto máximo
    scope_type: SimulationEventScope
    scope_pool: list[str]           # valores posibles del scope


# =============================================================================
# EVENTOS SCHEDULED (calendario estático)
# =============================================================================
# Formato: (event_type, mes, día, duration_days, factor_min, factor_max)
# Si día == 0, significa "se calcula por regla especial" (ej. 3er viernes).

SCHEDULED_EVENTS: list[tuple[SimulationEventType, int, int, int, float, float]] = [
    # BLACK_FRIDAY → 24 de noviembre (aprox), 1 día, factor ×2.5–3.5
    (SimulationEventType.BLACK_FRIDAY, 11, 24, 1, 2.5, 3.5),
    # BUEN_FIN → 3er viernes de noviembre (aprox), 4 días, factor ×2.0–3.0
    (SimulationEventType.BUEN_FIN, 11, 15, 4, 2.0, 3.0),
    # HOT_SALE → mediados de mayo, 5 días, factor ×1.8–2.5
    (SimulationEventType.HOT_SALE, 5, 15, 5, 1.8, 2.5),
]


# =============================================================================
# EVENTOS RANDOM (probabilidad diaria + cooldown)
# =============================================================================
# IMPORTANTE: las probabilidades están calibradas para dar ~50–70 eventos/año
# si el motor corre 365 días en BASELINE.

RANDOM_EVENTS: list[RandomEventConfig] = [
    # --- Comerciales (demanda) --------------------------------------------
    RandomEventConfig(
        event_type=SimulationEventType.HIGH_DEMAND,
        probability=1.0 / 30.0,          # ~12/año
        cooldown_days=5,
        duration_min=3,
        duration_max=7,
        factor_min=1.5,
        factor_max=2.5,
        scope_type=SimulationEventScope.CATEGORY,
        scope_pool=[
            "PLAYERAS", "SUDADERAS", "TENIS", "SHORTS",
            "LEGGINGS", "PANTS", "CALCETINES",
        ],
    ),
    RandomEventConfig(
        event_type=SimulationEventType.DEMAND_DROP,
        probability=1.0 / 90.0,          # ~4/año
        cooldown_days=20,
        duration_min=7,
        duration_max=14,
        factor_min=0.4,
        factor_max=0.7,
        scope_type=SimulationEventScope.GLOBAL,
        scope_pool=[],
    ),
    RandomEventConfig(
        event_type=SimulationEventType.PROMOTION,
        probability=1.0 / 60.0,          # ~6/año
        cooldown_days=10,
        duration_min=3,
        duration_max=7,
        factor_min=1.5,
        factor_max=2.2,
        scope_type=SimulationEventScope.CATEGORY,
        scope_pool=[
            "PLAYERAS", "SUDADERAS", "TENIS", "SHORTS",
            "MOCHILAS", "BOTELLAS", "CALCETINES",
        ],
    ),

    # --- De oferta (proveedores + CEDIS) ----------------------------------
    RandomEventConfig(
        event_type=SimulationEventType.SUPPLIER_DELAY,
        probability=1.0 / 60.0,          # ~6/año
        cooldown_days=14,
        duration_min=7,
        duration_max=14,
        factor_min=1.3,
        factor_max=1.6,                  # impacto sobre lead time
        scope_type=SimulationEventScope.SUPPLIER,
        scope_pool=[
            "SUP-N01", "SUP-N02", "SUP-N03",
            "SUP-M01", "SUP-M02", "SUP-M03",
            "SUP-I01", "SUP-I02",
        ],
    ),
    RandomEventConfig(
        event_type=SimulationEventType.SUPPLIER_OUTAGE,
        probability=1.0 / 200.0,         # ~2/año
        cooldown_days=30,
        duration_min=7,
        duration_max=21,
        factor_min=0.0,
        factor_max=0.0,                  # cancela POs
        scope_type=SimulationEventScope.SUPPLIER,
        scope_pool=["SUP-N01", "SUP-N02", "SUP-N03", "SUP-I01", "SUP-I02"],
    ),
    RandomEventConfig(
        event_type=SimulationEventType.WAREHOUSE_DELAY,
        probability=1.0 / 90.0,          # ~4/año
        cooldown_days=14,
        duration_min=3,
        duration_max=7,
        factor_min=1.3,
        factor_max=1.7,
        scope_type=SimulationEventScope.WAREHOUSE,
        scope_pool=["CEDIS-CDMX", "CEDIS-NL", "CEDIS-JAL"],
    ),
    RandomEventConfig(
        event_type=SimulationEventType.WAREHOUSE_OVERLOAD,
        probability=1.0 / 120.0,         # ~3/año
        cooldown_days=21,
        duration_min=5,
        duration_max=10,
        factor_min=1.2,
        factor_max=1.5,
        scope_type=SimulationEventScope.WAREHOUSE,
        scope_pool=["CEDIS-CDMX", "CEDIS-NL", "CEDIS-JAL"],
    ),

    # --- Logísticos (carriers) --------------------------------------------
    RandomEventConfig(
        event_type=SimulationEventType.CARRIER_DELAY,
        probability=1.0 / 45.0,          # ~8/año
        cooldown_days=10,
        duration_min=3,
        duration_max=10,
        factor_min=1.5,
        factor_max=2.5,                  # impacto sobre lead time
        scope_type=SimulationEventScope.CARRIER,
        scope_pool=["CAR-01", "CAR-02", "CAR-03", "CAR-04", "CAR-05"],
    ),

    # --- Operativos --------------------------------------------------------
    RandomEventConfig(
        event_type=SimulationEventType.PRODUCT_RETURN,
        probability=1.0 / 60.0,          # ~6/año
        cooldown_days=14,
        duration_min=5,
        duration_max=10,
        factor_min=1.5,
        factor_max=2.5,                  # multiplica la tasa de returns
        scope_type=SimulationEventScope.CATEGORY,
        scope_pool=["PLAYERAS", "TENIS", "SUDADERAS"],
    ),
    RandomEventConfig(
        event_type=SimulationEventType.PAYMENT_FAILURE,
        probability=1.0 / 120.0,         # ~3/año
        cooldown_days=21,
        duration_min=1,
        duration_max=3,
        factor_min=1.5,
        factor_max=2.5,                  # multiplica la tasa de cancelación
        scope_type=SimulationEventScope.GLOBAL,
        scope_pool=[],
    ),
    RandomEventConfig(
        event_type=SimulationEventType.ORDER_CANCELLATION,
        probability=1.0 / 120.0,         # ~3/año
        cooldown_days=21,
        duration_min=1,
        duration_max=3,
        factor_min=1.5,
        factor_max=2.5,
        scope_type=SimulationEventScope.GLOBAL,
        scope_pool=[],
    ),
]


# =============================================================================
# CASCADAS (evento A puede disparar evento B)
# =============================================================================
# Formato: (evento_origen, evento_cascada, probabilidad, nivel_max)
# Solo permitimos 2 niveles: 0 → 1 → 2. Nada más profundo.

CASCADE_RULES: list[
    tuple[SimulationEventType, SimulationEventType, float]
] = [
    # SUPPLIER_DELAY puede generar STOCKOUT si se prolonga
    (SimulationEventType.SUPPLIER_DELAY, SimulationEventType.STOCKOUT, 0.30),
    # SUPPLIER_OUTAGE puede generar STOCKOUT
    (SimulationEventType.SUPPLIER_OUTAGE, SimulationEventType.STOCKOUT, 0.60),
    # HIGH_DEMAND puede sobrecargar el CEDIS
    (SimulationEventType.HIGH_DEMAND, SimulationEventType.WAREHOUSE_OVERLOAD, 0.20),
    # CARRIER_DELAY puede disparar PRODUCT_RETURN (por "llegó tarde")
    (SimulationEventType.CARRIER_DELAY, SimulationEventType.PRODUCT_RETURN, 0.25),
    # WAREHOUSE_OVERLOAD puede disparar CARRIER_DELAY secundario
    (SimulationEventType.WAREHOUSE_OVERLOAD, SimulationEventType.CARRIER_DELAY, 0.15),
    # STOCKOUT (nivel 1) puede disparar ORDER_CANCELLATION (nivel 2)
    (SimulationEventType.STOCKOUT, SimulationEventType.ORDER_CANCELLATION, 0.40),
    # BLACK_FRIDAY puede sobrecargar el CEDIS
    (SimulationEventType.BLACK_FRIDAY, SimulationEventType.WAREHOUSE_OVERLOAD, 0.35),
    # BUEN_FIN puede sobrecargar el CEDIS
    (SimulationEventType.BUEN_FIN, SimulationEventType.WAREHOUSE_OVERLOAD, 0.25),
]


# =============================================================================
# HELPERS INTERNOS
# =============================================================================


def _is_scheduled_event_active(
    event_spec: tuple,
    sim_date: date,
) -> bool:
    """Determina si un evento scheduled cae hoy (o está en su rango)."""
    _, month, day, duration, _, _ = event_spec

    # El evento empieza en (month, day) de algún año. Asumimos mismo año que sim_date.
    try:
        start = date(sim_date.year, month, day)
    except ValueError:
        # Fecha inválida (ej. 30 feb). No ocurre.
        return False

    end = start + _timedelta_days(duration - 1)
    return start <= sim_date <= end


def _timedelta_days(days: int):
    """Wrapper para evitar import directo de timedelta en firmas."""
    from datetime import timedelta
    return timedelta(days=days)


# =============================================================================
# DETECCIÓN DE EVENTOS DEL DÍA
# =============================================================================


def detect_scheduled_events(
    sim_date: date,
    rng: random.Random,
) -> list[EventSpec]:
    """Detecta eventos scheduled activos en la fecha dada.

    Los eventos scheduled tienen scope GLOBAL (aplican a todo el catálogo).
    """
    detected: list[EventSpec] = []

    for spec in SCHEDULED_EVENTS:
        event_type, month, day, duration, factor_min, factor_max = spec

        if not _is_scheduled_event_active(spec, sim_date):
            continue

        try:
            start = date(sim_date.year, month, day)
        except ValueError:
            continue

        end = start + _timedelta_days(duration - 1)
        factor = rng.uniform(factor_min, factor_max)

        detected.append(
            EventSpec(
                event_type=event_type,
                trigger=SimulationEventTrigger.SCHEDULED,
                start_date=start,
                end_date=end,
                scope_type=SimulationEventScope.GLOBAL,
                scope_value=None,
                impact_factor=factor,
                metadata={"scheduled": True},
            )
        )

    return detected


def detect_random_events(
    sim_date: date,
    day_number: int,
    rng: random.Random,
    last_occurrence: dict[SimulationEventType, int],
) -> list[EventSpec]:
    """Detecta eventos random que ocurren hoy.

    Args:
        sim_date: fecha simulada actual.
        day_number: número de día desde el inicio del run.
        rng: RNG del subsistema de eventos para el día.
        last_occurrence: dict {event_type: day_number} con el último día
                         en que ocurrió cada tipo. Sirve para el cooldown.

    Returns:
        Lista de eventos detectados. Actualiza `last_occurrence` in-place.
    """
    detected: list[EventSpec] = []

    for config in RANDOM_EVENTS:
        # Cooldown
        last = last_occurrence.get(config.event_type, -9999)
        if (day_number - last) < config.cooldown_days:
            continue

        # Probabilidad
        if rng.random() >= config.probability:
            continue

        # Duración
        duration = rng.randint(config.duration_min, config.duration_max)
        end = sim_date + _timedelta_days(duration - 1)

        # Factor
        if config.factor_min == config.factor_max:
            factor = config.factor_min
        else:
            factor = rng.uniform(config.factor_min, config.factor_max)

        # Scope
        if config.scope_type == SimulationEventScope.GLOBAL:
            scope_value = None
        else:
            scope_value = rng.choice(config.scope_pool)

        detected.append(
            EventSpec(
                event_type=config.event_type,
                trigger=SimulationEventTrigger.RANDOM,
                start_date=sim_date,
                end_date=end,
                scope_type=config.scope_type,
                scope_value=scope_value,
                impact_factor=factor,
                metadata={"cooldown_days": config.cooldown_days},
            )
        )

        last_occurrence[config.event_type] = day_number

    return detected


def resolve_cascades(
    parent: EventSpec,
    sim_date: date,
    rng: random.Random,
) -> list[EventSpec]:
    """Genera eventos cascada a partir de un evento padre.

    Reglas:
    - Solo se generan cascadas directas (1 nivel).
    - El motor llama a esta función una sola vez por evento padre.
      Si una cascada genera otra cascada, esa se resuelve en el
      siguiente tick (day), no en el mismo.
    - El factor de la cascada es fijo (no aleatorio) salvo que la
      regla lo indique.
    """
    cascades: list[EventSpec] = []

    for parent_type, cascade_type, prob in CASCADE_RULES:
        if parent.event_type != parent_type:
            continue

        if rng.random() >= prob:
            continue

        # Hereda scope del padre; duración corta (3–7 días)
        duration = rng.randint(3, 7)
        end = sim_date + _timedelta_days(duration - 1)

        cascades.append(
            EventSpec(
                event_type=cascade_type,
                trigger=SimulationEventTrigger.CASCADE,
                start_date=sim_date,
                end_date=end,
                scope_type=parent.scope_type,
                scope_value=parent.scope_value,
                impact_factor=1.0,  # las cascadas no multiplican demanda per se
                metadata={"parent_event_type": parent.event_type.value},
            )
        )

    return cascades


# =============================================================================
# CÁLCULO DEL FACTOR APLICABLE
# =============================================================================


def event_factor_for(
    active_events: list[EventSpec],
    *,
    product_category_code: str | None = None,
    state_code: str | None = None,
    supplier_code: str | None = None,
    carrier_code: str | None = None,
    warehouse_code: str | None = None,
) -> float:
    """Calcula el `event_factor` que aplica a un producto/estado/... dado.

    Solo los eventos que matchean el scope del target cuentan. Los
    eventos de tipo logístico/operativo no aplican a demanda, pero
    se pueden aplicar a otros cálculos (fulfillment, procurement) —
    para eso se usan los mismos eventos, pasando el contexto adecuado.

    Returns:
        Un multiplicador. Si no hay eventos que apliquen, devuelve 1.0.
        Si hay varios, se multiplican entre sí.
    """
    factor = 1.0

    for ev in active_events:
        # Eventos no comerciales no afectan demanda directamente
        if ev.event_type in _NON_DEMAND_EVENTS:
            continue

        if ev.scope_type == SimulationEventScope.GLOBAL:
            factor *= ev.impact_factor
        elif (
            ev.scope_type == SimulationEventScope.CATEGORY
            and product_category_code == ev.scope_value
        ):
            factor *= ev.impact_factor
        elif (
            ev.scope_type == SimulationEventScope.PRODUCT
            and product_category_code == ev.scope_value
        ):
            factor *= ev.impact_factor
        elif (
            ev.scope_type == SimulationEventScope.STATE
            and state_code == ev.scope_value
        ):
            factor *= ev.impact_factor
        # SUPPLIER, CARRIER, WAREHOUSE no aplican a demanda
        # (se usan en fulfillment/procurement)

    return factor


def supplier_event_factor(
    active_events: list[EventSpec],
    supplier_code: str,
) -> float:
    """Impacto de eventos de oferta sobre un proveedor (para lead time)."""
    factor = 1.0
    for ev in active_events:
        if ev.scope_type == SimulationEventScope.SUPPLIER and ev.scope_value == supplier_code:
            if ev.event_type in (
                SimulationEventType.SUPPLIER_DELAY,
                SimulationEventType.SUPPLIER_OUTAGE,
            ):
                if ev.event_type == SimulationEventType.SUPPLIER_OUTAGE:
                    factor = 0.0  # cancela POs
                else:
                    factor *= ev.impact_factor
    return factor


def carrier_event_factor(
    active_events: list[EventSpec],
    carrier_code: str,
) -> float:
    """Impacto de eventos logísticos sobre un carrier (para lead time)."""
    factor = 1.0
    for ev in active_events:
        if ev.scope_type == SimulationEventScope.CARRIER and ev.scope_value == carrier_code:
            if ev.event_type == SimulationEventType.CARRIER_DELAY:
                factor *= ev.impact_factor
    return factor


# =============================================================================
# CONSTANTES INTERNAS
# =============================================================================


_NON_DEMAND_EVENTS = frozenset({
    SimulationEventType.SUPPLIER_DELAY,
    SimulationEventType.SUPPLIER_OUTAGE,
    SimulationEventType.WAREHOUSE_DELAY,
    SimulationEventType.WAREHOUSE_OVERLOAD,
    SimulationEventType.CARRIER_DELAY,
    SimulationEventType.LOST_SHIPMENT,
    SimulationEventType.STOCKOUT,
    SimulationEventType.PAYMENT_FAILURE,
    SimulationEventType.ORDER_CANCELLATION,
    SimulationEventType.PRICE_CHANGE,
})