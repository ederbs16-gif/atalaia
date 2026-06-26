import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atalaia.db.base import Base


class StatusVendaEnum(enum.Enum):
    aberta = "aberta"
    finalizada = "finalizada"
    cancelada = "cancelada"


class Venda(Base):
    __tablename__ = "vendas"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    orcamento_id: Mapped[int | None] = mapped_column(ForeignKey("orcamentos.id"), nullable=True)
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("clientes.id"), nullable=True)
    caixa_id: Mapped[int | None] = mapped_column(ForeignKey("caixas.id"), nullable=True)
    status: Mapped[StatusVendaEnum] = mapped_column(
        Enum(StatusVendaEnum), default=StatusVendaEnum.aberta, nullable=False
    )
    desconto_percentual: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0"), nullable=False
    )
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"), nullable=False)
    forma_pagamento_principal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    orcamento: Mapped["Orcamento"] = relationship("Orcamento", back_populates="venda")  # noqa: F821
    cliente: Mapped["Cliente"] = relationship("Cliente", back_populates="vendas")  # noqa: F821
    itens: Mapped[list["ItemVenda"]] = relationship(
        "ItemVenda", back_populates="venda", cascade="all, delete-orphan"
    )
    pagamentos: Mapped[list["PagamentoVenda"]] = relationship(  # noqa: F821
        "PagamentoVenda", back_populates="venda", cascade="all, delete-orphan"
    )
    devolucoes: Mapped[list["Devolucao"]] = relationship(  # noqa: F821
        "Devolucao", back_populates="venda", cascade="all, delete-orphan"
    )


class ItemVenda(Base):
    __tablename__ = "itens_venda"
    __table_args__ = (
        CheckConstraint("quantidade > 0", name="quantidade_positiva"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    venda_id: Mapped[int] = mapped_column(ForeignKey("vendas.id"), nullable=False)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), nullable=False)
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False)
    preco_unitario: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    venda: Mapped["Venda"] = relationship("Venda", back_populates="itens")
    produto: Mapped["Produto"] = relationship("Produto", lazy="joined")  # noqa: F821
