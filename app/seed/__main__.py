"""Entry point del seed completo.

Uso:
    python -m app.seed
"""

from app.seed.carriers import run as run_carriers
from app.seed.catalog import run as run_catalog
from app.seed.customers import run as run_customers
from app.seed.geography import run as run_geography
from app.seed.inventory import run as run_inventory
from app.seed.suppliers import run as run_suppliers


def main() -> None:
    run_catalog()
    run_geography()
    run_customers()
    run_inventory()
    run_suppliers()
    run_carriers()


if __name__ == "__main__":
    main()