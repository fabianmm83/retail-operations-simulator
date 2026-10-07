"""Base declarativa de SQLAlchemy.

Todos los modelos heredan de `Base`. Para que Alembic detecte las
tablas en autogenerate, es indispensable que los modelos se importen
ANTES de usar `Base.metadata`.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base declarativa común a todos los modelos."""

    pass


# Importar todos los modelos para que se registren en Base.metadata.
# Este import va al final para evitar ciclos:
#   app.models.catalog importa Base desde aquí,
#   entonces aquí importamos catalog después de definir Base.
from app.models import catalog  # noqa: E402, F401
from app.models import customers  # noqa: E402, F401
from app.models import geography  # noqa: E402, F401
from app.models import inventory  # noqa: E402, F401
from app.models import sales  # noqa: E402, F401
from app.models import simulation  # noqa: E402, F401
from app.models import suppliers  # noqa: E402, F401