"""Smoke tests de UI do módulo Clientes."""
from __future__ import annotations

from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from atalaia.db.base import Base
import atalaia.db.models  # noqa: F401

from atalaia.db.models.cliente import Cliente
from atalaia.modules.clientes import service


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


@pytest.fixture()
def cliente_existente(SM):
    with SM() as s:
        c = Cliente(nome="Fernanda Teste", telefone="99999-0000", documento="111.222.333-44", ativo=True)
        s.add(c)
        s.commit()
        s.refresh(c)
        return c.id


# ---------------------------------------------------------------------------
# Smoke tests
# ---------------------------------------------------------------------------

def test_smoke_tela_clientes(qtbot):
    from atalaia.modules.clientes.ui.tela_clientes import TelaClientes
    tela = TelaClientes()
    qtbot.addWidget(tela)
    assert tela.combo_status.count() == 3
    assert tela.combo_status.itemText(0) == "Ativos"


def test_smoke_formulario_cliente_criacao(qtbot):
    from atalaia.modules.clientes.ui.formulario_cliente import FormularioCliente
    dlg = FormularioCliente()
    qtbot.addWidget(dlg)
    assert dlg._cliente_id is None
    assert dlg.txt_nome.text() == ""


def test_smoke_formulario_cliente_edicao_campos_preenchidos(qtbot, cliente_existente):
    from atalaia.modules.clientes.ui.formulario_cliente import FormularioCliente
    dlg = FormularioCliente(cliente_id=cliente_existente)
    qtbot.addWidget(dlg)
    assert dlg.txt_nome.text() == "Fernanda Teste"
    assert dlg.txt_telefone.text() == "99999-0000"
    assert dlg.txt_documento.text() == "111.222.333-44"
