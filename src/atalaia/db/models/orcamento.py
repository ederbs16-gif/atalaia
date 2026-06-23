import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atalaia.db.base import Base


class StatusOrcamentoEnum(enum.Enum):
    aberto = "aberto"
    aprovado = "aprovado"
    recusado = "recusado"


class Orcamento(Base):
    __tablename__ = "orcamentos"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    numero: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    cliente_id: Mapped[int] = mapped_column(ForeignKey("clientes.id"), nullable=False)
    status: Mapped[StatusOrcamentoEnum] = mapped_column(
        Enum(StatusOrcamentoEnum), default=StatusOrcamentoEnum.aberto, nullable=False
    )
    validade_dias: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    data_criacao: Mapped[date] = mapped_column(Date, nullable=False)
    data_validade: Mapped[date] = mapped_column(Date, nullable=False)
    desconto_percentual: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=Decimal("0"), nullable=False
    )
    observacoes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    cliente: Mapped["Cliente"] = relationship("Cliente", back_populates="orcamentos")  # noqa: F821
    itens: Mapped[list["ItemOrcamento"]] = relationship(
        "ItemOrcamento", back_populates="orcamento", cascade="all, delete-orphan"
    )
    venda: Mapped["Venda"] = relationship("Venda", back_populates="orcamento", uselist=False)  # noqa: F821


class ItemOrcamento(Base):
    __tablename__ = "itens_orcamento"
    __table_args__ = (
        CheckConstraint("quantidade > 0", name="quantidade_positiva"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    orcamento_id: Mapped[int] = mapped_column(ForeignKey("orcamentos.id"), nullable=False)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"), nullable=False)
    quantidade: Mapped[int] = mapped_column(Integer, nullable=False)
    preco_unitario: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)

    orcamento: Mapped["Orcamento"] = relationship("Orcamento", back_populates="itens")
    produto: Mapped["Produto"] = relationship("Produto", lazy="joined")  # noqa: F821
