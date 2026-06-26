from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atalaia.db.base import Base


class PagamentoVenda(Base):
    __tablename__ = "pagamentos_venda"
    __table_args__ = (
        CheckConstraint("valor > 0", name="valor_positivo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    venda_id: Mapped[int] = mapped_column(ForeignKey("vendas.id"), nullable=False)
    forma: Mapped[str] = mapped_column(String(20), nullable=False)
    valor: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    venda: Mapped["Venda"] = relationship("Venda", back_populates="pagamentos")  # noqa: F821
