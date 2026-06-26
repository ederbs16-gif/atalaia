"""Testes do service de dashboard."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from atalaia.modules.dashboard import service

# ── helpers de mock ──────────────────────────────────────────────────────────

_VENDAS_ROW   = MagicMock(fetchone=lambda: (2, Decimal("300.00")))
_CAIXA_NONE   = MagicMock(fetchone=lambda: None)
_ORC_ROW      = MagicMock(fetchone=lambda: (0, 0, 0))
_EST_ROWS     = MagicMock(fetchall=lambda: [])
_CP_HOJE_ROWS = MagicMock(fetchall=lambda: [])
_CP_SEM_ROWS  = MagicMock(fetchall=lambda: [])
_CR_HOJE_ROWS = MagicMock(fetchall=lambda: [])
_CR_SEM_ROWS  = MagicMock(fetchall=lambda: [])


def _mock_session_factory(**overrides):
    defaults = {
        "vendas":      _VENDAS_ROW,
        "caixa":       _CAIXA_NONE,
        "orc":         _ORC_ROW,
        "est_rows":    _EST_ROWS,
        "est_count":   0,          # int → .scalar()
        "cp_hoje":     _CP_HOJE_ROWS,
        "cp_semana":   _CP_SEM_ROWS,
        "cr_hoje":     _CR_HOJE_ROWS,
        "cr_semana":   _CR_SEM_ROWS,
    }
    defaults.update(overrides)

    # Ordem das queries em obter_dados_dashboard():
    # 0 vendas, 1 caixa, 2 orc, 3 est_rows, 4 est_count(scalar),
    # 5 cp_hoje, 6 cp_semana, 7 cr_hoje, 8 cr_semana
    order_keys = ["vendas", "caixa", "orc", "est_rows", "est_count",
                  "cp_hoje", "cp_semana", "cr_hoje", "cr_semana"]
    calls = [0]

    def _execute(stmt, *a, **kw):
        n = calls[0]
        calls[0] += 1
        src = defaults[order_keys[n]] if n < len(order_keys) else MagicMock()
        mock = MagicMock()
        if isinstance(src, int):
            mock.scalar.return_value = src
        else:
            mock.fetchone = src.fetchone if hasattr(src, "fetchone") else lambda: src
            mock.fetchall = src.fetchall if hasattr(src, "fetchall") else lambda: []
        return mock

    session = MagicMock()
    session.execute.side_effect = _execute

    @contextmanager
    def _get_session():
        yield session

    return _get_session


# ── testes ───────────────────────────────────────────────────────────────────

def test_retorna_todas_as_chaves():
    with patch("atalaia.modules.dashboard.service.get_session", _mock_session_factory()):
        dados = service.obter_dados_dashboard()

    chaves = {"vendas_hoje", "caixa_status", "orcamentos_pendentes", "estoque_baixo",
              "contas_pagar_hoje", "contas_pagar_semana",
              "contas_receber_hoje_lista", "contas_receber_semana",
              "contas_vencer_hoje", "contas_vencer_semana", "contas_receber_hoje"}
    assert chaves.issubset(dados.keys())


def test_vendas_hoje_subchaves():
    with patch("atalaia.modules.dashboard.service.get_session", _mock_session_factory()):
        dados = service.obter_dados_dashboard()
    v = dados["vendas_hoje"]
    assert "total" in v and "valor" in v and "ticket_medio" in v


def test_sem_vendas_retorna_zeros():
    zero = MagicMock(fetchone=lambda: (0, Decimal("0")))
    with patch("atalaia.modules.dashboard.service.get_session",
               _mock_session_factory(vendas=zero)):
        dados = service.obter_dados_dashboard()
    assert dados["vendas_hoje"]["total"] == 0
    assert dados["vendas_hoje"]["ticket_medio"] == Decimal("0")


def test_estoque_baixo_no_maximo_5_itens():
    rows = [("P1", 0, 5, 5), ("P2", 1, 5, 4), ("P3", 2, 5, 3),
            ("P4", 3, 5, 2), ("P5", 4, 5, 1)]
    est_mock = MagicMock(fetchall=lambda: rows)
    with patch("atalaia.modules.dashboard.service.get_session",
               _mock_session_factory(est_rows=est_mock, est_count=5)):
        dados = service.obter_dados_dashboard()
    assert len(dados["estoque_baixo"]["itens"]) <= 5


def test_contas_pagar_hoje_lista_vazia_por_padrao():
    with patch("atalaia.modules.dashboard.service.get_session", _mock_session_factory()):
        dados = service.obter_dados_dashboard()
    assert dados["contas_pagar_hoje"] == []
    assert dados["contas_vencer_hoje"]["count"] == 0
    assert dados["contas_vencer_hoje"]["valor"] == Decimal("0")


def test_contas_pagar_hoje_preenche_lista():
    rows = [("Aluguel", Decimal("1200.00"), "pendente")]
    mock = MagicMock(fetchall=lambda: rows)
    with patch("atalaia.modules.dashboard.service.get_session",
               _mock_session_factory(cp_hoje=mock)):
        dados = service.obter_dados_dashboard()
    lista = dados["contas_pagar_hoje"]
    assert len(lista) == 1
    assert lista[0]["descricao"] == "Aluguel"
    assert lista[0]["valor"] == Decimal("1200.00")
    assert dados["contas_vencer_hoje"]["count"] == 1


def test_contas_receber_lista_vazia_por_padrao():
    with patch("atalaia.modules.dashboard.service.get_session", _mock_session_factory()):
        dados = service.obter_dados_dashboard()
    assert dados["contas_receber_hoje_lista"] == []
    assert dados["contas_receber_semana"] == []
