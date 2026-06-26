"""Smoke tests da UI do módulo Financeiro."""
from __future__ import annotations

from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from atalaia.db.base import Base
import atalaia.db.models  # noqa: F401

from atalaia.modules.financeiro import caixa_service, contas_service
from atalaia.modules.entrada_mercadorias import fornecedor_service
from atalaia.modules.clientes import service as cliente_service


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

    monkeypatch.setattr(caixa_service, "get_session", _session)
    monkeypatch.setattr(contas_service, "get_session", _session)
    monkeypatch.setattr(fornecedor_service, "get_session", _session)
    monkeypatch.setattr(cliente_service, "get_session", _session)


def test_smoke_tela_financeiro(qtbot):
    from atalaia.modules.financeiro.ui.tela_financeiro import TelaFinanceiro
    tela = TelaFinanceiro()
    qtbot.addWidget(tela)
    assert tela.tabWidget.count() == 3


def test_smoke_dialogo_abrir_caixa(qtbot):
    from atalaia.modules.financeiro.ui.dialogo_abrir_caixa import DialogoAbrirCaixa
    dlg = DialogoAbrirCaixa()
    qtbot.addWidget(dlg)
    assert dlg.spin_saldo is not None


def test_smoke_formulario_conta_pagar_e_receber(qtbot):
    from atalaia.modules.financeiro.ui.formulario_conta import FormularioConta
    dlg_pagar = FormularioConta(modo="pagar")
    qtbot.addWidget(dlg_pagar)
    assert hasattr(dlg_pagar, "combo_fornecedor")

    dlg_receber = FormularioConta(modo="receber")
    qtbot.addWidget(dlg_receber)
    assert hasattr(dlg_receber, "combo_cliente")
