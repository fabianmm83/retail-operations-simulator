"""Enums nativos de PostgreSQL para el simulador.

Todos los enums del proyecto viven aquí para evitar imports circulares
y mantener una única fuente de verdad.

Los nombres de las clases coinciden con el nombre del tipo PostgreSQL
que Alembic generará. Los valores son los que se almacenan en la DB.
"""

import enum


# =============================================================================
# CATÁLOGO (M1)
# =============================================================================


class DepartmentType(enum.StrEnum):
    """Departamento al que pertenece una categoría."""

    APPAREL = "APPAREL"
    FOOTWEAR = "FOOTWEAR"
    EQUIPMENT = "EQUIPMENT"
    ACCESSORIES = "ACCESSORIES"


class SegmentType(enum.StrEnum):
    """Segmento demográfico al que pertenece un producto."""

    WOMEN = "WOMEN"
    MEN = "MEN"
    KIDS = "KIDS"
    UNISEX = "UNISEX"


class AgeGroupType(enum.StrEnum):
    """Grupo de edad objetivo del producto."""

    ADULT = "ADULT"
    KIDS = "KIDS"


class SportType(enum.StrEnum):
    """Deporte principal al que está orientado el producto."""

    RUNNING = "RUNNING"
    TRAINING = "TRAINING"
    FUTBOL = "FUTBOL"
    BASKET = "BASKET"
    CASUAL = "CASUAL"
    YOGA = "YOGA"
    GENERAL = "GENERAL"


class DemandProfileType(enum.StrEnum):
    """Perfil de demanda asignado al producto."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NICHE = "NICHE"


class SeasonalityType(enum.StrEnum):
    """Patrón estacional de la categoría."""

    NONE = "NONE"
    WINTER = "WINTER"
    NEW_YEAR = "NEW_YEAR"
    SUMMER = "SUMMER"


class LifecycleStageType(enum.StrEnum):
    """Etapa del ciclo de vida del producto."""

    LAUNCH = "LAUNCH"
    GROWTH = "GROWTH"
    MATURE = "MATURE"
    DECLINE = "DECLINE"
    DISCONTINUED = "DISCONTINUED"


class ColorCode(enum.StrEnum):
    """Paleta cerrada de colores del catálogo."""

    BLK = "BLK"  # Negro
    WHT = "WHT"  # Blanco
    GRY = "GRY"  # Gris
    NVY = "NVY"  # Marino
    RED = "RED"  # Rojo
    BLU = "BLU"  # Azul
    GRN = "GRN"  # Verde
    PNK = "PNK"  # Rosa
    YLW = "YLW"  # Amarillo Rikochet


# =============================================================================
# GEOGRAFÍA (M2)
# =============================================================================


class IncomeGroupType(enum.StrEnum):
    """Grupo de ingreso relativo de un estado."""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class RegionType(enum.StrEnum):
    """Región geográfica de México."""

    CENTRO = "CENTRO"
    NORTE = "NORTE"
    OCCIDENTE = "OCCIDENTE"
    SUR = "SUR"


class LocationType(enum.StrEnum):
    """Tipo de ubicación física."""

    CEDIS = "CEDIS"
    STORE = "STORE"


# =============================================================================
# CLIENTES (M3)
# =============================================================================


class CustomerProfile(enum.StrEnum):
    """Perfil de comportamiento del cliente."""

    NEW = "NEW"
    ONE_TIME = "ONE_TIME"
    OCCASIONAL = "OCCASIONAL"
    REGULAR = "REGULAR"
    LOYAL = "LOYAL"
    INACTIVE = "INACTIVE"


class ChannelPreference(enum.StrEnum):
    """Canal preferido de compra del cliente."""

    ONLINE = "ONLINE"
    STORE = "STORE"
    OMNICHANNEL = "OMNICHANNEL"


class PriceSensitivity(enum.StrEnum):
    """Sensibilidad al precio del cliente."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class GenderType(enum.StrEnum):
    """Género del cliente."""

    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


# =============================================================================
# INVENTARIO (M4)
# =============================================================================


class MovementType(enum.StrEnum):
    """Tipo de movimiento de inventario."""

    SALE = "SALE"
    PURCHASE_RECEIPT = "PURCHASE_RECEIPT"
    RETURN = "RETURN"
    ADJUSTMENT = "ADJUSTMENT"
    DAMAGE = "DAMAGE"
    TRANSFER_OUT = "TRANSFER_OUT"
    TRANSFER_IN = "TRANSFER_IN"


class TransferStatus(enum.StrEnum):
    """Estado de una transferencia entre ubicaciones."""

    PENDING = "PENDING"
    IN_TRANSIT = "IN_TRANSIT"
    RECEIVED = "RECEIVED"
    CANCELLED = "CANCELLED"


class StockStatus(enum.StrEnum):
    """Estado calculado del stock de un SKU en una ubicación."""

    NORMAL = "NORMAL"
    REORDER = "REORDER"
    CRITICAL = "CRITICAL"
    STOCKOUT = "STOCKOUT"


# =============================================================================
# SUPPLIERS (M5)
# =============================================================================


class SupplierType(enum.StrEnum):
    """Tipo de proveedor."""

    LARGE_NATIONAL = "LARGE_NATIONAL"
    MEDIUM_NATIONAL = "MEDIUM_NATIONAL"
    IMPORTED = "IMPORTED"


class PurchaseOrderStatus(enum.StrEnum):
    """Estado de una purchase order."""

    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    IN_TRANSIT = "IN_TRANSIT"
    RECEIVED = "RECEIVED"
    PARTIAL = "PARTIAL"
    CANCELLED = "CANCELLED"


# =============================================================================
# SALES + LOGISTICS (M6)
# =============================================================================


class OrderChannel(enum.StrEnum):
    """Canal por el que se generó la orden."""

    ONLINE = "ONLINE"
    STORE = "STORE"


class OrderStatus(enum.StrEnum):
    """Estado del ciclo de vida de una orden."""

    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    PROCESSING = "PROCESSING"
    PACKED = "PACKED"
    SHIPPED = "SHIPPED"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    RETURNED = "RETURNED"


class PaymentMethod(enum.StrEnum):
    """Método de pago de la orden."""

    CARD = "CARD"
    CASH = "CASH"
    TRANSFER = "TRANSFER"
    OXXO = "OXXO"
    WALLET = "WALLET"


class ShipmentStatus(enum.StrEnum):
    """Estado del ciclo de vida de un shipment."""

    PENDING = "PENDING"
    PACKED = "PACKED"
    SHIPPED = "SHIPPED"
    IN_TRANSIT = "IN_TRANSIT"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    DELAYED = "DELAYED"
    LOST = "LOST"


class ReturnStatus(enum.StrEnum):
    """Estado del ciclo de vida de un return."""

    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    RECEIVED = "RECEIVED"
    REFUNDED = "REFUNDED"
    REJECTED = "REJECTED"


class ReturnReason(enum.StrEnum):
    """Motivo de la devolución."""

    WRONG_SIZE = "WRONG_SIZE"
    NOT_AS_EXPECTED = "NOT_AS_EXPECTED"
    DEFECTIVE = "DEFECTIVE"
    LATE_DELIVERY = "LATE_DELIVERY"
    CHANGED_MIND = "CHANGED_MIND"
    OTHER = "OTHER"


class ReturnItemCondition(enum.StrEnum):
    """Condición del producto devuelto."""

    GOOD = "GOOD"
    DAMAGED = "DAMAGED"
    USED = "USED"


class CarrierCoverage(enum.StrEnum):
    """Cobertura geográfica de un carrier."""

    NATIONAL = "NATIONAL"
    NORTH = "NORTH"
    CENTER = "CENTER"
    SOUTH = "SOUTH"


# =============================================================================
# SIMULATION (M7)
# =============================================================================


class SimulationRunStatus(enum.StrEnum):
    """Estado del ciclo de vida de una simulación."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class SimulationScenario(enum.StrEnum):
    """Escenario de la simulación."""

    BASELINE = "BASELINE"
    HIGH_DEMAND = "HIGH_DEMAND"
    SUPPLY_CRISIS = "SUPPLY_CRISIS"
    LOGISTICS_CRISIS = "LOGISTICS_CRISIS"
    ECONOMIC_DOWNTURN = "ECONOMIC_DOWNTURN"
    PEAK_SEASON = "PEAK_SEASON"
    STRESS_TEST = "STRESS_TEST"


class SimulationEventType(enum.StrEnum):
    """Tipo de evento de simulación.

    Los eventos alteran las condiciones normales durante su vigencia.
    Los comerciales afectan demanda; los de oferta afectan POs;
    los logísticos afectan shipments.
    """

    # Comerciales (demanda)
    NORMAL_OPERATION = "NORMAL_OPERATION"
    HIGH_DEMAND = "HIGH_DEMAND"
    BLACK_FRIDAY = "BLACK_FRIDAY"
    BUEN_FIN = "BUEN_FIN"
    HOT_SALE = "HOT_SALE"
    SEASONAL_PEAK = "SEASONAL_PEAK"
    DEMAND_DROP = "DEMAND_DROP"
    PRODUCT_LAUNCH = "PRODUCT_LAUNCH"
    PROMOTION = "PROMOTION"

    # De oferta (proveedores + CEDIS)
    SUPPLIER_DELAY = "SUPPLIER_DELAY"
    SUPPLIER_OUTAGE = "SUPPLIER_OUTAGE"
    WAREHOUSE_DELAY = "WAREHOUSE_DELAY"
    WAREHOUSE_OVERLOAD = "WAREHOUSE_OVERLOAD"

    # Logísticos (carriers + shipments)
    CARRIER_DELAY = "CARRIER_DELAY"
    LOST_SHIPMENT = "LOST_SHIPMENT"

    # Operativos
    STOCKOUT = "STOCKOUT"
    PRODUCT_RETURN = "PRODUCT_RETURN"
    PAYMENT_FAILURE = "PAYMENT_FAILURE"
    ORDER_CANCELLATION = "ORDER_CANCELLATION"
    PRICE_CHANGE = "PRICE_CHANGE"


class SimulationEventScope(enum.StrEnum):
    """Alcance del evento."""

    GLOBAL = "GLOBAL"
    STATE = "STATE"
    CATEGORY = "CATEGORY"
    PRODUCT = "PRODUCT"
    SUPPLIER = "SUPPLIER"
    CARRIER = "CARRIER"
    WAREHOUSE = "WAREHOUSE"


class SimulationEventStatus(enum.StrEnum):
    """Estado del ciclo de vida de un evento."""

    SCHEDULED = "SCHEDULED"
    ACTIVE = "ACTIVE"
    FINISHED = "FINISHED"
    CANCELLED = "CANCELLED"


class SimulationEventTrigger(enum.StrEnum):
    """Cómo se originó el evento."""

    SCHEDULED = "SCHEDULED"
    RANDOM = "RANDOM"
    MANUAL = "MANUAL"
    CASCADE = "CASCADE"


# =============================================================================
# ESTADO GENÉRICO
# =============================================================================


class RecordStatus(enum.StrEnum):
    """Estado genérico de un registro (soft status, no soft delete)."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"