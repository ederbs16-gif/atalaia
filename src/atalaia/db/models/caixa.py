from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, Enum, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from atalaia.db.base import Base


class StatusCaixaEnum(enum.Enum):
    aberto = "aberto"
    fechado = "fechado"


class Caixa(Base):
    __tablename__ = "caixas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    hostname: Mapped[str] = mapped_column(String(100), nullable=False)
    saldo_inicial: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"), nullable=False)
    total_dinheiro: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"), nullable=False)
    total_pix: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"), nullable=False)
    total_debito: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"), nullable=False)
    total_credito: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"), nullable=False)
    status: Mapped[StatusCaixaEnum] = mapped_column(
        Enum(StatusCaixaEnum), default=StatusCaixaEnum.aberto, nullable=False
    )
    aberto_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    fechado_em: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    observacoes: Mapped[str | None] = mapped_column(String(500), nullable=True)
