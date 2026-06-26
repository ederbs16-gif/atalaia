"""Smoke tests da UI do Dashboard."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

_DADOS_MOCK = {
    "vendas_hoje": {"total": 0, "valor": Decimal("0"), "ticket_medio": Decimal("0")},
    "caixa_status": {"aberto": False, "saldo_inicial": Decimal("0"), "total_vendas": Decimal("0")},
    "orcamentos_pendentes": {"abertos": 0, "vencendo_hoje": 0, "vencidos": 0},
    "estoque_baixo": {"count": 0, "itens": []},
    # listas detalhadas
    "contas_pagar_hoje":         [],
    "contas_pagar_semana":       [],
    "contas_receber_hoje_lista": [],
    "contas_receber_semana":     [],
    # totais
    "contas_vencer_hoje":   {"count": 0, "valor": Decimal("0")},
    "contas_vencer_semana": {"count": 0, "valor": Decimal("0")},
    "contas_receber_hoje":  {"count": 0, "valor": Decimal("0")},
}

_DADOS_COM_CONTAS = {
    **_DADOS_MOCK,
    "contas_pagar_hoje": [
        {"descricao": "Aluguel", "valor": Decimal("1200.00"), "status": "pendente"},
    ],
    "contas_pagar_semana": [
        {"descricao": "Energia", "vencimento": date.today(), "valor": Decimal("280.00"), "status": "pendente"},
    ],
    "contas_receber_hoje_lista": [
        {"descricao": "Serviços ABC", "valor": Decimal("240.00"), "status": "pendente"},
    ],
    "contas_receber_semana": [],
    "contas_vencer_hoje":   {"count": 1, "valor": Decimal("1200.00")},
    "contas_vencer_semana": {"count": 1, "valor": Decimal("280.00")},
    "contas_receber_hoje":  {"count": 1, "valor": Decimal("240.00")},
}


@pytest.fixture(autouse=True)
def patch_service(monkeypatch):
    import atalaia.modules.dashboard.service as svc
    monkeypatch.setattr(svc, "obter_dados_dashboard", lambda: _DADOS_MOCK)


def test_smoke_instancia(qtbot):
    from atalaia.modules.dashboard.ui.tela_dashboard import TelaDashboard
    w = TelaDashboard()
    qtbot.addWidget(w)
    assert w is not None


def test_timer_existe_e_ativo(qtbot):
    from atalaia.modules.dashboard.ui.tela_dashboard import TelaDashboard
    w = TelaDashboard()
    qtbot.addWidget(w)
    assert hasattr(w, "_timer")
    assert w._timer.isActive()
    assert w._timer.interval() == 5 * 60 * 1000


def test_botao_atualizar_chama_service(qtbot, monkeypatch):
    import atalaia.modules.dashboard.service as svc
    chamadas = []
    monkeypatch.setattr(svc, "obter_dados_dashboard",
                        lambda: (chamadas.append(1), _DADOS_MOCK)[1])

    from atalaia.modules.dashboard.ui.tela_dashboard import TelaDashboard
    w = TelaDashboard()
    qtbot.addWidget(w)

    chamadas.clear()
    from PySide6.QtWidgets import QPushButton
    btn = next(b for b in w.findChildren(QPushButton) if "Atualizar" in b.text())
    btn.click()

    assert len(chamadas) == 1


def test_card_contas_com_dados(qtbot, monkeypatch):
    import atalaia.modules.dashboard.service as svc
    monkeypatch.setattr(svc, "obter_dados_dashboard", lambda: _DADOS_COM_CONTAS)

    from atalaia.modules.dashboard.ui.tela_dashboard import TelaDashboard
    w = TelaDashboard()
    qtbot.addWidget(w)
    # Verifica que o resumo do card de pagar reflete 1 conta hoje
    assert "1" in w._v_pagar.text()


def test_card_contas_vazio_mostra_placeholder(qtbot):
    from atalaia.modules.dashboard.ui.tela_dashboard import TelaDashboard
    w = TelaDashboard()
    qtbot.addWidget(w)
    from PySide6.QtWidgets import QLabel
    labels = [l.text() for l in w.findChildren(QLabel)]
    assert any("Nenhuma" in t for t in labels)
