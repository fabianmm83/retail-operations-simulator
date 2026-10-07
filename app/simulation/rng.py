"""Sistema de números aleatorios jerárquico y reproducible.

Objetivo: que una simulación con el mismo seed produzca exactamente
los mismos resultados, aunque se cambie el orden de ejecución de
algunos componentes o se reanude desde un checkpoint.

Estrategia:
  - Cada SimulationRun tiene un `seed` maestro (entero).
  - Los sub-sistemas (customers, demand, events, carriers, etc.)
    derivan su propio seed desde el seed maestro + una etiqueta.
  - Cada día de simulación deriva su propio RNG desde el seed del
    sub-sistema + el número de día.
  - Los RNG son instancias de `random.Random` sembradas localmente.
    NO usamos `random.seed()` global, para evitar contaminación
    entre componentes.

Uso típico:

    from app.simulation.rng import make_rng, make_daily_rng

    # RNG para un subsistema
    rng = make_rng(seed=12345, label="demand")

    # RNG para un subsistema en un día específico
    rng = make_daily_rng(seed=12345, label="demand", day_number=15)
"""

from __future__ import annotations

import hashlib
import random


# =============================================================================
# DERIVACIÓN DE SEEDS
# =============================================================================


def derive_seed(master_seed: int, *labels: str | int) -> int:
    """Deriva un seed entero determinista a partir de un seed maestro
    y uno o más labels (strings o enteros).

    El resultado es determinista: mismos argumentos → mismo seed.
    Es estable entre versiones de Python (usa SHA-256, no `hash()`).

    Ejemplo:
        derive_seed(12345, "demand", 15)  → un entero
        derive_seed(12345, "events")      → otro entero distinto
    """
    payload = f"{master_seed}:" + ":".join(str(label) for label in labels)
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    # Tomamos los primeros 8 bytes como entero sin signo.
    # 64 bits de entropía son suficientes para `random.Random`.
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


# =============================================================================
# CREACIÓN DE RNGs
# =============================================================================


def make_rng(master_seed: int, *labels: str | int) -> random.Random:
    """Crea un RNG local determinista a partir del seed maestro y labels.

    Cada componente debe pedir su propio RNG con su propia etiqueta,
    para que el orden de ejecución entre componentes no afecte los
    resultados.
    """
    seed = derive_seed(master_seed, *labels)
    return random.Random(seed)


def make_daily_rng(
    master_seed: int,
    label: str,
    day_number: int,
) -> random.Random:
    """Crea un RNG para un subsistema en un día específico.

    Esto es clave para reproducibilidad: el día N del subsistema X
    siempre usa el mismo RNG, sin importar cuántos días se hayan
    procesado antes en esa corrida.
    """
    return make_rng(master_seed, label, day_number)


# =============================================================================
# HELPERS DE USO COMÚN
# =============================================================================


def weighted_choice(
    rng: random.Random,
    options: list,
    weights: list[float],
):
    """Elige un elemento de `options` con probabilidad proporcional
    a `weights`.

    Wrapper sobre `random.choices` con k=1 para evitar el retorno
    de listas.

    Ejemplo:
        weighted_choice(rng, ["A", "B"], [0.7, 0.3])  → "A" o "B"
    """
    return rng.choices(options, weights=weights, k=1)[0]


def jitter(rng: random.Random, base: float, pct: float) -> float:
    """Aplica una variación aleatoria a `base` de ±`pct` (fracción).

    Ejemplo:
        jitter(rng, 100.0, 0.15)  → un valor entre 85.0 y 115.0
    """
    factor = 1.0 + rng.uniform(-pct, pct)
    return base * factor


def bernoulli(rng: random.Random, probability: float) -> bool:
    """Devuelve True con probabilidad `probability`.

    Wrapper semántico sobre `rng.random() < probability`.
    """
    return rng.random() < probability


# =============================================================================
# VALIDACIÓN DE REPRODUCIBILIDAD
# =============================================================================


def fingerprint_rng(rng: random.Random, draws: int = 5) -> list[float]:
    """Extrae N números del RNG. Útil para verificar reproducibilidad
    en tests: dos RNG con el mismo seed deben producir el mismo fingerprint.

    OJO: consumir el RNG. Solo usar en tests o diagnósticos.
    """
    return [rng.random() for _ in range(draws)]