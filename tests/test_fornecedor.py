"""
Testes da camada de serviço de Fornecedores.

Usa SQLite em memória com monkeypatch de get_session no módulo fornecedor_service,
mesmo padrão de test_service_produto.py.
"""

from __future__ import annotations

from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from atalaia.db.base import Base
import atalaia.db.models  # noqa: F401 — registra todos os models na metadata
from atalaia.modules.entrada_mercadorias import fornecedor_service
from atalaia.modules.entrada_mercadorias.exceptions import FornecedorNaoEncontradoError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine():
    e = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(e)
    yield e
    Base.metadata.drop_all(e)
    e.dispose()


@pytest.fixture(autouse=True)
def patch_and_clean(engine, monkeypatch):
    _SM = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    @contextmanager
    def _test_session():
        s = _SM()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    monkeypatch.setattr(fornecedor_service, "get_session", _test_session)

    yield

    with engine.connect() as conn:
        conn.execute(text("DELETE FROM fornecedores"))
        conn.commit()


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

def test_criar_fornecedor_nome_vazio_levanta_erro():
    with pytest.raises(ValueError, match="[Nn]ome"):
        fornecedor_service.criar_fornecedor({"nome": ""})


def test_criar_fornecedor_nome_so_espacos_levanta_erro():
    with pytest.raises(ValueError, match="[Nn]ome"):
        fornecedor_service.criar_fornecedor({"nome": "   "})


def test_criar_fornecedor_valido_sem_documento():
    f = fornecedor_service.criar_fornecedor({"nome": "Distribuidora Sul", "documento": None})
    assert f.id is not None
    assert f.nome == "Distribuidora Sul"
    assert f.documento is None
    assert f.ativo is True


def test_criar_fornecedor_valido_com_todos_os_campos():
    dados = {
        "nome": "Papelaria Central",
        "documento": "12.345.678/0001-99",
        "telefone": "(51) 3333-4444",
        "email": "contato@papelaria.com",
        "observacoes": "Entrega às terças",
    }
    f = fornecedor_service.criar_fornecedor(dados)
    assert f.id is not None
    assert f.documento == "12.345.678/0001-99"
    assert f.email == "contato@papelaria.com"


def test_inativar_fornecedor_remove_da_listagem_ativa():
    f = fornecedor_service.criar_fornecedor({"nome": "Fornecedor Para Inativar"})

    fornecedor_service.inativar_fornecedor(f.id)

    ativos = fornecedor_service.listar_fornecedores(apenas_ativos=True)
    assert f.id not in [x.id for x in ativos]


def test_inativar_fornecedor_aparece_sem_filtro():
    f = fornecedor_service.criar_fornecedor({"nome": "Inativo Visível"})

    fornecedor_service.inativar_fornecedor(f.id)

    todos = fornecedor_service.listar_fornecedores(apenas_ativos=False)
    assert f.id in [x.id for x in todos]


def test_obter_fornecedor_inexistente_levanta_erro():
    with pytest.raises(FornecedorNaoEncontradoError):
        fornecedor_service.obter_fornecedor(99999)


def test_obter_fornecedor_existente_retorna_objeto():
    f = fornecedor_service.criar_fornecedor({"nome": "Fornecedor Buscado"})
    recuperado = fornecedor_service.obter_fornecedor(f.id)
    assert recuperado.id == f.id
    assert recuperado.nome == "Fornecedor Buscado"


def test_atualizar_fornecedor_campos_parciais():
    f = fornecedor_service.criar_fornecedor({"nome": "Nome Original", "telefone": "111"})

    atualizado = fornecedor_service.atualizar_fornecedor(f.id, {"telefone": "999"})

    assert atualizado.nome == "Nome Original"
    assert atualizado.telefone == "999"


def test_atualizar_fornecedor_inexistente_levanta_erro():
    with pytest.raises(FornecedorNaoEncontradoError):
        fornecedor_service.atualizar_fornecedor(99999, {"nome": "X"})


def test_inativar_fornecedor_inexistente_levanta_erro():
    with pytest.raises(FornecedorNaoEncontradoError):
        fornecedor_service.inativar_fornecedor(99999)


def test_listar_fornecedores_ordenado_por_nome():
    fornecedor_service.criar_fornecedor({"nome": "Zebra Distribuidora"})
    fornecedor_service.criar_fornecedor({"nome": "Alpha Suprimentos"})
    fornecedor_service.criar_fornecedor({"nome": "Mega Atacado"})

    lista = fornecedor_service.listar_fornecedores()
    nomes = [f.nome for f in lista]
    assert nomes == sorted(nomes)
