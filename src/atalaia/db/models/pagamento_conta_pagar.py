from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atalaia.db.base import Base


class FormaPagamentoEnum(enum.Enum):
    dinheiro = "dinheiro"
    pix = "pix"
    debito = "debito"
    credito = "credito"


class PagamentoContaPagar(Base):
    __tablename__ = "pagamentos_conta_pagar"
    __table_args__ = (
        CheckConstraint("valor > 0", name="valor_positivo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conta_pagar_id: Mapped[int] = mapped_column(ForeignKey("contas_pagar.id"), nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    forma_pagamento: Mapped[FormaPagamentoEnum] = mapped_column(Enum(FormaPagamentoEnum), nullable=False)
    data_pagamento: Mapped[date] = mapped_column(Date, nullable=False)
    observacoes: Mapped[str | None] = mapped_column(String(200), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    conta_pagar: Mapped["ContaPagar"] = relationship("ContaPagar", back_populates="pagamentos")
