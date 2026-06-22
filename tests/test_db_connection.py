"""
Teste de conexão via get_session().

Usa SQLite em memória (não MySQL) porque:
- Não exige servidor MySQL rodando no ambiente de CI ou na máquina do dev.
- É suficiente para validar que get_session() abre, faz commit e fecha corretamente.
- Testes que dependem de comportamento MySQL-específico (enums, tipos) devem usar
  um banco de teste dedicado e ser marcados com @pytest.mark.integration.
"""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from contextlib import contextmanager

from atalaia.db.base import Base
import atalaia.db.models  # noqa: F401 — registra todos os models na metadata


TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="module")
def sqlite_engine():
    engine = create_engine(TEST_DATABASE_URL)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def sqlite_get_session(sqlite_engine):
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sqlite_engine)

    @contextmanager
    def _get_session():
        session = _SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return _get_session


def test_session_opens_and_closes(sqlite_get_session):
    with sqlite_get_session() as session:
        result = session.execute(text("SELECT 1")).scalar()
        assert result == 1


def test_session_rollback_on_error(sqlite_get_session):
    with pytest.raises(ZeroDivisionError):
        with sqlite_get_session() as session:
            session.execute(text("SELECT 1"))
            raise ZeroDivisionError("erro simulado")
