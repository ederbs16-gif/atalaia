from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from atalaia.db.base import Base


class Configuracao(Base):
    __tablename__ = "configuracoes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chave: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    valor: Mapped[str] = mapped_column(String(500), nullable=True)
