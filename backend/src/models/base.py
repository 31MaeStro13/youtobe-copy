"""
Базовые миксины для моделей: автогенерация временных меток и первичных ключей.
"""

from datetime import datetime
from sqlalchemy import DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column


class TimestampMixin:
    """Миксин для фиксации времени создания и обновления записи."""
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class IDMixin:
    """Миксин для суррогатного целочисленного первичного ключа."""
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
