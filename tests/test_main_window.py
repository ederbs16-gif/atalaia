"""Smoke tests da MainWindow."""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt


@pytest.fixture(autouse=True)
def patch_services(monkeypatch):
    import atalaia.modules.produtos.service as ps
    import atalaia.modules.clientes.service as cs
    import atalaia.modules.entrada_mercadorias.fornecedor_service as fs
    import atalaia.modules.entrada_mercadorias.entrada_service as es

    monkeypatch.setattr(ps, "listar_categorias", lambda: [])
    monkeypatch.setattr(ps, "listar_produtos", lambda *a, **kw: [])
    monkeypatch.setattr(ps, "buscar_produtos_por_termo", lambda *a, **kw: [])
    monkeypatch.setattr(cs, "buscar_clientes_por_termo", lambda *a, **kw: [])
    monkeypatch.setattr(fs, "buscar_fornecedores_por_termo", lambda *a, **kw: [])
    monkeypatch.setattr(fs, "listar_fornecedores", lambda *a, **kw: [])
    monkeypatch.setattr(es, "listar_entradas", lambda *a, **kw: [])

    import atalaia.modules.orcamentos.service as ors
    monkeypatch.setattr(ors, "listar_orcamentos", lambda *a, **kw: [])


def test_main_window_instancia_sem_erro(qtbot):
    from atalaia.ui.main_window import MainWindow
    w = MainWindow()
    qtbot.addWidget(w)
    assert w is not None


def test_clique_produtos_abre_tela_produtos(qtbot):
    from atalaia.ui.main_window import MainWindow
    from atalaia.modules.produtos.ui.tela_produtos import TelaProdutos
    w = MainWindow()
    qtbot.addWidget(w)
    qtbot.mouseClick(w.btn_produtos, Qt.LeftButton)
    assert isinstance(w._stack.currentWidget(), TelaProdutos)


def test_clique_fornecedores_abre_tela_fornecedores(qtbot):
    from atalaia.ui.main_window import MainWindow
    from atalaia.modules.entrada_mercadorias.ui.tela_fornecedores import TelaFornecedores
    w = MainWindow()
    qtbot.addWidget(w)
    qtbot.mouseClick(w.btn_fornecedores, Qt.LeftButton)
    assert isinstance(w._stack.currentWidget(), TelaFornecedores)


def test_clique_entradas_abre_tela_entradas(qtbot):
    from atalaia.ui.main_window import MainWindow
    from atalaia.modules.entrada_mercadorias.ui.tela_entradas import TelaEntradas
    w = MainWindow()
    qtbot.addWidget(w)
    qtbot.mouseClick(w.btn_entradas, Qt.LeftButton)
    assert isinstance(w._stack.currentWidget(), TelaEntradas)


def test_botao_sair_existe_no_sidebar(qtbot):
    from atalaia.ui.main_window import MainWindow
    w = MainWindow()
    qtbot.addWidget(w)
    assert hasattr(w, "btn_sair")
    assert not w.btn_sair.isHidden()
