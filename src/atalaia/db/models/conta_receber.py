from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atalaia.db.base import Base
from atalaia.db.models.conta_pagar import StatusContaEnum


class ContaReceber(Base):
    __tablename__ = "contas_receber"
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
    cliente_id: Mapped[int | None] = mapped_column(ForeignKey("clientes.id"), nullable=True)
    orcamento_id: Mapped[int | None] = mapped_column(ForeignKey("orcamentos.id"), nullable=True)
    parcela_numero: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parcela_total: Mapped[int | None] = mapped_column(Integer, nullable=True)
    grupo_parcelas: Mapped[str | None] = mapped_column(String(36), nullable=True)
    observacoes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    cliente: Mapped["Cliente | None"] = relationship("Cliente", back_populates="contas_receber")
    orcamento: Mapped["Orcamento | None"] = relationship("Orcamento", back_populates="contas_receber")
    pagamentos: Mapped[list["PagamentoContaReceber"]] = relationship(
        "PagamentoContaReceber", back_populates="conta_receber", cascade="all, delete-orphan"
    )
