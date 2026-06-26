from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atalaia.db.base import Base
from atalaia.db.models.pagamento_conta_pagar import FormaPagamentoEnum


class PagamentoContaReceber(Base):
    __tablename__ = "pagamentos_conta_receber"
    __table_args__ = (
        CheckConstraint("valor > 0", name="valor_positivo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conta_receber_id: Mapped[int] = mapped_column(ForeignKey("contas_receber.id"), nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    forma_pagamento: Mapped[FormaPagamentoEnum] = mapped_column(Enum(FormaPagamentoEnum), nullable=False)
    data_pagamento: Mapped[date] = mapped_column(Date, nullable=False)
    observacoes: Mapped[str | None] = mapped_column(String(200), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    conta_receber: Mapped["ContaReceber"] = relationship("ContaReceber", back_populates="pagamentos")
