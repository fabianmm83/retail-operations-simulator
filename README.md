# Cuidado con Rikochet — Retail Operations Simulator

[![Python](https://img.shields.io/badge/python-3.13-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.1-red.svg)](https://www.sqlalchemy.org/)
[![Alembic](https://img.shields.io/badge/Alembic-1.20-orange.svg)](https://alembic.sqlalchemy.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Un **sistema operacional sintético con estado** que simula la operación diaria de una empresa retail ficticia mexicana. No es un CRUD ni un generador de datos aleatorios: es un motor que aplica reglas de negocio, eventos y consecuencias, produciendo datos empresariales coherentes y reproducibles.

---

## Tabla de contenido

- [¿Qué es esto?](#qué-es-esto)
- [Arquitectura del ecosistema](#arquitectura-del-ecosistema)
- [Empresa simulada](#empresa-simulada)
- [Stack técnico](#stack-técnico)
- [Modelo de datos](#modelo-de-datos)
- [Motor de simulación](#motor-de-simulación)
- [API REST](#api-rest)
- [Instalación y uso](#instalación-y-uso)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Reproducibilidad](#reproducibilidad)
- [Próximos pasos](#próximos-pasos)
- [Posicionamiento profesional](#posicionamiento-profesional)
- [Licencia](#licencia)

---

## ¿Qué es esto?

**Cuidado con Rikochet** es un ecosistema de proyectos diseñado para demostrar capacidades de ingeniería de software y de datos en un dominio realista. Está compuesto por dos repositorios:

1. **`retail-operations-simulator`** (este repo) — Simula la operación diaria de la empresa.
2. **`retail-data-platform`** (próximamente) — Consume los datos y construye analítica + dashboards.

El principio central:

```text
ESTADO → REGLAS DE NEGOCIO → DECISIONES → EVENTOS → CONSECUENCIAS → NUEVO ESTADO → DATOS
Los datos no se generan aleatoriamente. Son el resultado natural de la operación simulada.

Arquitectura del ecosistema
text
┌────────────────────────────────────────────────────────────┐
│  retail-operations-simulator                               │
│  Python + FastAPI + PostgreSQL + SQLAlchemy + Alembic      │
│  → Simula la operación diaria                              │
│  → Produce datos operacionales con estado                  │
└──────────────────────┬─────────────────────────────────────┘
                       │
                       │ datos
                       ▼
┌────────────────────────────────────────────────────────────┐
│  retail-data-platform                                      │
│  Ingestion → RAW → Validation → STAGING → Transformation   │
│  → Analytical Model → KPIs → React Dashboard               │
└────────────────────────────────────────────────────────────┘
Empresa simulada
Cuidado con Rikochet es un retailer deportivo mexicano ficticio:

Atributo	Valor
Rubro	Ropa, calzado y accesorios deportivos
Mercado	México
Moneda	MXN
Canal predominante	Online > Tienda física
Cobertura	10 estados
CEDIS	3 (CDMX, NL, JAL)
Tiendas físicas	12
Catálogo	32 productos · 647 SKUs
Clientes iniciales	10,000
Proveedores	8
Carriers	5
Todos los datos son sintéticos. No representan ventas reales de ninguna empresa.

Stack técnico
Categoría	Tecnología
Lenguaje	Python 3.13
Web framework	FastAPI
Servidor ASGI	Uvicorn
ORM	SQLAlchemy 2.1
Migraciones	Alembic 1.20
Base de datos	PostgreSQL 16 (en Docker)
Validación	Pydantic 2.13 + pydantic-settings
Generación de datos	Faker
Cálculos numéricos	NumPy
Testing	pytest + httpx
Linting	Ruff
Contenedores	Docker + Docker Compose
Modelo de datos
El esquema está organizado en 7 dominios funcionales:

Bloque	Dominio	Tablas	Registros seed
M1	Catálogo	3	12 categorías · 32 productos · 647 SKUs
M2	Geografía	3	10 estados · 15 ubicaciones · 120 afinidades
M3	Clientes	2	10,000 clientes · 24,899 preferencias
M4	Inventario	4	2,901 filas de inventario
M5	Proveedores	4	8 proveedores · 84 supplier_products
M6	Ventas + Logística	6	5 carriers
M7	Simulación	3	(runtime)
Total	25 tablas	
Características del modelo
33 enums nativos de PostgreSQL.

UUID v4 generados en Python (portables, sin depender de extensiones de DB).

available_quantity GENERATED (quantity - reserved_quantity) con STORED.

Reglas de negocio codificadas como CHECK constraints.

Sin soft delete — el estado se maneja con enums (RecordStatus).

Auditoría con created_at y updated_at en todas las tablas.

JSONB para configuraciones variables (config_snapshot, metadata_json, snapshot.data).

Migraciones
text
001_create_catalog_tables
002_create_geography_tables
003_create_customers_tables
004_create_inventory_tables
005_create_suppliers_tables
006_create_sales_tables
007_create_simulation_tables
Motor de simulación
El motor ejecuta un ciclo diario de 8 fases sobre el estado persistido.

Las 8 fases
Avance de tiempo — simulation_date += 1.

Eventos del día — scheduled + random + cascadas.

Carry-over — recepción de POs, transfers, entrega de shipments.

Generación de demanda — órdenes para clientes activos.

Procesamiento de órdenes — pago, reserva, movimientos SALE.

Logística — envío de shipments.

Reabastecimiento — evaluación de reorder points, creación de POs y transfers.

Cierre del día — snapshots + commit atómico.

Componentes del motor
Módulo	Responsabilidad
rng.py	RNG determinista con seed jerárquico
demand.py	Fórmula maestra de demanda (8 factores)
events.py	Catálogo de eventos, cooldowns, cascadas
fulfillment.py	Órdenes, productos, SKUs, carriers, shipments
replenishment.py	Reorder points, POs, transfers
engine.py	Ciclo diario y orquestación
__main__.py	CLI runner
Eventos simulados
Comerciales: HIGH_DEMAND, BLACK_FRIDAY, BUEN_FIN, HOT_SALE, SEASONAL_PEAK, DEMAND_DROP, PRODUCT_LAUNCH, PROMOTION.

De oferta: SUPPLIER_DELAY, SUPPLIER_OUTAGE, WAREHOUSE_DELAY, WAREHOUSE_OVERLOAD.

Logísticos: CARRIER_DELAY, LOST_SHIPMENT.

Operativos: STOCKOUT, PRODUCT_RETURN, PAYMENT_FAILURE, ORDER_CANCELLATION, PRICE_CHANGE.

Cascadas
Un evento puede disparar otro. Ejemplo real observado en una corrida:

text
SUPPLIER_DELAY (sobre SUP-I01)
    ↓
STOCKOUT (sobre SUP-I01)
    ↓
ORDER_CANCELLATION
Máximo 2 niveles de profundidad.

API REST
Endpoints read-only documentados automáticamente en /docs.

Grupo	Descripción
health	Health checks del servicio y DB
catalog	Categorías, productos, variantes
geography	Estados, ubicaciones, afinidades
customers	Clientes y preferencias
inventory	Inventario, movimientos, transfers
suppliers	Proveedores, productos, POs
sales	Órdenes, items, shipments, returns, carriers
simulation	Runs, eventos, snapshots
Todos los endpoints son GET. Las escrituras vienen del seed y del motor de simulación.

Instalación y uso
Requisitos
Docker Desktop corriendo

Python 3.13

Git

Setup
bash
# Clonar
git clone https://github.com/fabianmm83/retail-operations-simulator.git
cd retail-operations-simulator

# Crear venv
python -m venv .venv
.venv\Scripts\activate     # Windows
# source .venv/bin/activate  # macOS/Linux

# Instalar dependencias
pip install -e ".[dev]"

# Levantar PostgreSQL
docker compose up -d

# Aplicar migraciones
alembic upgrade head

# Poblar la base de datos (idempotente)
python -m app.seed

# Arrancar la API
uvicorn app.main:app --reload --port 8000
Comandos útiles
bash
# Correr una simulación (baseline, 30 días, seed 12345)
python -m app.simulation --days 30 --seed 12345

# Correr con reset (borra runs previos)
python -m app.simulation --days 30 --seed 12345 --reset

# Correr con escenario
python -m app.simulation --days 90 --seed 42 --scenario HIGH_DEMAND

# Verbose (logs detallados)
python -m app.simulation --days 5 --seed 12345 --verbose

# API docs
http://localhost:8000/docs
Verificación rápida
bash
# Conteos esperados después del seed
categories              12
products                32
product_variants       647
states                  10
locations               15
state_category_affinity 120
customers            10000
customer_category_pref  24899
inventory             2901
inventory_movements   2901
suppliers                8
supplier_products       84
carriers                 5
Estructura del proyecto
text
retail-operations-simulator/
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 90d73468a824_001_create_catalog_tables.py
│       ├── 797d1297f7a7_002_create_geography_tables.py
│       ├── 36f36181cb96_003_create_customers_tables.py
│       ├── 8f0f07879828_004_create_inventory_tables.py
│       ├── b3e3c09db3a4_005_create_suppliers_tables.py
│       ├── a4bf27e873c5_006_create_sales_tables.py
│       └── 58f65b4ae46a_007_create_simulation_tables.py
├── alembic.ini
├── app/
│   ├── main.py
│   ├── api/v1/                    # 8 routers HTTP
│   ├── core/                      # config + enums (33 tipos)
│   ├── db/                        # base, session, mixins
│   ├── models/                    # 7 archivos de modelos SQLAlchemy
│   ├── schemas/                   # 7 archivos de schemas Pydantic
│   ├── seed/                      # 6 seeds idempotentes
│   └── simulation/                # motor de simulación (7 módulos)
│       ├── rng.py
│       ├── demand.py
│       ├── events.py
│       ├── fulfillment.py
│       ├── replenishment.py
│       ├── engine.py
│       └── __main__.py
├── scripts/
│   ├── debug_day1.py              # verificación día 1
│   └── debug_repro.py             # verificación de reproducibilidad
├── tests/
├── .env.example
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── ARCHITECTURE.md
└── README.md
Reproducibilidad
Uno de los principios del proyecto: misma seed + misma configuración → mismos datos exactos.

Cómo se garantiza
Seed jerárquico: cada subsistema (customers, demand, events, carriers) deriva su propio RNG desde el seed maestro + etiqueta.

RNG por día: cada día usa un RNG independiente derivado de (seed, subsistema, day_number).

ORDER BY explícito: todas las queries iteradas por el motor tienen orden determinista.

Motor sin estado mutable: el motor NO modifica el estado base (clientes, productos) durante la simulación.

Cómo verificarlo
bash
# Corre 5 días dos veces con el mismo seed
python -m app.simulation --days 5 --seed 12345 --reset
python -m app.simulation --days 5 --seed 12345 --reset
Ambas corridas deben producir exactamente:

text
Órdenes:    XXXX
Shipments:  XXXX
Eventos:    XX
Snapshots:  5
Revenue:    $X,XXX,XXX.XX
Próximos pasos
□ Tests automatizados con pytest (reproducibilidad, integridad referencial, constraints).
□ Integración completa de la fórmula de demanda con la generación de órdenes.
□ Implementación completa de returns (crear → aprobar → recibir → reembolsar).
□ Backorders formales cuando no hay stock suficiente.
□ Optimización de rendimiento del motor (batches de INSERT).
□ retail-data-platform: pipeline de datos con ingestion, RAW, validation, STAGING, transformation, KPIs y dashboard React.
□ Airflow para orquestación (V2).
□ dbt para transformaciones versionadas (V3).
□ Cloud deployment (V4).
Posicionamiento profesional
Este proyecto complementa un perfil orientado a:

Backend Engineering

Full Stack

Data Engineering

Cloud

Software Engineering

El valor no está en "hice una tienda". Está en:

Diseñé y construí un sistema operacional sintético con estado, reglas de negocio, persistencia relacional, simulación de eventos y generación de datos; posteriormente construí un pipeline de Data Engineering para transformar esos datos en un modelo analítico y KPIs.

Licencia
MIT. Ver LICENSE para detalles.

Contacto
GitHub: @fabianmm83