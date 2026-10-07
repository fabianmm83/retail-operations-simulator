# Arquitectura — Retail Operations Simulator

Documento técnico sobre las decisiones de diseño del sistema.

---

## Tabla de contenido

1. [Visión general](#visión-general)
2. [Filosofía de diseño](#filosofía-de-diseño)
3. [Modelo de datos](#modelo-de-datos)
4. [Motor de simulación](#motor-de-simulación)
5. [Sistema de reproducibilidad](#sistema-de-reproducibilidad)
6. [Sistema de eventos](#sistema-de-eventos)
7. [Fórmula de demanda](#fórmula-de-demanda)
8. [Fulfillment y logística](#fulfillment-y-logística)
9. [Reabastecimiento](#reabastecimiento)
10. [Decisiones técnicas](#decisiones-técnicas)
11. [Limitaciones de V1](#limitaciones-de-v1)
12. [Roadmap](#roadmap)

---

## Visión general

El proyecto implementa un **sistema operacional sintético**. Su objetivo es producir datos empresariales que sean el resultado natural de operaciones simuladas, no de generación aleatoria.

```text
ESTADO
  ↓
REGLAS DE NEGOCIO
  ↓
DECISIONES
  ↓
EVENTOS
  ↓
CONSECUENCIAS
  ↓
NUEVO ESTADO
  ↓
DATOS
Cada dato tiene una causa trazable. Cada cambio de estado deja un registro. Cada operación tiene consecuencias.

Filosofía de diseño
Principio 1 — Los datos son el resultado, no el objetivo
No se generan 100,000 registros aleatorios. Se simula una operación día a día que produce esos registros.

Principio 2 — Estado persistente
El sistema conserva estado entre días. Un día no reinicia el mundo.

Principio 3 — Trazabilidad total
Todo cambio de inventario tiene un movimiento asociado. Toda orden tiene un shipment (si es online). Todo reorder tiene una PO.

Principio 4 — Reproducibilidad estricta
Misma seed + misma configuración → mismos datos exactos. Esto permite:

Debugging de escenarios específicos.

Comparación de escenarios con mismo seed.

Tests automatizados que verifican comportamiento.

Principio 5 — Transaccionalidad
Cada día simulado es una transacción atómica. Si falla a la mitad, se hace rollback completo y el run queda en estado FAILED.

Principio 6 — Reglas en la base de datos
Los invariantes importantes se codifican como constraints SQL (CHECK, UNIQUE, FOREIGN KEY). La DB no permite estados inválidos.

Modelo de datos
Jerarquía
text
CATÁLOGO (M1)
  Category 1─N Product 1─N ProductVariant

GEOGRAFÍA (M2)
  State 1─N Location
  State N─M Category (vía StateCategoryAffinity)

CLIENTES (M3)
  Customer N─1 State
  Customer 1─N CustomerCategoryPreference

INVENTARIO (M4)
  Inventory N─1 ProductVariant
  Inventory N─1 Location
  InventoryMovement N─1 ProductVariant
  InventoryMovement N─1 Location
  Transfer N─1 Location (origin)
  Transfer N─1 Location (destination)
  TransferItem N─1 Transfer
  TransferItem N─1 ProductVariant

PROVEEDORES (M5)
  Supplier N─1 State
  Supplier 1─N SupplierProduct
  SupplierProduct N─1 Product
  PurchaseOrder N─1 Supplier
  PurchaseOrder N─1 Location
  PurchaseOrderItem N─1 PurchaseOrder
  PurchaseOrderItem N─1 Product

VENTAS + LOGÍSTICA (M6)
  Carrier 1─N Shipment
  Customer 1─N Order
  Order N─1 State
  Order N─1 Location
  Order 1─N OrderItem
  Order 1─N Shipment
  Order 1─N Return
  OrderItem N─1 ProductVariant
  Return 1─N ReturnItem
  ReturnItem N─1 OrderItem

SIMULACIÓN (M7)
  SimulationRun 1─N SimulationEvent
  SimulationRun 1─N SimulationSnapshot
  SimulationEvent N─1 SimulationEvent (parent, cascadas)
Decisiones de diseño
UUID v4 generado en Python (no en DB): portable, sin depender de pgcrypto, control total.

Enums nativos de PostgreSQL: type-safe, eficientes, con CHECK implícito.

available_quantity GENERATED: (quantity - reserved_quantity) STORED. Nunca se desincroniza.

Sin soft delete: se usa el enum RecordStatus (ACTIVE / INACTIVE).

created_at + updated_at en todas las tablas: auditoría.

NUMERIC(10,2) para dinero: precisión decimal exacta.

JSONB para campos variables: config_snapshot, metadata_json, snapshot.data.

Motor de simulación
Ciclo diario
Cada día simulado se ejecuta en 8 fases ordenadas. El orden importa.

text
FASE 1 — Avance de tiempo
    simulation_date += 1

FASE 2 — Eventos del día
    - Detectar eventos scheduled (Black Friday, etc.)
    - Detectar eventos random (con cooldown)
    - Resolver cascadas de eventos del día
    - Persistir como SimulationEvent
    - Cargar todos los eventos activos hoy

FASE 3 — Carry-over
    - POs: PENDING → CONFIRMED → IN_TRANSIT → RECEIVED
    - Transfers: PENDING → IN_TRANSIT → RECEIVED
    - Shipments: PACKED → SHIPPED → IN_TRANSIT → DELIVERED
    - Aplicar retrasos por confiabilidad

FASE 4 — Generación de demanda
    - Iterar clientes activos
    - Calcular probabilidad de compra del día
    - Construir orden (productos, SKUs, carrier, shipment)

FASE 5 — Procesamiento de órdenes
    - Verificar pago (5% falla)
    - Reservar stock
    - Registrar movimiento SALE
    - STORE: entrega inmediata

FASE 6 — Logística
    - Avanzar shipments del día a SHIPPED

FASE 7 — Reabastecimiento
    - Evaluar reorder point por (SKU, CEDIS)
    - Crear Purchase Orders agrupadas por proveedor
    - Evaluar reorder point por (SKU, tienda)
    - Crear Transfers desde CEDIS de la región

FASE 8 — Cierre del día
    - Snapshot si corresponde (día 1–30 / cada 7 / cada 30)
    - Actualizar run.last_tick_at
    - Commit atómico
Justificación del orden
Fase	Por qué en ese lugar
Eventos primero	Afectan todo el día: demanda, logística, POs
Carry-over antes de demanda	El stock que llegó hoy debe estar disponible para vender
Demanda antes de procesar	Todas las órdenes del día se procesan juntas
Procesamiento antes de logística	Los shipments se generan a partir de órdenes confirmadas
Logística antes de reabastecimiento	Primero vemos qué se consumió, luego reponemos
Cierre al final	Refleja el estado consolidado del día
Sistema de reproducibilidad
El problema
Un motor con estado es fácilmente no-determinista por:

Orden de queries sin ORDER BY.

Uso de random global.

Estado mutable compartido entre corridas.

Timestamps que afectan decisiones.

La solución
1. RNG determinista

Cada subsistema deriva su propio random.Random desde el seed maestro:

python
rng = make_daily_rng(seed, "orders", day_number)
La función derive_seed(seed, "orders", 5) usa SHA-256 sobre f"{seed}:orders:5" para generar un entero. Es estable entre versiones de Python.

2. Queries deterministas

Todas las queries iteradas por el motor tienen ORDER BY explícito:

python
customers = list(
    db.scalars(
        select(Customer)
        .where(...)
        .order_by(Customer.customer_code)  # ← obligatorio
    ).all()
)
Razón: PostgreSQL no garantiza orden sin ORDER BY. Con UPDATE sobre la tabla, puede reorganizar lecturas.

3. Motor sin estado mutable en entidades base

El motor NO modifica Customer, Product, ProductVariant, Location, State, Supplier, Carrier.

Por qué: si el motor muta Customer.profile, la segunda corrida del mismo seed parte de un estado distinto y diverge. La solución fue eliminar esas mutaciones y calcular los contadores agregados por query cuando se necesiten.

4. Transacción atómica por día

Cada día es una transacción. Si falla, rollback completo del día.

5. Sin random global

En ningún punto del motor se usa random.random(), random.choice(), etc. Siempre el RNG inyectado.

Cómo verificarlo
bash
python -m app.simulation --days 5 --seed 12345 --reset
python -m app.simulation --days 5 --seed 12345 --reset
Ambas corridas deben producir el mismo resultado exacto.

Sistema de eventos
Tipos de eventos
Scheduled: fecha predefinida (Black Friday, Buen Fin, Hot Sale).

Random: probabilidad diaria + cooldown.

Cascade: disparado por otro evento.

Estructura
Cada evento tiene:

event_type: tipo (HIGH_DEMAND, SUPPLIER_DELAY, etc.).

scope_type: alcance (GLOBAL, STATE, CATEGORY, PRODUCT, SUPPLIER, CARRIER, WAREHOUSE).

scope_value: valor específico (ej. "CDMX", "PLAYERAS", "SUP-I01").

impact_factor: multiplicador.

start_date / end_date: vigencia.

trigger: cómo se originó (SCHEDULED, RANDOM, MANUAL, CASCADE).

parent_event_id: si es cascada, referencia al padre.

Cascadas
Máximo 2 niveles. Reglas definidas en CASCADE_RULES:

python
(SUPPLIER_DELAY, STOCKOUT, 0.30)
(SUPPLIER_OUTAGE, STOCKOUT, 0.60)
(HIGH_DEMAND, WAREHOUSE_OVERLOAD, 0.20)
(CARRIER_DELAY, PRODUCT_RETURN, 0.25)
(WAREHOUSE_OVERLOAD, CARRIER_DELAY, 0.15)
(STOCKOUT, ORDER_CANCELLATION, 0.40)
(BLACK_FRIDAY, WAREHOUSE_OVERLOAD, 0.35)
(BUEN_FIN, WAREHOUSE_OVERLOAD, 0.25)
Ejemplo real observado: SUPPLIER_DELAY → STOCKOUT → ORDER_CANCELLATION.

Cómo se calcula el event_factor
Para cada producto/estado en un día:

python
factor = 1.0
for event in active_events:
    if event.scope_type == GLOBAL:
        factor *= event.impact_factor
    elif event.scope_type == CATEGORY and category_code == event.scope_value:
        factor *= event.impact_factor
    elif ...
Los eventos de tipo logístico y de oferta no afectan la demanda. Afectan lead times, cancelaciones, retrasos.

Fórmula de demanda
La fórmula maestra
text
demanda_diaria[producto, estado] =
    base_perfil[producto]
  × multiplicador_segmento
  × regional_factor[estado]
  × afinidad_categoria[estado, cat]
  × temporal_factor[cat, mes]
  × lifecycle_factor[producto]
  × growth_factor[estado, día]
  × event_factor[producto, día]
  × variación_aleatoria
Los 8 factores
Factor	Rango	Fuente
base_perfil	1–80	Punto medio del perfil (HIGH 60, MEDIUM 18, LOW 7, NICHE 2)
multiplicador_segmento	0.40–1.20	WOMEN 1.20 · MEN 1.00 · KIDS 0.60 · UNISEX 0.40
regional_factor	0.48–1.62	Atributo del estado
afinidad_categoria	0.5–1.5	Tabla state_category_affinity
temporal_factor	0.40–1.80	Patrón estacional de la categoría
lifecycle_factor	0.00–1.20	Etapa del producto
growth_factor	1.00–1.10	Crecimiento anual del estado
event_factor	1.00–3.50	Eventos activos del día
Verificación
Ejemplo del Bloque G: Playera Rikochet Mujer en CDMX, día 15 de enero:

text
base 60 × 1.20 (WOMEN) × 1.62 (CDMX) × 1.05 (PLAYERAS) × 1.00 × 1.00 × 1.00 × 1.07
= 131.24 unidades/día
Verificado con el módulo demand.py.

Fulfillment y logística
Flujo de una orden online
text
1. Cliente compra
   ↓
2. Determinar ubicación de surtido (85% CEDIS, 15% tienda)
   ↓
3. Elegir productos y SKUs según preferencias del cliente
   ↓
4. Asignar carrier según región
   ↓
5. Calcular costo de envío (tarifa × región × peso)
   ↓
6. Aplicar envío gratis si subtotal >= $599
   ↓
7. Crear Order + OrderItems + Shipment
   ↓
8. Verificar pago (5% falla)
   ↓
9. Reservar stock y registrar movimiento SALE
   ↓
10. Shipment PENDING → SHIPPED → IN_TRANSIT → DELIVERED
Selección de productos
La elección de productos de una orden usa un scoring ponderado:

python
score = 1.0
score *= 2.5 si product.segment == customer.preferred_segment
score *= 1.2 si product.segment == UNISEX
score *= 0.4 en otro caso

score *= customer_category_preference (0.5–1.5)
score *= 1.6 si demand_profile == HIGH
score *= 1.5 si price_sensitivity == LOW y producto caro
score *= 0.5 si price_sensitivity == HIGH y producto caro
score *= 1.4 si product.branded
Selección de carrier por región
Región	Carrier
Centro (CDMX, EDOMEX, PUE, QRO)	CAR-03 (Logística Centro)
Norte (NL, BC)	CAR-02 (Paquetería del Norte)
Occidente (JAL)	CAR-01 (Envíos Rápidos MX)
Sur (OAX, CHIS, GRO)	CAR-05 (Económico MX)
Si un carrier está bajo CARRIER_DELAY, se elige otro.

Reabastecimiento
Evaluación de reorder
Al final de cada día:

text
Para cada SKU × CEDIS:
    si available_quantity <= reorder_point:
        → crear PO

Para cada SKU × tienda:
    si available_quantity <= reorder_point_tienda:
        → crear Transfer desde CEDIS de la región
Selección de proveedor
Reglas en orden de prioridad:

Filtrar suppliers inactivos.

Filtrar suppliers bajo SUPPLIER_OUTAGE.

Preferir priority 1 (si no está bajo SUPPLIER_DELAY).

Considerar priority 3 (importado) si cantidad >= 500.

Preferir priority 2.

Fallback: cualquier prioridad disponible.

Cálculo de cantidad
text
cantidad_bruta = max_stock - available_quantity
cantidad_ajustada = max(MOQ, redondear_a_multiplo_de_10(cantidad_bruta))
Ejemplo: max_stock=200, available=45, MOQ=100 → 160.

Agrupación de POs
Las POs se agrupan por proveedor. Si 5 SKUs distintos necesitan reorder del mismo proveedor el mismo día, se crea 1 PO con 5 items, no 5 POs separadas.

Decisiones técnicas
UUID v4 generado en Python
python
id: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    primary_key=True,
    default=uuid.uuid4,  # ← Python, no DB
)
Ventajas:

Portable a SQLite (tests).

Control total del valor.

No requiere extensión pgcrypto.

Desventajas:

El default no aplica si insertas por SQL directo (raro en este proyecto).

available_quantity GENERATED
python
available_quantity: Mapped[int] = mapped_column(
    Integer,
    Computed("quantity - reserved_quantity", persisted=True),
)
Ventaja: nunca se desincroniza. PostgreSQL lo mantiene automáticamente.

Desventaja: no se puede escribir directamente. Hay que modificar quantity o reserved_quantity.

Enums nativos
python
status: Mapped[RecordStatus] = mapped_column(
    SAEnum(RecordStatus, name="record_status", create_type=False),
    server_default=RecordStatus.ACTIVE.value,
)
Ventajas:

Type-safe en DB.

Índices más eficientes que VARCHAR.

CHECK implícito.

Desventaja: agregar un valor requiere ALTER TYPE.

Migraciones manuales para enums
El include_object en alembic/env.py filtra los enums en autogenerate. Los enums nuevos se crean manualmente al inicio de cada migración:

python
postgresql.ENUM('VALOR1', 'VALOR2', name='nombre_enum').create(op.get_bind())
Razón: SQLAlchemy + Alembic tiene un bug donde create_type=False no se propaga al autogenerate. La solución es crear enums a mano y usar postgresql.ENUM(..., create_type=False) en las columnas.

Limitaciones de V1
Motor
Returns: se pueden crear pero no se procesan end-to-end (crear → aprobar → recibir → reembolsar).

Backorders formales: cuando no hay stock, la orden se procesa igual sin descuento real de inventario. No hay cola de backorders.

Cancelaciones por falta de stock: no existen. Solo cancelación por fallo de pago.

Fórmula de demanda: demand.py está implementado y verificado, pero la generación real de órdenes no usa esta fórmula agregada. Se genera por probabilidad individual del cliente.

Transición de perfil de cliente: no se implementa porque el motor no muta clientes. Queda para V2 con una tabla customer_state_by_run o cálculo por query.

Modelo de datos
No hay colecciones/temporadas de productos.

No hay subsegmentos (bebé, junior, plus).

No hay múltiples direcciones de envío por cliente.

No hay BOPIS (buy online, pickup in store).

No hay promotions formales: el campo discount existe pero siempre es 0.

Otros
No hay autenticación en la API.

No hay paginación con cursor (solo offset/limit).

No hay rate limiting.

No hay logging estructurado (JSON).

Roadmap
V1.1 — Tests y refinamientos
□ Tests automatizados con pytest.
□ Integrar la fórmula de demanda con la generación de órdenes.
□ Implementar returns end-to-end.
□ Backorders formales.
□ Cancelaciones por falta de stock.
V1.2 — Performance
□ Batch inserts con bulk_save_objects.
□ Índices adicionales según queries observadas.
□ Paginación con cursor para runs grandes.
V2 — Data platform
□ Repositorio retail-data-platform.
□ Ingestion desde PostgreSQL operacional.
□ RAW + Validation + STAGING.
□ Modelo analítico (star schema).
□ KPIs precalculados.
□ React dashboard.
□ Airflow para orquestación.
V3 — dbt
□ Migrar transformaciones a dbt.
□ Tests de dbt.
□ Documentación de linaje.
V4 — Cloud
□ Migrar a GCP o AWS.
□ BigQuery o Snowflake.
□ Airflow gestionado.
□ CI/CD con GitHub Actions.
V5 — ML / AI
□ Demand forecasting.
□ Stockout prediction.
□ Reorder recommendation.
Conclusión
El proyecto demuestra:

Diseño de sistemas: 25 tablas coherentes con reglas de negocio reales.

Backend engineering: FastAPI + SQLAlchemy + Alembic + PostgreSQL.

Simulación con estado: motor de 8 fases que produce datos trazables.

Reproducibilidad estricta: RNG jerárquico + sin estado mutable.

Data engineering: base sólida para el siguiente repositorio.