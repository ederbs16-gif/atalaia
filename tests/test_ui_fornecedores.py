"""
Testes de UI e service de Fornecedores.

Smoke tests para TelaFornecedores e FormularioFornecedor,
mais testes unitários de buscar_fornecedores_por_termo.
"""
from __future__ import annotations

from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from atalaia.db.base import Base
import atalaia.db.models  # noqa: F401

from atalaia.db.models.fornecedor import Fornecedor
from atalaia.modules.entrada_mercadorias import fornecedor_service


# ---------------------------------------------------------------------------
# Fixtures de banco
# ---------------------------------------------------------------------------

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

    monkeypatch.setattr(fornecedor_service, "get_session", _session)

    yield

    with SM() as s:
        s.execute(text("DELETE FROM fornecedores"))
        s.commit()


@pytest.fixture()
def fornecedor_ativo(SM):
    with SM() as s:
        f = Fornecedor(nome="Papelaria Central", documento="12.345.678/0001-99", ativo=True)
        s.add(f)
        s.commit()
        s.refresh(f)
        return f.id


@pytest.fixture()
def fornecedor_inativo(SM):
    with SM() as s:
        f = Fornecedor(nome="Distribuidora Velha", documento="98.765.432/0001-11", ativo=False)
        s.add(f)
        s.commit()
        s.refresh(f)
        return f.id


# ---------------------------------------------------------------------------
# Smoke tests de UI (pytest-qt)
# ---------------------------------------------------------------------------

def test_smoke_tela_fornecedores(qtbot):
    from atalaia.modules.entrada_mercadorias.ui.tela_fornecedores import TelaFornecedores
    tela = TelaFornecedores()
    qtbot.addWidget(tela)
    assert tela.combo_status.count() == 3
    assert tela.combo_status.itemText(0) == "Ativos"


def test_smoke_formulario_fornecedor_criacao(qtbot):
    from atalaia.modules.entrada_mercadorias.ui.formulario_fornecedor import FormularioFornecedor
    dlg = FormularioFornecedor()
    qtbot.addWidget(dlg)
    assert dlg._fornecedor_id is None
    assert dlg.txt_nome.text() == ""


def test_smoke_formulario_fornecedor_edicao_campos_preenchidos(qtbot, fornecedor_ativo):
    from atalaia.modules.entrada_mercadorias.ui.formulario_fornecedor import FormularioFornecedor
    dlg = FormularioFornecedor(fornecedor_id=fornecedor_ativo)
    qtbot.addWidget(dlg)
    assert dlg.txt_nome.text() == "Papelaria Central"
    assert dlg.txt_documento.text() == "12.345.678/0001-99"


# ---------------------------------------------------------------------------
# Testes unitários de buscar_fornecedores_por_termo
# ---------------------------------------------------------------------------

def test_buscar_por_nome_retorna_fornecedor(fornecedor_ativo):
    resultado = fornecedor_service.buscar_fornecedores_por_termo("central")
    assert any(f.id == fornecedor_ativo for f in resultado)


def test_buscar_por_documento_retorna_fornecedor(fornecedor_ativo):
    resultado = fornecedor_service.buscar_fornecedores_por_termo("12.345")
    assert any(f.id == fornecedor_ativo for f in resultado)


def test_buscar_sem_correspondencia_retorna_lista_vazia():
    resultado = fornecedor_service.buscar_fornecedores_por_termo("xyzxyzxyz")
    assert resultado == []


def test_buscar_apenas_ativos_false_inclui_inativos(fornecedor_ativo, fornecedor_inativo):
    resultado = fornecedor_service.buscar_fornecedores_por_termo("", apenas_ativos=False)
    ids = [f.id for f in resultado]
    assert fornecedor_ativo in ids
    assert fornecedor_inativo in ids
