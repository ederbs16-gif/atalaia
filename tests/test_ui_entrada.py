"""
Smoke tests da UI de Entrada de Mercadorias.

Usa SQLite em memória com monkeypatch de get_session nos módulos de service,
mesmo padrão dos outros testes de UI do projeto.
"""
from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from atalaia.db.base import Base
import atalaia.db.models  # noqa: F401

from atalaia.db.models.categoria import Categoria
from atalaia.db.models.fornecedor import Fornecedor
from atalaia.db.models.produto import Produto, TipoEnum
from atalaia.modules.entrada_mercadorias import entrada_service, fornecedor_service
from atalaia.modules.entrada_mercadorias.exceptions import EntradaJaConfirmadaError


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

    monkeypatch.setattr(entrada_service, "get_session", _session)
    monkeypatch.setattr(fornecedor_service, "get_session", _session)

    yield

    with SM() as s:
        s.execute(text("DELETE FROM itens_entrada"))
        s.execute(text("DELETE FROM entradas_mercadorias"))
        s.execute(text("DELETE FROM produtos"))
        s.execute(text("DELETE FROM categorias"))
        s.execute(text("DELETE FROM fornecedores"))
        s.commit()


@pytest.fixture()
def fornecedor(SM):
    with SM() as s:
        f = Fornecedor(nome="Fornecedor UI", ativo=True)
        s.add(f)
        s.commit()
        s.refresh(f)
        return f.id


@pytest.fixture()
def entrada_confirmada(SM, fornecedor):
    from datetime import date
    with SM() as s:
        cat = Categoria(nome="Cat UI")
        s.add(cat)
        s.commit()
        s.refresh(cat)
        p = Produto(
            nome="Prod UI",
            tipo=TipoEnum.produto,
            categoria_id=cat.id,
            preco_venda=Decimal("10.00"),
            controla_estoque=True,
            estoque_atual=10,
        )
        s.add(p)
        s.commit()
        s.refresh(p)
        produto_id = p.id

    entrada = entrada_service.criar_entrada(fornecedor_id=fornecedor)
    entrada_service.adicionar_item(
        entrada_id=entrada.id,
        produto_id=produto_id,
        quantidade=2,
        custo_unitario=Decimal("5.00"),
    )
    entrada_service.confirmar_entrada(entrada.id)
    return entrada.id


# ---------------------------------------------------------------------------
# Testes de service (sem UI)
# ---------------------------------------------------------------------------

def test_excluir_rascunho_confirmado_levanta_erro(entrada_confirmada):
    with pytest.raises(EntradaJaConfirmadaError):
        entrada_service.excluir_rascunho(entrada_confirmada)


# ---------------------------------------------------------------------------
# Smoke tests de UI (pytest-qt)
# ---------------------------------------------------------------------------

def test_smoke_tela_entradas(qtbot, fornecedor):
    from atalaia.modules.entrada_mercadorias.ui.tela_entradas import TelaEntradas
    tela = TelaEntradas()
    qtbot.addWidget(tela)
    assert tela.combo_status.count() == 3
    assert tela.combo_fornecedor.count() >= 2  # "Todos" + ao menos 1 fornecedor


def test_smoke_formulario_entrada_criacao(qtbot):
    from atalaia.modules.entrada_mercadorias.ui.formulario_entrada import FormularioEntrada
    dlg = FormularioEntrada()
    qtbot.addWidget(dlg)
    assert dlg._entrada_id is None
    assert not dlg._grp_itens.isEnabled()


def test_smoke_formulario_entrada_confirmada(qtbot, entrada_confirmada):
    from atalaia.modules.entrada_mercadorias.ui.formulario_entrada import FormularioEntrada
    dlg = FormularioEntrada(entrada_id=entrada_confirmada)
    qtbot.addWidget(dlg)
    assert dlg._modo_readonly is True
    assert not dlg._lbl_readonly.isHidden()
    assert not dlg._grp_itens.isEnabled()
    assert not dlg.btn_salvar_cabecalho.isEnabled()
