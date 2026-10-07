"""Modelos SQLAlchemy del simulador.

Aquí se importan todos los modelos para que SQLAlchemy los registre
en Base.metadata. Esto es indispensable para que Alembic los detecte
en las migraciones autogeneradas.

Orden de imports: respetar dependencias (catálogo primero, luego
geografía, clientes, inventario, suppliers, sales, simulation).
"""

from app.models.catalog import (
    Category,
    Product,
    ProductVariant,
)
from app.models.customers import (
    Customer,
    CustomerCategoryPreference,
)
from app.models.geography import (
    Location,
    State,
    StateCategoryAffinity,
)
from app.models.inventory import (
    Inventory,
    InventoryMovement,
    Transfer,
    TransferItem,
)
from app.models.sales import (
    Carrier,
    Order,
    OrderItem,
    Return,
    ReturnItem,
    Shipment,
)
from app.models.simulation import (
    SimulationEvent,
    SimulationRun,
    SimulationSnapshot,
)
from app.models.suppliers import (
    PurchaseOrder,
    PurchaseOrderItem,
    Supplier,
    SupplierProduct,
)

__all__ = [
    # Catalog
    "Category",
    "Product",
    "ProductVariant",
    # Geography
    "Location",
    "State",
    "StateCategoryAffinity",
    # Customers
    "Customer",
    "CustomerCategoryPreference",
    # Inventory
    "Inventory",
    "InventoryMovement",
    "Transfer",
    "TransferItem",
    # Suppliers
    "Supplier",
    "SupplierProduct",
    "PurchaseOrder",
    "PurchaseOrderItem",
    # Sales
    "Carrier",
    "Order",
    "OrderItem",
    "Shipment",
    "Return",
    "ReturnItem",
    # Simulation
    "SimulationRun",
    "SimulationEvent",
    "SimulationSnapshot",
]