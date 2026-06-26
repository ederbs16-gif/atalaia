"""Smoke tests da UI do módulo PDV."""
from __future__ import annotations

from decimal import Decimal

import pytest


@pytest.fixture(autouse=True)
def patch_pdv(monkeypatch):
    import atalaia.modules.pdv.venda_service as vs
    import atalaia.modules.financeiro.caixa_service as cxs
    from atalaia.db.models.caixa import Caixa, StatusCaixaEnum

    caixa_mock = Caixa(id=1, hostname="test", status=StatusCaixaEnum.aberto,
                       saldo_inicial=Decimal("0"), total_dinheiro=Decimal("0"),
                       total_pix=Decimal("0"), total_debito=Decimal("0"),
                       total_credito=Decimal("0"))

    monkeypatch.setattr(cxs, "obter_caixa_aberto", lambda: caixa_mock)
    monkeypatch.setattr(vs, "iniciar_venda", lambda *a, **kw: _venda_mock())
    monkeypatch.setattr(vs, "obter_venda", lambda *a, **kw: _venda_mock())
    monkeypatch.setattr(vs, "calcular_totais", lambda *a, **kw: {
        "subtotal": Decimal("0"), "desconto_percentual": Decimal("0"),
        "desconto_valor": Decimal("0"), "total": Decimal("0"),
        "total_pago": Decimal("0"), "troco": Decimal("0"), "falta_pagar": Decimal("0"),
    })
    monkeypatch.setattr(vs, "listar_vendas", lambda *a, **kw: [])

    import atalaia.modules.orcamentos.service as ors
    monkeypatch.setattr(ors, "listar_orcamentos", lambda *a, **kw: [])


def _venda_mock():
    from unittest.mock import MagicMock
    v = MagicMock()
    v.id = 1
    v.cliente = None
    v.itens = []
    v.pagamentos = []
    v.devolucoes = []
    v.desconto_percentual = Decimal("0")
    v.total = Decimal("0")
    v.caixa_id = 1
    return v


def test_smoke_tela_pdv(qtbot):
    from atalaia.modules.pdv.ui.tela_pdv import TelaPDV
    w = TelaPDV()
    qtbot.addWidget(w)
    assert w._venda_id == 1
    assert w.btn_finalizar is not None


def test_smoke_dialogo_importar_orcamento(qtbot):
    from atalaia.modules.pdv.ui.dialogo_importar_orcamento import DialogoImportarOrcamento
    dlg = DialogoImportarOrcamento()
    qtbot.addWidget(dlg)
    assert dlg.tabela is not None


def test_smoke_dialogo_devolucao(qtbot):
    from atalaia.modules.pdv.ui.dialogo_devolucao import DialogoDevolucao
    dlg = DialogoDevolucao()
    qtbot.addWidget(dlg)
    assert dlg.spin_venda_id is not None


def test_sincronizacao_desconto_rs_e_pct(qtbot, monkeypatch):
    import atalaia.modules.pdv.venda_service as vs
    monkeypatch.setattr(vs, "calcular_totais", lambda *a, **kw: {
        "subtotal": Decimal("37.00"), "desconto_percentual": Decimal("0"),
        "desconto_valor": Decimal("0"), "total": Decimal("37.00"),
        "total_pago": Decimal("0"), "troco": Decimal("0"), "falta_pagar": Decimal("37.00"),
    })
    from atalaia.modules.pdv.ui.tela_pdv import TelaPDV
    w = TelaPDV()
    qtbot.addWidget(w)

    w.spin_desconto_rs.setValue(5.00)
    pct = w.spin_desconto_pct.value()
    assert abs(pct - (5.00 / 37.00 * 100)) < 0.1
