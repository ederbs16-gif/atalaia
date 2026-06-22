"""
Testes da camada de serviço do módulo Produtos.

Todos os testes usam SQLite em memória. O monkeypatch redireciona get_session()
no módulo service para uma session SQLite, mantendo os testes isolados do
MySQL de produção e sem dependência de servidor externo.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from atalaia.db.base import Base
import atalaia.db.models  # noqa: F401
from atalaia.db.models.produto import TipoEnum
from atalaia.modules.produtos.exceptions import (
    CategoriaNaoEncontradaError,
    CodigoBarrasDuplicadoError,
    DescontoExcedeLimiteError,
    DescontoMaximoForaDoIntervaloError,
    DescontoNaoPermitidoError,
    EstoqueInsuficienteError,
    PromocaoInvalidaError,
)
from atalaia.modules.produtos import service


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
    """Redireciona get_session do service para SQLite e limpa tabelas após cada teste."""
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

def _nova_categoria(nome="Geral"):
    return service.criar_categoria(nome)


def _novo_produto(categoria_id, **kwargs):
    defaults = dict(
        nome="Caneta Azul",
        tipo=TipoEnum.produto,
        categoria_id=categoria_id,
        preco_venda=Decimal("2.50"),
        unidade_medida="UN",
        controla_estoque=True,
        estoque_atual=10,
    )
    defaults.update(kwargs)
    return service.criar_produto(defaults)


# ---------------------------------------------------------------------------
# criar_produto
# ---------------------------------------------------------------------------

def test_criar_produto_tipo_produto():
    cat = _nova_categoria()
    p = _novo_produto(cat.id, nome="Caderno", estoque_atual=5)
    assert p.id is not None
    assert p.tipo == TipoEnum.produto
    assert p.controla_estoque is True
    assert p.estoque_atual == 5


def test_criar_produto_tipo_servico():
    cat = _nova_categoria()
    p = service.criar_produto({
        "nome": "Impressão A4",
        "tipo": TipoEnum.servico,
        "categoria_id": cat.id,
        "preco_venda": Decimal("0.50"),
        "unidade_medida": "UN",
        "controla_estoque": False,
    })
    assert p.tipo == TipoEnum.servico
    assert p.controla_estoque is False


def test_criar_produto_categoria_inexistente():
    with pytest.raises(CategoriaNaoEncontradaError):
        service.criar_produto({
            "nome": "X",
            "tipo": TipoEnum.produto,
            "categoria_id": 99999,
            "preco_venda": Decimal("1.00"),
            "unidade_medida": "UN",
        })


def test_criar_produto_servico_normaliza_controla_estoque():
    """controla_estoque=True com tipo=servico deve ser normalizado para False."""
    cat = _nova_categoria()
    p = service.criar_produto({
        "nome": "Suporte TI",
        "tipo": TipoEnum.servico,
        "categoria_id": cat.id,
        "preco_venda": Decimal("150.00"),
        "unidade_medida": "UN",
        "controla_estoque": True,  # será normalizado para False
    })
    assert p.controla_estoque is False


# ---------------------------------------------------------------------------
# dar_baixa_estoque
# ---------------------------------------------------------------------------

def test_baixa_estoque_suficiente(engine):
    cat = _nova_categoria()
    p = _novo_produto(cat.id, estoque_atual=5)

    service.dar_baixa_estoque(p.id, 3)

    with engine.connect() as conn:
        atual = conn.execute(
            text("SELECT estoque_atual FROM produtos WHERE id = :id"), {"id": p.id}
        ).scalar()
    assert atual == 2


def test_baixa_estoque_insuficiente_levanta_erro_e_nao_altera(engine):
    cat = _nova_categoria()
    p = _novo_produto(cat.id, estoque_atual=2)

    with pytest.raises(EstoqueInsuficienteError):
        service.dar_baixa_estoque(p.id, 5)

    with engine.connect() as conn:
        atual = conn.execute(
            text("SELECT estoque_atual FROM produtos WHERE id = :id"), {"id": p.id}
        ).scalar()
    assert atual == 2  # estoque não foi alterado


def test_baixa_estoque_sem_controle_nao_levanta_erro(engine):
    """Produto com controla_estoque=False (serviço): dar_baixa não faz nada e não levanta erro."""
    cat = _nova_categoria()
    p = service.criar_produto({
        "nome": "Xerox",
        "tipo": TipoEnum.servico,
        "categoria_id": cat.id,
        "preco_venda": Decimal("0.25"),
        "unidade_medida": "UN",
        "controla_estoque": False,
    })

    service.dar_baixa_estoque(p.id, 100)  # não deve levantar

    with engine.connect() as conn:
        atual = conn.execute(
            text("SELECT estoque_atual FROM produtos WHERE id = :id"), {"id": p.id}
        ).scalar()
    assert atual == 0  # permanece 0 (padrão); não foi alterado


def test_simulacao_concorrencia(engine):
    """
    Com estoque_atual=2, duas chamadas sequenciais de dar_baixa_estoque(id, 2)
    sem recarregar o objeto Produto em memória entre elas simulam duas sessões
    concorrentes lendo o mesmo estado inicial.

    A segunda chamada deve falhar com EstoqueInsuficienteError, comprovando que
    o UPDATE atômico (WHERE estoque_atual >= qtd) impede a venda dupla mesmo
    sem re-leitura do objeto em Python.
    """
    cat = _nova_categoria()
    p = _novo_produto(cat.id, estoque_atual=2)

    # Primeira "sessão": sucesso
    service.dar_baixa_estoque(p.id, 2)

    # Segunda "sessão": o objeto Python ainda tem estoque_atual=2 em memória,
    # mas o banco tem 0 — o UPDATE atômico rejeita
    with pytest.raises(EstoqueInsuficienteError):
        service.dar_baixa_estoque(p.id, 2)

    with engine.connect() as conn:
        atual = conn.execute(
            text("SELECT estoque_atual FROM produtos WHERE id = :id"), {"id": p.id}
        ).scalar()
    assert atual == 0


# ---------------------------------------------------------------------------
# obter_preco_vigente
# ---------------------------------------------------------------------------

def _produto_com_promocao(cat_id, inicio, fim, preco=Decimal("10.00"), promo=Decimal("7.00")):
    return service.criar_produto({
        "nome": "Prod Promo",
        "tipo": TipoEnum.produto,
        "categoria_id": cat_id,
        "preco_venda": preco,
        "unidade_medida": "UN",
        "produto_em_promocao": True,
        "preco_promocional": promo,
        "promocao_inicio": inicio,
        "promocao_fim": fim,
    })


def test_preco_vigente_dentro_do_periodo():
    cat = _nova_categoria()
    p = _produto_com_promocao(cat.id, date(2026, 6, 1), date(2026, 6, 30))
    assert service.obter_preco_vigente(p, date(2026, 6, 15)) == Decimal("7.00")


def test_preco_vigente_no_limite_inicio():
    cat = _nova_categoria()
    p = _produto_com_promocao(cat.id, date(2026, 6, 1), date(2026, 6, 30))
    assert service.obter_preco_vigente(p, date(2026, 6, 1)) == Decimal("7.00")


def test_preco_vigente_no_limite_fim():
    cat = _nova_categoria()
    p = _produto_com_promocao(cat.id, date(2026, 6, 1), date(2026, 6, 30))
    assert service.obter_preco_vigente(p, date(2026, 6, 30)) == Decimal("7.00")


def test_preco_vigente_antes_do_periodo():
    cat = _nova_categoria()
    p = _produto_com_promocao(cat.id, date(2026, 6, 1), date(2026, 6, 30))
    assert service.obter_preco_vigente(p, date(2026, 5, 31)) == Decimal("10.00")


def test_preco_vigente_depois_do_periodo():
    cat = _nova_categoria()
    p = _produto_com_promocao(cat.id, date(2026, 6, 1), date(2026, 6, 30))
    assert service.obter_preco_vigente(p, date(2026, 7, 1)) == Decimal("10.00")


def test_preco_vigente_promocao_false_ignora_datas():
    cat = _nova_categoria()
    p = service.criar_produto({
        "nome": "Sem Promo",
        "tipo": TipoEnum.produto,
        "categoria_id": cat.id,
        "preco_venda": Decimal("10.00"),
        "unidade_medida": "UN",
        "produto_em_promocao": False,
        "preco_promocional": Decimal("7.00"),
        "promocao_inicio": date(2026, 6, 1),
        "promocao_fim": date(2026, 6, 30),
    })
    assert service.obter_preco_vigente(p, date(2026, 6, 15)) == Decimal("10.00")


# ---------------------------------------------------------------------------
# validar_desconto
# ---------------------------------------------------------------------------

def test_desconto_dentro_do_limite():
    cat = _nova_categoria()
    p = _novo_produto(
        cat.id,
        permite_desconto=True,
        desconto_maximo_percentual=Decimal("10.00"),
    )
    service.validar_desconto(p, Decimal("10.00"))  # não deve levantar


def test_desconto_excede_limite():
    cat = _nova_categoria()
    p = _novo_produto(
        cat.id,
        permite_desconto=True,
        desconto_maximo_percentual=Decimal("10.00"),
    )
    with pytest.raises(DescontoExcedeLimiteError):
        service.validar_desconto(p, Decimal("10.01"))


def test_desconto_nao_permitido():
    cat = _nova_categoria()
    p = _novo_produto(cat.id, permite_desconto=False)
    with pytest.raises(DescontoNaoPermitidoError):
        service.validar_desconto(p, Decimal("5.00"))


def test_desconto_zero_sempre_passa():
    cat = _nova_categoria()
    p = _novo_produto(cat.id, permite_desconto=False)
    service.validar_desconto(p, Decimal("0"))  # não deve levantar


# ---------------------------------------------------------------------------
# inativar_produto + listar_produtos
# ---------------------------------------------------------------------------

def test_inativar_produto_some_da_listagem():
    cat = _nova_categoria()
    p = _novo_produto(cat.id, nome="Para Inativar")

    service.inativar_produto(p.id)

    ativos = service.listar_produtos(apenas_ativos=True)
    ids_ativos = [x.id for x in ativos]
    assert p.id not in ids_ativos


def test_inativar_produto_aparece_sem_filtro():
    cat = _nova_categoria()
    p = _novo_produto(cat.id, nome="Inativo Visivel")

    service.inativar_produto(p.id)

    todos = service.listar_produtos(apenas_ativos=False)
    ids_todos = [x.id for x in todos]
    assert p.id in ids_todos


# ---------------------------------------------------------------------------
# CodigoBarrasDuplicadoError + restrição de estoque_atual
# ---------------------------------------------------------------------------

def test_criar_produto_codigo_barras_duplicado():
    cat = _nova_categoria()
    _novo_produto(cat.id, nome="Produto A", codigo_barras="BAR-001")

    with pytest.raises(CodigoBarrasDuplicadoError) as exc_info:
        _novo_produto(cat.id, nome="Produto B", codigo_barras="BAR-001")

    assert "BAR-001" in str(exc_info.value)


def test_atualizar_produto_codigo_barras_duplicado():
    cat = _nova_categoria()
    _novo_produto(cat.id, nome="Produto A", codigo_barras="BAR-002")
    p2 = _novo_produto(cat.id, nome="Produto B", codigo_barras="BAR-003")

    with pytest.raises(CodigoBarrasDuplicadoError) as exc_info:
        service.atualizar_produto(p2.id, {"codigo_barras": "BAR-002"})

    assert "BAR-002" in str(exc_info.value)


def test_atualizar_produto_estoque_atual_proibido(engine):
    cat = _nova_categoria()
    p = _novo_produto(cat.id, estoque_atual=10)

    with pytest.raises(ValueError, match="estoque_atual"):
        service.atualizar_produto(p.id, {"estoque_atual": 99})

    with engine.connect() as conn:
        atual = conn.execute(
            text("SELECT estoque_atual FROM produtos WHERE id = :id"), {"id": p.id}
        ).scalar()
    assert atual == 10  # valor original preservado


# ---------------------------------------------------------------------------
# DescontoMaximoForaDoIntervaloError + PromocaoInvalidaError
# ---------------------------------------------------------------------------

def test_criar_produto_desconto_maximo_fora_intervalo():
    cat = _nova_categoria()
    with pytest.raises(DescontoMaximoForaDoIntervaloError) as exc_info:
        _novo_produto(
            cat.id,
            nome="Desc Inválido",
            permite_desconto=True,
            desconto_maximo_percentual=Decimal("150.00"),
        )
    assert "150" in str(exc_info.value)

    # nada persistido
    assert service.listar_produtos(apenas_ativos=False) == []


def test_atualizar_produto_desconto_maximo_fora_intervalo(engine):
    cat = _nova_categoria()
    p = _novo_produto(cat.id, desconto_maximo_percentual=Decimal("10.00"))

    with pytest.raises(DescontoMaximoForaDoIntervaloError):
        service.atualizar_produto(p.id, {"desconto_maximo_percentual": Decimal("-5.00")})

    with engine.connect() as conn:
        valor = conn.execute(
            text("SELECT desconto_maximo_percentual FROM produtos WHERE id = :id"),
            {"id": p.id},
        ).scalar()
    assert Decimal(str(valor)) == Decimal("10.00")  # original preservado


def test_criar_produto_promocao_datas_invertidas():
    cat = _nova_categoria()
    with pytest.raises(PromocaoInvalidaError, match="ata"):
        service.criar_produto({
            "nome": "Promo Datas",
            "tipo": TipoEnum.produto,
            "categoria_id": cat.id,
            "preco_venda": Decimal("10.00"),
            "unidade_medida": "UN",
            "produto_em_promocao": True,
            "preco_promocional": Decimal("8.00"),
            "promocao_inicio": date(2026, 6, 30),
            "promocao_fim": date(2026, 6, 1),
        })
    assert service.listar_produtos(apenas_ativos=False) == []


def test_atualizar_produto_promocao_datas_invertidas(engine):
    cat = _nova_categoria()
    p = _produto_com_promocao(cat.id, date(2026, 6, 1), date(2026, 6, 30))

    # atualização parcial: muda só promocao_fim para antes do início existente
    with pytest.raises(PromocaoInvalidaError, match="ata"):
        service.atualizar_produto(p.id, {"promocao_fim": date(2026, 5, 1)})

    with engine.connect() as conn:
        fim = conn.execute(
            text("SELECT promocao_fim FROM produtos WHERE id = :id"), {"id": p.id}
        ).scalar()
    assert str(fim) == "2026-06-30"  # original preservado


def test_criar_produto_preco_promocional_maior_que_venda():
    cat = _nova_categoria()
    with pytest.raises(PromocaoInvalidaError, match="romocional"):
        service.criar_produto({
            "nome": "Promo Preço",
            "tipo": TipoEnum.produto,
            "categoria_id": cat.id,
            "preco_venda": Decimal("10.00"),
            "unidade_medida": "UN",
            "produto_em_promocao": True,
            "preco_promocional": Decimal("15.00"),
        })
    assert service.listar_produtos(apenas_ativos=False) == []


def test_atualizar_produto_preco_promocional_maior_que_venda(engine):
    cat = _nova_categoria()
    p = _novo_produto(cat.id, preco_venda=Decimal("10.00"))

    # atualização parcial: define preço promocional acima do preço de venda existente
    with pytest.raises(PromocaoInvalidaError, match="romocional"):
        service.atualizar_produto(p.id, {"preco_promocional": Decimal("12.00")})

    with engine.connect() as conn:
        promo = conn.execute(
            text("SELECT preco_promocional FROM produtos WHERE id = :id"), {"id": p.id}
        ).scalar()
    assert promo is None  # nada foi gravado
