from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atalaia.db.base import Base


class TipoDevolucaoEnum(enum.Enum):
    troca = "troca"
    reembolso = "reembolso"


class StatusDevolucaoEnum(enum.Enum):
    pendente = "pendente"
    concluida = "concluida"


class Devolucao(Base):
    __tablename__ = "devolucoes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    venda_id: Mapped[int] = mapped_column(ForeignKey("vendas.id"), nullable=False)
    tipo: Mapped[TipoDevolucaoEnum] = mapped_column(Enum(TipoDevolucaoEnum), nullable=False)
    motivo: Mapped[str] = mapped_column(String(500), nullable=False)
    valor_reembolso: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), default=Decimal("0"), nullable=False
    )
    forma_reembolso: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[StatusDevolucaoEnum] = mapped_column(
        Enum(StatusDevolucaoEnum), default=StatusDevolucaoEnum.pendente, nullable=False
    )
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    venda: Mapped["Venda"] = relationship("Venda", back_populates="devolucoes")  # noqa: F821
    itens: Mapped[list["ItemDevolucao"]] = relationship(
        "ItemDevolucao", back_populates="devolucao", cascade="all, delete-orphan"
    )


class ItemDevolucao(Base):
    __tablename__ = "itens_devolucao"
    __table_args__ = (
        CheckConstraint("quantidade > 0", name="quantidade_positiva"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    devolucao_id: Mapped[int] = mapped_column(ForeignKey("devolucoes.id"), nullable=False)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), nullable=False)
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False)
    produto_substituto_id: Mapped[int | None] = mapped_column(
        ForeignKey("produtos.id"), nullable=True
    )

    devolucao: Mapped["Devolucao"] = relationship("Devolucao", back_populates="itens")
    produto: Mapped["Produto"] = relationship(  # noqa: F821
        "Produto", foreign_keys=[produto_id]
    )
    produto_substituto: Mapped["Produto | None"] = relationship(  # noqa: F821
        "Produto", foreign_keys=[produto_substituto_id]
    )
