"""Testes de service do módulo Clientes."""
from __future__ import annotations

from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from atalaia.db.base import Base
import atalaia.db.models  # noqa: F401

from atalaia.modules.clientes import service
from atalaia.modules.clientes.exceptions import ClienteNaoEncontradoError


@pytest.fixture(scope="module")
def engine():
    e = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(e)
    yield e
    Base.metadata.drop_all(e)
    e.dispose()


@pytest.fixture()
def SM(engine):
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(autouse=True)
def patch_service(SM, monkeypatch):
    @contextmanager
    def _session():
        s = SM()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    monkeypatch.setattr(service, "get_session", _session)

    yield

    with SM() as s:
        s.execute(text("DELETE FROM clientes"))
        s.commit()


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

def test_criar_cliente_nome_vazio_levanta_value_error():
    with pytest.raises(ValueError, match="Nome"):
        service.criar_cliente({"nome": ""})


def test_criar_cliente_valido_documento_none():
    c = service.criar_cliente({"nome": "Maria Silva", "documento": None})
    assert c.id is not None
    assert c.nome == "Maria Silva"
    assert c.documento is None
    assert c.ativo is True


def test_inativar_cliente_remove_de_listagem_ativa():
    c = service.criar_cliente({"nome": "João Ativo"})
    service.inativar_cliente(c.id)
    ativos = service.listar_clientes(apenas_ativos=True)
    assert not any(x.id == c.id for x in ativos)


def test_obter_cliente_inexistente_levanta_erro():
    with pytest.raises(ClienteNaoEncontradoError):
        service.obter_cliente(999999)


def test_buscar_por_nome_retorna_cliente():
    service.criar_cliente({"nome": "Ana Rodrigues"})
    resultado = service.buscar_clientes_por_termo("rodrigues")
    assert any(c.nome == "Ana Rodrigues" for c in resultado)


def test_buscar_por_documento_retorna_cliente():
    service.criar_cliente({"nome": "Carlos Doc", "documento": "123.456.789-00"})
    resultado = service.buscar_clientes_por_termo("456.789")
    assert any(c.nome == "Carlos Doc" for c in resultado)


def test_buscar_sem_correspondencia_retorna_vazio():
    resultado = service.buscar_clientes_por_termo("xyzxyzxyz")
    assert resultado == []
