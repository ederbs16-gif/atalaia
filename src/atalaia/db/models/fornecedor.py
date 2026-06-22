from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from atalaia.db.base import Base


class Fornecedor(Base):
    """
    Representa um fornecedor de mercadorias.

    Decisão de design: não há UNIQUE em 'nome' nem em 'documento'.
    - 'nome': o mesmo fornecedor pode ter filiais com nomes semelhantes ou
      ligeiramente diferentes; impor unicidade geraria falso-positivo.
    - 'documento': campo nullable por design — fornecedores informais, pessoa
      física sem CNPJ ou estrangeiros podem não ter identificador fiscal
      compatível. Mesmo quando preenchido, não validamos dígitos verificadores:
      o campo é texto livre para cobrir CNPJ, CPF e identificadores variados.

    Soft-delete: nunca excluir fisicamente — setar ativo=False.
    Fornecedores referenciados em entradas passadas devem permanecer acessíveis
    para histórico mesmo após inativação.
    """

    __tablename__ = "fornecedores"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(150), nullable=False)
    documento: Mapped[str | None] = mapped_column(String(20), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    observacoes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    entradas: Mapped[list["EntradaMercadoria"]] = relationship(  # noqa: F821
        "EntradaMercadoria", back_populates="fornecedor"
    )
