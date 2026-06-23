from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atalaia.db.base import Base


class Cliente(Base):
    """
    Representa um cliente do estabelecimento.

    Decisão de design: não há UNIQUE em 'nome' nem em 'documento'.
    - 'nome': homônimos são comuns; unicidade geraria falso-positivo.
    - 'documento': campo nullable — clientes sem CPF/CNPJ são válidos.
      Mesmo quando preenchido, é texto livre (sem validação de dígitos
      verificadores), cobrindo CPF, CNPJ e identificadores variados.

    Soft-delete: nunca excluir fisicamente — setar ativo=False.
    Clientes referenciados em orçamentos e vendas passadas devem permanecer
    acessíveis para histórico mesmo após inativação.
    """

    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    telefone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    documento: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    orcamentos: Mapped[list["Orcamento"]] = relationship("Orcamento", back_populates="cliente")  # noqa: F821
    vendas: Mapped[list["Venda"]] = relationship("Venda", back_populates="cliente")  # noqa: F821
