"""
Testes do FormularioProduto e DialogoCategoria (pytest-qt).

Mesmo padrão de isolamento de test_tela_produtos.py: SQLite em memória com
monkeypatch de get_session no módulo service. Como o formulário e o diálogo
acessam o banco apenas via service, monkeypatchar service.get_session cobre
todos os caminhos.
"""

from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal

import pytest
from PySide6.QtWidgets import QDialog, QMessageBox
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from atalaia.db.base import Base
import atalaia.db.models  # noqa: F401
from atalaia.db.models.produto import TipoEnum
from atalaia.modules.produtos import service
from atalaia.modules.produtos.ui import formulario_produto as fp_mod
from atalaia.modules.produtos.ui.dialogo_categoria import DialogoCategoria
from atalaia.modules.produtos.ui.formulario_produto import FormularioProduto


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

    monkeypatch.setattr(service, "get_session", _test_session)

    yield

    with engine.connect() as conn:
        conn.execute(text("DELETE FROM produtos"))
        conn.execute(text("DELETE FROM categorias"))
        conn.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _preencher_minimo(form, cat_id, nome="Produto X", preco="9.90", barcode=None):
    form.txt_nome.setText(nome)
    idx = form.combo_categoria.findData(cat_id)
    form.combo_categoria.setCurrentIndex(idx)
    form.txt_preco_venda.setText(preco)
    if barcode:
        form.txt_codigo_barras.setText(barcode)


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

def test_criar_smoke_combo_populado(qtbot):
    service.criar_categoria("Papelaria")
    service.criar_categoria("Eletrônicos")

    form = FormularioProduto()
    qtbot.addWidget(form)

    assert form.combo_categoria.count() == 2
    nomes = {form.combo_categoria.itemText(i) for i in range(form.combo_categoria.count())}
    assert {"Papelaria", "Eletrônicos"} == nomes


def test_editar_preenche_campos_e_substitui_estoque_inicial(qtbot):
    cat = service.criar_categoria("Geral")
    p = service.criar_produto({
        "nome": "Caderno",
        "tipo": TipoEnum.produto,
        "categoria_id": cat.id,
        "preco_venda": Decimal("12.50"),
        "unidade_medida": "UN",
        "estoque_atual": 7,
        "codigo_barras": "ABC-1",
    })

    form = FormularioProduto(produto_id=p.id)
    qtbot.addWidget(form)

    assert form.txt_nome.text() == "Caderno"
    assert form.txt_preco_venda.text() == "12.50"
    assert form.txt_codigo_barras.text() == "ABC-1"
    # Estoque Inicial substituído pelo label read-only no modo Editar
    assert "7" in form.lbl_estoque_atual.text()
    assert form.spin_estoque_inicial.parent() is None  # nunca adicionado ao layout


def test_tipo_servico_desabilita_e_desmarca_controla_estoque(qtbot):
    service.criar_categoria("Serviços")

    form = FormularioProduto()
    qtbot.addWidget(form)

    assert form.chk_controla_estoque.isChecked() is True
    assert form.chk_controla_estoque.isEnabled() is True

    idx_servico = form.combo_tipo.findData(TipoEnum.servico)
    form.combo_tipo.setCurrentIndex(idx_servico)

    assert form.chk_controla_estoque.isChecked() is False
    assert form.chk_controla_estoque.isEnabled() is False


def test_salvar_criar_persiste_e_fecha(qtbot):
    cat = service.criar_categoria("Geral")

    form = FormularioProduto()
    qtbot.addWidget(form)
    _preencher_minimo(form, cat.id, nome="Lápis", preco="1.50")

    form._salvar()

    assert form.produto_salvo() is True
    assert form.result() == QDialog.Accepted

    produtos = service.listar_produtos(apenas_ativos=False)
    assert any(p.nome == "Lápis" for p in produtos)


def test_salvar_codigo_barras_duplicado_mantem_aberto(qtbot, monkeypatch):
    cat = service.criar_categoria("Geral")
    service.criar_produto({
        "nome": "Existente",
        "tipo": TipoEnum.produto,
        "categoria_id": cat.id,
        "preco_venda": Decimal("5.00"),
        "unidade_medida": "UN",
        "codigo_barras": "DUP-1",
    })

    avisos = []
    monkeypatch.setattr(
        fp_mod.QMessageBox,
        "warning",
        lambda *args, **kwargs: avisos.append(args),
    )

    form = FormularioProduto()
    qtbot.addWidget(form)
    _preencher_minimo(form, cat.id, nome="Novo", preco="3.00", barcode="DUP-1")

    form._salvar()

    assert form.produto_salvo() is False
    assert len(avisos) == 1
    # a mensagem (último arg posicional) menciona o código em conflito
    assert "DUP-1" in avisos[0][-1]


def test_criar_categoria_via_dialogo_atualiza_combo_e_seleciona(qtbot, monkeypatch):
    service.criar_categoria("Inicial")

    form = FormularioProduto()
    qtbot.addWidget(form)
    assert form.combo_categoria.count() == 1

    def fake_exec(dlg):
        dlg.txt_nome.setText("Recém Criada")
        dlg._salvar()  # cria via service real e chama accept()
        return QDialog.Accepted

    monkeypatch.setattr(fp_mod.DialogoCategoria, "exec", fake_exec, raising=False)

    form._abrir_dialogo_categoria()

    assert form.combo_categoria.count() == 2
    # a categoria recém-criada deve estar selecionada
    assert form.combo_categoria.currentText() == "Recém Criada"
