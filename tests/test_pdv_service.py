"""Testes de service do módulo PDV."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from atalaia.db.base import Base
import atalaia.db.models  # noqa: F401

from atalaia.db.models.categoria import Categoria
from atalaia.db.models.produto import Produto, TipoEnum
from atalaia.db.models.cliente import Cliente
from atalaia.db.models.caixa import Caixa, StatusCaixaEnum
from atalaia.db.models.venda import Venda, ItemVenda, StatusVendaEnum
from atalaia.modules.pdv import venda_service
from atalaia.modules.pdv.exceptions import (
    VendaJaFinalizadaError,
    PagamentoInsuficienteError,
    DescontoInvalidoError,
    DevolucaoInvalidaError,
)
from atalaia.modules.financeiro.exceptions import CaixaNaoAbertoError
from atalaia.modules.produtos.exceptions import EstoqueInsuficienteError


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

    monkeypatch.setattr(venda_service, "get_session", _session)

    yield

    with SM() as s:
        for tabela in [
            "itens_devolucao", "devolucoes", "pagamentos_venda",
            "itens_venda", "vendas", "produtos", "categorias", "clientes", "caixas",
        ]:
            s.execute(text(f"DELETE FROM {tabela}"))
        s.commit()


@pytest.fixture()
def caixa_aberto(SM):
    with SM() as s:
        c = Caixa(
            hostname="test-host",
            saldo_inicial=Decimal("0"),
            total_dinheiro=Decimal("0"),
            total_pix=Decimal("0"),
            total_debito=Decimal("0"),
            total_credito=Decimal("0"),
            status=StatusCaixaEnum.aberto,
        )
        s.add(c)
        s.commit()
        s.refresh(c)
        return c


@pytest.fixture()
def mock_caixa_aberto(caixa_aberto, monkeypatch):
    monkeypatch.setattr(venda_service.caixa_service, "obter_caixa_aberto", lambda: caixa_aberto)
    monkeypatch.setattr(venda_service.caixa_service, "registrar_pagamento_caixa", lambda *a, **kw: None)
    return caixa_aberto


@pytest.fixture()
def produto_com_estoque(SM):
    with SM() as s:
        cat = Categoria(nome="Cat PDV")
        s.add(cat)
        s.commit()
        s.refresh(cat)
        p = Produto(
            nome="Produto PDV",
            tipo=TipoEnum.produto,
            categoria_id=cat.id,
            preco_venda=Decimal("37.00"),
            controla_estoque=True,
            estoque_atual=10,
            permite_desconto=True,
            desconto_maximo_percentual=Decimal("50"),
        )
        s.add(p)
        s.commit()
        s.refresh(p)
        return p.id


@pytest.fixture()
def produto_substituto(SM):
    with SM() as s:
        cat = Categoria(nome="Cat Sub")
        s.add(cat)
        s.commit()
        s.refresh(cat)
        p = Produto(
            nome="Produto Substituto",
            tipo=TipoEnum.produto,
            categoria_id=cat.id,
            preco_venda=Decimal("40.00"),
            controla_estoque=True,
            estoque_atual=5,
        )
        s.add(p)
        s.commit()
        s.refresh(p)
        return p.id


@pytest.fixture()
def venda_aberta(mock_caixa_aberto):
    venda = venda_service.iniciar_venda()
    return venda.id


@pytest.fixture()
def venda_com_item(venda_aberta, produto_com_estoque):
    venda_service.adicionar_item(venda_aberta, produto_com_estoque, quantidade=2)
    return venda_aberta


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

def test_iniciar_venda_sem_caixa_levanta_erro(monkeypatch):
    monkeypatch.setattr(venda_service.caixa_service, "obter_caixa_aberto", lambda: None)
    with pytest.raises(CaixaNaoAbertoError):
        venda_service.iniciar_venda()


def test_adicionar_item_congela_preco_vigente(SM, venda_aberta, produto_com_estoque):
    item = venda_service.adicionar_item(venda_aberta, produto_com_estoque, quantidade=1)
    assert item.preco_unitario == Decimal("37.00")


def test_aplicar_desconto_por_valor(SM, venda_com_item):
    venda = venda_service.aplicar_desconto(venda_com_item, valor=Decimal("5.00"))
    # subtotal = 2 * 37 = 74; pct = 5/74 * 100 ≈ 6.76
    assert venda.desconto_percentual > 0
    totais = venda_service.calcular_totais(venda_com_item)
    assert abs(totais["desconto_valor"] - Decimal("5.00")) < Decimal("0.02")


def test_aplicar_desconto_por_percentual(SM, venda_com_item):
    venda_service.aplicar_desconto(venda_com_item, percentual=Decimal("5.00"))
    totais = venda_service.calcular_totais(venda_com_item)
    # subtotal = 74; 5% = 3.70
    assert abs(totais["desconto_valor"] - Decimal("3.70")) < Decimal("0.02")


def test_finalizar_venda_ok(SM, venda_com_item, produto_com_estoque, mock_caixa_aberto):
    venda_service.adicionar_pagamento(venda_com_item, "dinheiro", Decimal("80.00"))
    venda = venda_service.finalizar_venda(venda_com_item)

    assert venda.status == StatusVendaEnum.finalizada
    assert venda.forma_pagamento_principal == "dinheiro"

    with SM() as s:
        p = s.get(Produto, produto_com_estoque)
        assert p.estoque_atual == 8  # 10 - 2


def test_finalizar_venda_pagamento_insuficiente(SM, venda_com_item):
    venda_service.adicionar_pagamento(venda_com_item, "pix", Decimal("10.00"))
    with pytest.raises(PagamentoInsuficienteError):
        venda_service.finalizar_venda(venda_com_item)


def test_cancelar_venda_finalizada_levanta_erro(SM, venda_com_item, mock_caixa_aberto):
    venda_service.adicionar_pagamento(venda_com_item, "dinheiro", Decimal("80.00"))
    venda_service.finalizar_venda(venda_com_item)
    with pytest.raises(VendaJaFinalizadaError):
        venda_service.cancelar_venda(venda_com_item)


def test_registrar_devolucao_troca(SM, venda_com_item, produto_com_estoque, produto_substituto, mock_caixa_aberto):
    venda_service.adicionar_pagamento(venda_com_item, "dinheiro", Decimal("80.00"))
    venda_service.finalizar_venda(venda_com_item)

    with SM() as s:
        estoque_antes = s.get(Produto, produto_com_estoque).estoque_atual
        estoque_sub_antes = s.get(Produto, produto_substituto).estoque_atual

    venda_service.registrar_devolucao(
        venda_com_item,
        itens=[{"produto_id": produto_com_estoque, "quantidade": 1, "produto_substituto_id": produto_substituto}],
        tipo="troca",
        motivo="Produto com defeito",
    )

    with SM() as s:
        assert s.get(Produto, produto_com_estoque).estoque_atual == estoque_antes + 1
        assert s.get(Produto, produto_substituto).estoque_atual == estoque_sub_antes - 1


def test_registrar_devolucao_quantidade_invalida(SM, venda_com_item, produto_com_estoque, mock_caixa_aberto):
    venda_service.adicionar_pagamento(venda_com_item, "dinheiro", Decimal("80.00"))
    venda_service.finalizar_venda(venda_com_item)

    with pytest.raises(DevolucaoInvalidaError):
        venda_service.registrar_devolucao(
            venda_com_item,
            itens=[{"produto_id": produto_com_estoque, "quantidade": 99}],
            tipo="reembolso",
            motivo="Teste",
            forma_reembolso="dinheiro",
        )
