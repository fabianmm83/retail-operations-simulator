"""Motor de demanda diaria.

Implementa la fórmula maestra del Bloque G:

    demanda_diaria[producto, estado] =
        base_perfil
      × multiplicador_segmento
      × regional_factor
      × afinidad_categoria
      × temporal_factor
      × lifecycle_factor
      × growth_factor
      × event_factor
      × variación_aleatoria

El resultado es la demanda esperada de UN producto en UN estado en UN día.

NOTA: Este módulo NO genera órdenes. Devuelve un número (unidades/día).
La traducción a órdenes concretas ocurre en fulfillment.py.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.core.enums import (
    DemandProfileType,
    LifecycleStageType,
    SeasonalityType,
    SegmentType,
)


# =============================================================================
# CONSTANTES DE LA FÓRMULA
# =============================================================================


# Unidades/día base por perfil de demanda (a nivel empresa, antes de factores).
DEMAND_BASE: dict[DemandProfileType, tuple[float, float]] = {
    DemandProfileType.HIGH:   (40.0,  80.0),
    DemandProfileType.MEDIUM: (12.0,  25.0),
    DemandProfileType.LOW:    ( 4.0,  10.0),
    DemandProfileType.NICHE:  ( 1.0,   3.0),
}

# Multiplicador por segmento.
SEGMENT_MULTIPLIER: dict[SegmentType, float] = {
    SegmentType.WOMEN:  1.20,
    SegmentType.MEN:    1.00,
    SegmentType.KIDS:   0.60,
    SegmentType.UNISEX: 0.40,
}

# Factor por etapa de lifecycle.
LIFECYCLE_FACTOR: dict[LifecycleStageType, float] = {
    LifecycleStageType.LAUNCH:       0.40,
    LifecycleStageType.GROWTH:       1.20,
    LifecycleStageType.MATURE:       1.00,
    LifecycleStageType.DECLINE:      0.50,
    LifecycleStageType.DISCONTINUED: 0.00,
}

# Factores mensuales por patrón estacional.
# Índice: 1 = enero, 12 = diciembre.
TEMPORAL_FACTOR: dict[SeasonalityType, dict[int, float]] = {
    SeasonalityType.NONE: {
        1: 1.00, 2: 1.00, 3: 1.00, 4: 1.00, 5: 1.00, 6: 1.00,
        7: 1.00, 8: 1.00, 9: 1.00, 10: 1.00, 11: 1.00, 12: 1.00,
    },
    SeasonalityType.WINTER: {
        1: 1.30, 2: 1.10, 3: 0.90, 4: 0.70, 5: 0.50, 6: 0.40,
        7: 0.40, 8: 0.50, 9: 0.80, 10: 1.20, 11: 1.60, 12: 1.80,
    },
    SeasonalityType.NEW_YEAR: {
        1: 1.80, 2: 1.50, 3: 1.30, 4: 1.10, 5: 1.00, 6: 0.90,
        7: 0.80, 8: 0.80, 9: 0.80, 10: 0.90, 11: 0.90, 12: 1.00,
    },
    SeasonalityType.SUMMER: {
        1: 0.60, 2: 0.65, 3: 0.80, 4: 1.00, 5: 1.30, 6: 1.50,
        7: 1.60, 8: 1.50, 9: 1.10, 10: 0.85, 11: 0.70, 12: 0.60,
    },
}

# Variación aleatoria diaria (±15%).
RANDOM_JITTER_PCT = 0.15


# =============================================================================
# ESTRUCTURAS
# =============================================================================


@dataclass(frozen=True)
class DemandInputs:
    """Todos los factores necesarios para calcular la demanda de
    un producto en un estado un día dado.

    Se pasan ya resueltos para que `compute_demand` sea una función pura
    (sin queries a la DB, sin RNG global). Eso la hace fácil de testear.
    """

    demand_profile: DemandProfileType
    segment: SegmentType
    lifecycle_stage: LifecycleStageType
    seasonality: SeasonalityType
    regional_factor: float
    affinity_factor: float
    growth_rate: float
    day_number: int
    event_factor: float


# =============================================================================
# HELPERS
# =============================================================================


def _base_for_profile(profile: DemandProfileType) -> float:
    """Devuelve el punto medio del rango base del perfil de demanda."""
    low, high = DEMAND_BASE[profile]
    return (low + high) / 2.0


def _growth_factor(growth_rate: float, day_number: int) -> float:
    """Aplica crecimiento tendencial anual de forma suave.

    growth_factor(día) = (1 + growth_rate) ** (días / 365)

    Ejemplo con growth_rate = 0.05 (5% anual):
        día 0    → 1.000
        día 180  → 1.024
        día 365  → 1.050
    """
    return (1.0 + growth_rate) ** (day_number / 365.0)


def _month_from_day_number(day_number: int) -> int:
    """Convierte day_number (0-indexed) a mes (1–12).

    Asumimos que el día 0 = 1 de enero del primer año.
    Soporta múltiples años (módulo 12).
    """
    return ((day_number // 30) % 12) + 1


# =============================================================================
# FUNCIÓN PRINCIPAL
# =============================================================================


def compute_demand(
    inputs: DemandInputs,
    random_jitter: float,
) -> float:
    """Calcula la demanda diaria esperada para un producto en un estado.

    Args:
        inputs: los 8 factores del sistema.
        random_jitter: variación aleatoria ya generada por el RNG del día
                       (un valor entre -RANDOM_JITTER_PCT y +RANDOM_JITTER_PCT).
                       Se pasa desde afuera para mantener esta función pura
                       y testable.

    Returns:
        Demanda diaria en unidades (float >= 0). Nunca negativa.
    """
    # 1. Base del perfil
    base = _base_for_profile(inputs.demand_profile)

    # 2. Multiplicador de segmento
    segment_mult = SEGMENT_MULTIPLIER[inputs.segment]

    # 3. Factor estacional del mes
    month = _month_from_day_number(inputs.day_number)
    temporal = TEMPORAL_FACTOR[inputs.seasonality][month]

    # 4. Factor de lifecycle
    lifecycle = LIFECYCLE_FACTOR[inputs.lifecycle_stage]

    # 5. Factor de crecimiento
    growth = _growth_factor(inputs.growth_rate, inputs.day_number)

    # 6. Producto completo
    demand = (
        base
        * segment_mult
        * inputs.regional_factor
        * inputs.affinity_factor
        * temporal
        * lifecycle
        * growth
        * inputs.event_factor
        * (1.0 + random_jitter)
    )

    # 7. Nunca negativa
    return max(demand, 0.0)


# =============================================================================
# UTILIDADES
# =============================================================================


def demand_summary(inputs: DemandInputs, random_jitter: float = 0.0) -> dict:
    """Devuelve un dict con todos los factores y el resultado.

    Útil para debugging y para tests.
    """
    base = _base_for_profile(inputs.demand_profile)
    segment_mult = SEGMENT_MULTIPLIER[inputs.segment]
    month = _month_from_day_number(inputs.day_number)
    temporal = TEMPORAL_FACTOR[inputs.seasonality][month]
    lifecycle = LIFECYCLE_FACTOR[inputs.lifecycle_stage]
    growth = _growth_factor(inputs.growth_rate, inputs.day_number)

    result = compute_demand(inputs, random_jitter)

    return {
        "demand_profile": inputs.demand_profile.value,
        "base": base,
        "segment_multiplier": segment_mult,
        "regional_factor": inputs.regional_factor,
        "affinity_factor": inputs.affinity_factor,
        "temporal_factor": temporal,
        "lifecycle_factor": lifecycle,
        "growth_factor": round(growth, 4),
        "event_factor": inputs.event_factor,
        "random_jitter": random_jitter,
        "final_demand": round(result, 2),
    }