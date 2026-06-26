"""Testes de service do módulo Orçamentos."""
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
from atalaia.db.models.cliente import Cliente
from atalaia.db.models.produto import Produto, TipoEnum
from atalaia.db.models.orcamento import Orcamento, StatusOrcamentoEnum
from atalaia.modules.orcamentos import service
from atalaia.modules.orcamentos.exceptions import (
    OrcamentoJaFinalizadoError,
    OrcamentoVencidoError,
)
from atalaia.modules.clientes.exceptions import ClienteInativoError


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

    monkeypatch.setattr(service, "get_session", _session)
    yield
    with SM() as s:
        s.execute(text("DELETE FROM itens_venda"))
        s.execute(text("DELETE FROM vendas"))
        s.execute(text("DELETE FROM itens_orcamento"))
        s.execute(text("DELETE FROM orcamentos"))
        s.execute(text("DELETE FROM produtos"))
        s.execute(text("DELETE FROM categorias"))
        s.execute(text("DELETE FROM clientes"))
        s.commit()


@pytest.fixture()
def cliente_ativo(SM):
    with SM() as s:
        c = Cliente(nome="Cliente Teste", ativo=True)
        s.add(c)
        s.commit()
        s.refresh(c)
        return c.id


@pytest.fixture()
def cliente_inativo(SM):
    with SM() as s:
        c = Cliente(nome="Cliente Inativo", ativo=False)
        s.add(c)
        s.commit()
        s.refresh(c)
        return c.id


@pytest.fixture()
def produto_com_estoque(SM):
    with SM() as s:
        cat = Categoria(nome="Cat Orc")
        s.add(cat)
        s.commit()
        s.refresh(cat)
        p = Produto(
            nome="Produto Orc",
            tipo=TipoEnum.produto,
            categoria_id=cat.id,
            preco_venda=Decimal("50.00"),
            controla_estoque=True,
            estoque_atual=10,
        )
        s.add(p)
        s.commit()
        s.refresh(p)
        return p.id


@pytest.fixture()
def orcamento_aberto(cliente_ativo, produto_com_estoque):
    orc = service.criar_orcamento(cliente_id=cliente_ativo)
    service.adicionar_item(orc.id, produto_com_estoque, quantidade=2)
    return orc.id


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

def test_criar_orcamento_cliente_inativo_levanta_erro(cliente_inativo):
    with pytest.raises(ClienteInativoError):
        service.criar_orcamento(cliente_id=cliente_inativo)


def test_adicionar_item_congela_preco_vigente(SM, cliente_ativo, produto_com_estoque):
    orc = service.criar_orcamento(cliente_id=cliente_ativo)
    item = service.adicionar_item(orc.id, produto_com_estoque, quantidade=1)
    # preco_unitario deve ser o preco_venda (sem promoção ativa)
    assert item.preco_unitario == Decimal("50.00")


def test_aprovar_orcamento_muda_status_sem_criar_venda(SM, orcamento_aberto, produto_com_estoque):
    service.aprovar_orcamento(orcamento_aberto)

    with SM() as s:
        orc = s.get(Orcamento, orcamento_aberto)
        assert orc.status == StatusOrcamentoEnum.aprovado

    from atalaia.db.models.produto import Produto as P
    from atalaia.db.models.venda import Venda
    with SM() as s:
        p = s.get(P, produto_com_estoque)
        assert p.estoque_atual == 10  # estoque não é baixado

        vendas = s.query(Venda).filter(Venda.orcamento_id == orcamento_aberto).all()
        assert vendas == []  # nenhuma venda criada


def test_aprovar_orcamento_vencido_levanta_erro(SM, orcamento_aberto):
    with SM() as s:
        orc = s.get(Orcamento, orcamento_aberto)
        orc.data_validade = date.today() - timedelta(days=1)
        s.commit()
    with pytest.raises(OrcamentoVencidoError):
        service.aprovar_orcamento(orcamento_aberto)


def test_aprovar_orcamento_ja_aprovado_levanta_erro(SM, cliente_ativo, produto_com_estoque):
    orc = service.criar_orcamento(cliente_id=cliente_ativo)
    service.adicionar_item(orc.id, produto_com_estoque, quantidade=1)
    service.aprovar_orcamento(orc.id)
    with pytest.raises(OrcamentoJaFinalizadoError):
        service.aprovar_orcamento(orc.id)


def test_recusar_orcamento_nao_altera_estoque(SM, orcamento_aberto, produto_com_estoque):
    service.recusar_orcamento(orcamento_aberto)
    with SM() as s:
        from atalaia.db.models.produto import Produto as P
        p = s.get(P, produto_com_estoque)
        assert p.estoque_atual == 10  # inalterado
        orc = s.get(Orcamento, orcamento_aberto)
        assert orc.status == StatusOrcamentoEnum.recusado
