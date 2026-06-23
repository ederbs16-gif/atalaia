"""Smoke tests da UI de Orçamentos."""
from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from atalaia.db.base import Base
import atalaia.db.models  # noqa: F401

from atalaia.db.models.categoria import Categoria
from atalaia.db.models.cliente import Cliente
from atalaia.db.models.produto import Produto, TipoEnum
from atalaia.modules.orcamentos import service
from atalaia.modules.clientes import service as cliente_service
from atalaia.modules.produtos import service as produto_service


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
def patch_services(SM, monkeypatch):
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
    monkeypatch.setattr(cliente_service, "get_session", _session)
    monkeypatch.setattr(produto_service, "get_session", _session)

    yield

    with SM() as s:
        s.execute(text("DELETE FROM itens_venda"))
        s.execute(text("DELETE FROM vendas"))
        s.execute(text("DELETE FROM itens_orcamento"))
        s.execute(text("DELETE FROM orcamentos"))
        s.execute(text("DELETE FROM produtos"))
        s.execute(text("DELETE FROM categorias"))
        s.execute(text("DELETE FROM clientes"))
        s.commit()


@pytest.fixture()
def cliente(SM):
    with SM() as s:
        c = Cliente(nome="Cliente UI Orc", ativo=True)
        s.add(c)
        s.commit()
        s.refresh(c)
        return c.id


def test_smoke_tela_orcamentos(qtbot):
    from atalaia.modules.orcamentos.ui.tela_orcamentos import TelaOrcamentos
    tela = TelaOrcamentos()
    qtbot.addWidget(tela)
    assert tela.combo_status.count() >= 2


def test_smoke_formulario_orcamento_criacao(qtbot, cliente):
    from atalaia.modules.orcamentos.ui.formulario_orcamento import FormularioOrcamento
    dlg = FormularioOrcamento()
    qtbot.addWidget(dlg)
    assert dlg._orc_id is None
    assert not dlg._grp_itens.isEnabled()
    assert dlg.combo_cliente.count() >= 1
