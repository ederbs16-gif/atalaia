"""Smoke tests da UI do módulo Relatórios."""
from __future__ import annotations

from datetime import date, timedelta

import pytest


@pytest.fixture(autouse=True)
def patch_queries(monkeypatch):
    import atalaia.modules.relatorios.queries as q

    monkeypatch.setattr(q, "vendas_por_periodo", lambda *a, **kw: {
        "total_vendas": 0, "valor_bruto": 0, "valor_desconto": 0,
        "valor_liquido": 0, "ticket_medio": 0, "agrupado_por_dia": [],
    })
    monkeypatch.setattr(q, "produtos_mais_vendidos", lambda *a, **kw: [])
    monkeypatch.setattr(q, "estoque_baixo", lambda: [])
    monkeypatch.setattr(q, "fluxo_de_caixa", lambda *a, **kw: {
        "entradas_total": 0, "saidas_total": 0, "saldo": 0,
        "por_forma": {"dinheiro": 0, "pix": 0, "debito": 0, "credito": 0},
        "por_dia": [],
    })
    monkeypatch.setattr(q, "contas_a_pagar_receber", lambda *a, **kw: {
        "pagar": {"total_pendente": 0, "total_vencido": 0, "total_pago": 0, "itens": []},
        "receber": {"total_pendente": 0, "total_vencido": 0, "total_pago": 0, "itens": []},
    })


def test_smoke_tela_relatorios(qtbot):
    from atalaia.modules.relatorios.ui.tela_relatorios import TelaRelatorios
    w = TelaRelatorios()
    qtbot.addWidget(w)
    assert w is not None


def test_smoke_cinco_abas(qtbot):
    from atalaia.modules.relatorios.ui.tela_relatorios import TelaRelatorios
    w = TelaRelatorios()
    qtbot.addWidget(w)
    assert w.tabWidget.count() == 5


def test_gerar_vendas_periodo_vazio_sem_excecao(qtbot):
    from atalaia.modules.relatorios.ui.tela_relatorios import TelaRelatorios
    w = TelaRelatorios()
    qtbot.addWidget(w)
    w.tabWidget.setCurrentIndex(0)
    w._aba_vendas.gerar()
    assert w._aba_vendas._model.rowCount() == 0
