"""Testes das queries do módulo Relatórios."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, timedelta
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
from atalaia.db.models.pagamento_venda import PagamentoVenda
from atalaia.db.models.conta_pagar import ContaPagar, StatusContaEnum
from atalaia.db.models.pagamento_conta_pagar import PagamentoContaPagar, FormaPagamentoEnum
from atalaia.modules.relatorios import queries
from atalaia.modules.relatorios.periodo import calcular_periodo


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
def patch_session(SM, monkeypatch):
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

    monkeypatch.setattr(queries, "get_session", _session)

    yield

    with SM() as s:
        for t in [
            "pagamentos_conta_pagar", "contas_pagar",
            "pagamentos_venda", "itens_venda", "vendas",
            "produtos", "categorias", "clientes", "caixas",
        ]:
            s.execute(text(f"DELETE FROM {t}"))
        s.commit()


# ─── Fixtures de dados ────────────────────────────────────────────────────────

@pytest.fixture()
def cat_produto(SM):
    with SM() as s:
        cat = Categoria(nome="Cat Teste")
        s.add(cat)
        s.commit()
        s.refresh(cat)
        return cat.id


@pytest.fixture()
def produto_fisico(SM, cat_produto):
    with SM() as s:
        p = Produto(
            nome="Produto Teste",
            tipo=TipoEnum.produto,
            categoria_id=cat_produto,
            preco_venda=Decimal("50.00"),
            controla_estoque=True,
            estoque_atual=5,
            estoque_minimo=10,
        )
        s.add(p)
        s.commit()
        s.refresh(p)
        return p.id


@pytest.fixture()
def produto_ok(SM, cat_produto):
    with SM() as s:
        p = Produto(
            nome="Produto OK",
            tipo=TipoEnum.produto,
            categoria_id=cat_produto,
            preco_venda=Decimal("30.00"),
            controla_estoque=True,
            estoque_atual=20,
            estoque_minimo=5,
        )
        s.add(p)
        s.commit()
        s.refresh(p)
        return p.id


@pytest.fixture()
def venda_finalizada(SM, produto_fisico):
    with SM() as s:
        cli = Cliente(nome="Cliente Teste")
        s.add(cli)
        s.commit()
        s.refresh(cli)

        caixa = Caixa(
            hostname="test", saldo_inicial=Decimal("0"),
            total_dinheiro=Decimal("0"), total_pix=Decimal("0"),
            total_debito=Decimal("0"), total_credito=Decimal("0"),
            status=StatusCaixaEnum.aberto,
        )
        s.add(caixa)
        s.commit()
        s.refresh(caixa)

        v = Venda(
            status=StatusVendaEnum.finalizada,
            caixa_id=caixa.id,
            cliente_id=cli.id,
            desconto_percentual=Decimal("0"),
            total=Decimal("100.00"),
        )
        s.add(v)
        s.commit()
        s.refresh(v)

        item = ItemVenda(
            venda_id=v.id,
            produto_id=produto_fisico,
            quantidade=2,
            preco_unitario=Decimal("50.00"),
        )
        s.add(item)

        pag = PagamentoVenda(venda_id=v.id, forma="dinheiro", valor=Decimal("100.00"))
        s.add(pag)
        s.commit()
        return v.id


@pytest.fixture()
def conta_pagar_pendente(SM, engine):
    with SM() as s:
        conta = ContaPagar(
            descricao="Conta Teste",
            valor_total=Decimal("200.00"),
            valor_pago=Decimal("50.00"),
            status=StatusContaEnum.pago_parcialmente,
            vencimento=date.today() + timedelta(days=10),
        )
        s.add(conta)
        s.commit()
        s.refresh(conta)

        pag = PagamentoContaPagar(
            conta_pagar_id=conta.id,
            valor=Decimal("50.00"),
            forma_pagamento=FormaPagamentoEnum.pix,
            data_pagamento=date.today(),
        )
        s.add(pag)
        s.commit()
        return conta.id


# ─── Testes de calcular_periodo ───────────────────────────────────────────────

def test_calcular_periodo_diario():
    ini, fim = calcular_periodo("diario")
    hoje = date.today()
    assert ini == hoje
    assert fim == hoje


def test_calcular_periodo_semanal():
    ini, fim = calcular_periodo("semanal")
    hoje = date.today()
    assert fim == hoje
    assert ini == hoje - timedelta(days=6)


def test_calcular_periodo_mensal():
    ini, fim = calcular_periodo("mensal")
    hoje = date.today()
    assert fim == hoje
    assert ini == hoje.replace(day=1)


def test_calcular_periodo_personalizado():
    ini, fim = calcular_periodo("personalizado")
    assert ini is None
    assert fim is None


# ─── Testes de vendas_por_periodo ─────────────────────────────────────────────

def test_vendas_por_periodo_sem_dados():
    ini = date(2000, 1, 1)
    fim = date(2000, 1, 31)
    dados = queries.vendas_por_periodo(ini, fim)
    assert dados["total_vendas"] == 0
    assert dados["valor_liquido"] == Decimal("0")
    assert dados["agrupado_por_dia"] == []


def test_vendas_por_periodo_com_venda(venda_finalizada):
    ini = date.today() - timedelta(days=1)
    fim = date.today() + timedelta(days=1)
    dados = queries.vendas_por_periodo(ini, fim)
    assert dados["total_vendas"] >= 1
    assert dados["valor_liquido"] >= Decimal("100.00")


# ─── Testes de produtos_mais_vendidos ─────────────────────────────────────────

def test_produtos_mais_vendidos_sem_dados():
    ini = date(2000, 1, 1)
    fim = date(2000, 1, 31)
    dados = queries.produtos_mais_vendidos(ini, fim)
    assert dados == []


def test_produtos_mais_vendidos_ordenado(venda_finalizada):
    ini = date.today() - timedelta(days=1)
    fim = date.today() + timedelta(days=1)
    dados = queries.produtos_mais_vendidos(ini, fim)
    assert len(dados) >= 1
    assert dados[0]["quantidade_total"] >= 2
    if len(dados) > 1:
        assert dados[0]["quantidade_total"] >= dados[1]["quantidade_total"]


# ─── Testes de estoque_baixo ──────────────────────────────────────────────────

def test_estoque_baixo_inclui_produto_com_estoque_insuficiente(produto_fisico):
    dados = queries.estoque_baixo()
    ids_nomes = [d["nome"] for d in dados]
    assert "Produto Teste" in ids_nomes


def test_estoque_baixo_exclui_produto_com_estoque_ok(produto_ok):
    dados = queries.estoque_baixo()
    nomes = [d["nome"] for d in dados]
    assert "Produto OK" not in nomes


# ─── Testes de fluxo_de_caixa ─────────────────────────────────────────────────

def test_fluxo_de_caixa_sem_dados():
    ini = date(2000, 1, 1)
    fim = date(2000, 1, 31)
    dados = queries.fluxo_de_caixa(ini, fim)
    assert dados["entradas_total"] == Decimal("0")
    assert dados["saidas_total"] == Decimal("0")
    assert dados["saldo"] == Decimal("0")


def test_fluxo_de_caixa_soma_por_forma(venda_finalizada):
    ini = date.today() - timedelta(days=1)
    fim = date.today() + timedelta(days=1)
    dados = queries.fluxo_de_caixa(ini, fim)
    assert dados["por_forma"]["dinheiro"] >= Decimal("100.00")


def test_fluxo_de_caixa_saidas(conta_pagar_pendente):
    ini = date.today() - timedelta(days=1)
    fim = date.today() + timedelta(days=1)
    dados = queries.fluxo_de_caixa(ini, fim)
    assert dados["saidas_total"] >= Decimal("50.00")
