from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atalaia.db.base import Base


class StatusContaEnum(enum.Enum):
    pendente = "pendente"
    pago_parcialmente = "pago_parcialmente"
    pago = "pago"


class ContaPagar(Base):
    __tablename__ = "contas_pagar"
    __table_args__ = (
        CheckConstraint("valor_total > 0", name="valor_total_positivo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    descricao: Mapped[str] = mapped_column(String(200), nullable=False)
    valor_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    valor_pago: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=Decimal("0"), nullable=False)
    status: Mapped[StatusContaEnum] = mapped_column(
        Enum(StatusContaEnum), default=StatusContaEnum.pendente, nullable=False
    )
    vencimento: Mapped[date] = mapped_column(Date, nullable=False)
    fornecedor_id: Mapped[int | None] = mapped_column(ForeignKey("fornecedores.id"), nullable=True)
    parcela_numero: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parcela_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grupo_parcelas: Mapped[str | None] = mapped_column(String(36), nullable=True)
    observacoes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    fornecedor: Mapped["Fornecedor | None"] = relationship("Fornecedor", back_populates="contas_pagar")
    pagamentos: Mapped[list["PagamentoContaPagar"]] = relationship(
        "PagamentoContaPagar", back_populates="conta_pagar", cascade="all, delete-orphan"
    )
