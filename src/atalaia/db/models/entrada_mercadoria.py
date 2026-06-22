import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atalaia.db.base import Base


class StatusEntradaEnum(enum.Enum):
    rascunho = "rascunho"
    confirmada = "confirmada"


class EntradaMercadoria(Base):
    __tablename__ = "entradas_mercadorias"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    fornecedor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("fornecedores.id"), nullable=False
    )
    numero_nota: Mapped[str | None] = mapped_column(String(50), nullable=True)
    data_entrada: Mapped[date] = mapped_column(Date, nullable=False)
    observacoes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[StatusEntradaEnum] = mapped_column(
        Enum(StatusEntradaEnum), nullable=False, default=StatusEntradaEnum.rascunho
    )
    criado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    fornecedor: Mapped["Fornecedor"] = relationship(  # noqa: F821
        "Fornecedor", back_populates="entradas"
    )
    itens: Mapped[list["ItemEntrada"]] = relationship(
        "ItemEntrada", back_populates="entrada", cascade="all, delete-orphan"
    )


class ItemEntrada(Base):
    __tablename__ = "itens_entrada"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    entrada_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("entradas_mercadorias.id"), nullable=False
    )
    produto_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("produtos.id"), nullable=False
    )
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False)
    custo_unitario: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    entrada: Mapped["EntradaMercadoria"] = relationship(
        "EntradaMercadoria", back_populates="itens"
    )
    produto: Mapped["Produto"] = relationship(  # noqa: F821
        "Produto", back_populates="itens_entrada", lazy="joined"
    )

    __table_args__ = (
        CheckConstraint("quantidade > 0", name="quantidade_positiva"),
        CheckConstraint("custo_unitario >= 0", name="custo_unitario_nao_negativo"),
    )
