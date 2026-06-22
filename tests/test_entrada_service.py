"""
Testes da camada de serviço de Entrada de Mercadorias.

Usa SQLite em memória com monkeypatch de get_session no módulo entrada_service,
mesmo padrão de test_fornecedor.py.
"""

from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from atalaia.db.base import Base
import atalaia.db.models  # noqa: F401 — registra todos os models na metadata
from atalaia.db.models.categoria import Categoria
from atalaia.db.models.fornecedor import Fornecedor
from atalaia.db.models.produto import Produto, TipoEnum
from atalaia.modules.entrada_mercadorias import entrada_service
from atalaia.modules.entrada_mercadorias.exceptions import (
    EntradaJaConfirmadaError,
    FornecedorInativoError,
)


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


@pytest.fixture()
def SM(engine):
    return sessionmaker(bind=engine, autocommit=False, autoflush=False)


@pytest.fixture(autouse=True)
def patch_and_clean(engine, SM, monkeypatch):
    @contextmanager
    def _test_session():
        s = SM()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    monkeypatch.setattr(entrada_service, "get_session", _test_session)

    yield

    with engine.connect() as conn:
        conn.execute(text("DELETE FROM itens_entrada"))
        conn.execute(text("DELETE FROM entradas_mercadorias"))
        conn.execute(text("DELETE FROM produtos"))
        conn.execute(text("DELETE FROM categorias"))
        conn.execute(text("DELETE FROM fornecedores"))
        conn.commit()


@pytest.fixture()
def categoria(SM):
    with SM() as s:
        cat = Categoria(nome="Geral")
        s.add(cat)
        s.commit()
        s.refresh(cat)
        return cat.id


@pytest.fixture()
def fornecedor_ativo(SM):
    with SM() as s:
        f = Fornecedor(nome="Fornecedor Ativo", ativo=True)
        s.add(f)
        s.commit()
        s.refresh(f)
        return f.id


@pytest.fixture()
def fornecedor_inativo(SM):
    with SM() as s:
        f = Fornecedor(nome="Fornecedor Inativo", ativo=False)
        s.add(f)
        s.commit()
        s.refresh(f)
        return f.id


def _criar_produto(SM, categoria_id: int, preco_custo=None, estoque=0) -> int:
    with SM() as s:
        p = Produto(
            nome="Produto Teste",
            tipo=TipoEnum.produto,
            categoria_id=categoria_id,
            preco_venda=Decimal("20.00"),
            preco_custo=Decimal(str(preco_custo)) if preco_custo is not None else None,
            controla_estoque=True,
            estoque_atual=estoque,
        )
        s.add(p)
        s.commit()
        s.refresh(p)
        return p.id


def _obter_produto(engine, produto_id: int) -> dict:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT estoque_atual, preco_custo, preco_custo_anterior, custo_medio"
                " FROM produtos WHERE id = :id"
            ),
            {"id": produto_id},
        ).fetchone()
    return {
        "estoque_atual": row[0],
        "preco_custo": Decimal(str(row[1])) if row[1] is not None else None,
        "preco_custo_anterior": Decimal(str(row[2])) if row[2] is not None else None,
        "custo_medio": Decimal(str(row[3])) if row[3] is not None else None,
    }


# ---------------------------------------------------------------------------
# Testes
# ---------------------------------------------------------------------------

def test_criar_entrada_fornecedor_inativo_levanta_erro(fornecedor_inativo):
    with pytest.raises(FornecedorInativoError):
        entrada_service.criar_entrada(fornecedor_id=fornecedor_inativo)


def test_adicionar_item_quantidade_zero_levanta_valor_erro(SM, categoria, fornecedor_ativo):
    produto_id = _criar_produto(SM, categoria)
    entrada = entrada_service.criar_entrada(fornecedor_id=fornecedor_ativo)
    with pytest.raises(ValueError, match="quantidade"):
        entrada_service.adicionar_item(
            entrada_id=entrada.id,
            produto_id=produto_id,
            quantidade=0,
            custo_unitario=Decimal("5.00"),
        )


def test_adicionar_item_quantidade_negativa_levanta_valor_erro(SM, categoria, fornecedor_ativo):
    produto_id = _criar_produto(SM, categoria)
    entrada = entrada_service.criar_entrada(fornecedor_id=fornecedor_ativo)
    with pytest.raises(ValueError, match="quantidade"):
        entrada_service.adicionar_item(
            entrada_id=entrada.id,
            produto_id=produto_id,
            quantidade=-1,
            custo_unitario=Decimal("5.00"),
        )


def test_adicionar_item_em_entrada_confirmada_levanta_erro(SM, engine, categoria, fornecedor_ativo):
    produto_id = _criar_produto(SM, categoria, estoque=5)
    entrada = entrada_service.criar_entrada(fornecedor_id=fornecedor_ativo)
    entrada_service.adicionar_item(
        entrada_id=entrada.id,
        produto_id=produto_id,
        quantidade=1,
        custo_unitario=Decimal("10.00"),
    )
    entrada_service.confirmar_entrada(entrada.id)

    with pytest.raises(EntradaJaConfirmadaError):
        entrada_service.adicionar_item(
            entrada_id=entrada.id,
            produto_id=produto_id,
            quantidade=1,
            custo_unitario=Decimal("10.00"),
        )


def test_confirmar_entrada_atualiza_estoque_e_custo(SM, engine, categoria, fornecedor_ativo):
    produto_id = _criar_produto(SM, categoria, preco_custo=Decimal("10.00"), estoque=5)

    entrada = entrada_service.criar_entrada(fornecedor_id=fornecedor_ativo)
    entrada_service.adicionar_item(
        entrada_id=entrada.id,
        produto_id=produto_id,
        quantidade=3,
        custo_unitario=Decimal("8.00"),
    )
    entrada_service.confirmar_entrada(entrada.id)

    p = _obter_produto(engine, produto_id)
    assert p["estoque_atual"] == 8
    assert p["preco_custo"] == Decimal("8.00")
    assert p["preco_custo_anterior"] == Decimal("10.00")
    assert p["custo_medio"] == Decimal("9.00")

    with engine.connect() as conn:
        status = conn.execute(
            text("SELECT status FROM entradas_mercadorias WHERE id = :id"),
            {"id": entrada.id},
        ).scalar()
    assert status == "confirmada"


def test_confirmar_entrada_primeiro_custo_null(SM, engine, categoria, fornecedor_ativo):
    produto_id = _criar_produto(SM, categoria, preco_custo=None, estoque=0)

    entrada = entrada_service.criar_entrada(fornecedor_id=fornecedor_ativo)
    entrada_service.adicionar_item(
        entrada_id=entrada.id,
        produto_id=produto_id,
        quantidade=10,
        custo_unitario=Decimal("15.00"),
    )
    entrada_service.confirmar_entrada(entrada.id)

    p = _obter_produto(engine, produto_id)
    assert p["preco_custo"] == Decimal("15.00")
    assert p["preco_custo_anterior"] is None
    assert p["custo_medio"] == Decimal("15.00")


def test_confirmar_entrada_duas_vezes_levanta_erro(SM, engine, categoria, fornecedor_ativo):
    produto_id = _criar_produto(SM, categoria, estoque=10)

    entrada = entrada_service.criar_entrada(fornecedor_id=fornecedor_ativo)
    entrada_service.adicionar_item(
        entrada_id=entrada.id,
        produto_id=produto_id,
        quantidade=2,
        custo_unitario=Decimal("5.00"),
    )
    entrada_service.confirmar_entrada(entrada.id)

    with pytest.raises(EntradaJaConfirmadaError):
        entrada_service.confirmar_entrada(entrada.id)
