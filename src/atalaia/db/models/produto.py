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


class TipoEnum(enum.Enum):
    produto = "produto"
    servico = "servico"


class Produto(Base):
    __tablename__ = "produtos"

    # Identificação e classificação
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(200), nullable=False)
    descricao: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tipo: Mapped[TipoEnum] = mapped_column(Enum(TipoEnum), nullable=False)
    categoria_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("categorias.id"), nullable=False
    )

    # Estoque
    controla_estoque: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    estoque_atual: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    estoque_minimo: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Preço e desconto
    preco_custo: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    preco_custo_anterior: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    custo_medio: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    preco_venda: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    permite_desconto: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    desconto_maximo_percentual: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), default=0, nullable=False
    )

    # Promoção
    produto_em_promocao: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    preco_promocional: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    promocao_inicio: Mapped[date | None] = mapped_column(Date, nullable=True)
    promocao_fim: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Outros
    codigo_barras: Mapped[str | None] = mapped_column(
        String(50), unique=True, index=True, nullable=True
    )
    unidade_medida: Mapped[str] = mapped_column(String(10), default="UN", nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    categoria: Mapped["Categoria"] = relationship(  # noqa: F821
        "Categoria", back_populates="produtos"
    )
    itens_entrada: Mapped[list["ItemEntrada"]] = relationship(  # noqa: F821
        "ItemEntrada", back_populates="produto"
    )

    __table_args__ = (
        CheckConstraint("estoque_atual >= 0", name="estoque_nao_negativo"),
        CheckConstraint("preco_venda >= 0", name="preco_venda_nao_negativo"),
        CheckConstraint(
            "desconto_maximo_percentual >= 0 AND desconto_maximo_percentual <= 100",
            name="desconto_maximo_valido",
        ),
        CheckConstraint(
            "promocao_inicio IS NULL OR promocao_fim IS NULL OR promocao_fim >= promocao_inicio",
            name="datas_promocao_validas",
        ),
        CheckConstraint(
            "preco_promocional IS NULL OR preco_promocional <= preco_venda",
            name="preco_promocional_valido",
        ),
    )
