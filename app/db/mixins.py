"""Mixins reutilizables para los modelos SQLAlchemy.

Centralizan comportamiento común: UUIDs, timestamps de auditoría, etc.
Todos los modelos del proyecto heredan de al menos uno de estos mixins.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column


class UUIDMixin:
    """Agrega una PK UUID v4 generada en Python.

    Ventajas:
    - No depende de extensiones de PostgreSQL (pgcrypto).
    - Portable a SQLite para tests.
    - El valor es determinista desde la app, no desde la DB.
    """

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False,
    )


class TimestampMixin:
    """Agrega created_at y updated_at gestionados por la app.

    - created_at: se asigna al insertar (default=func.now()).
    - updated_at: se actualiza en cada UPDATE (onupdate=func.now()).
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )