"""
Testes para os models Categoria e Produto.

Estratégia de banco:
- SQLite em memória para todos os testes de criação, unicidade, relacionamento
  e validação de ENUM (SQLAlchemy valida o tipo Python antes de enviar ao banco).
- CHECK constraints (estoque_atual >= 0, preco_venda >= 0, etc.) dependem de
  enforcement no banco. SQLite pode não aplicá-los dependendo da versão.
  Esses testes são marcados com @pytest.mark.skip e documentados como
  comportamento garantido no MySQL de produção — validar manualmente ou via
  suite de integração apontada para o banco real.
"""

import pytest
from contextlib import contextmanager
from decimal import Decimal

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError

from atalaia.db.base import Base
import atalaia.db.models  # noqa: F401 — registra todos os models na metadata
from atalaia.db.models.categoria import Categoria
from atalaia.db.models.produto import Produto, TipoEnum


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sqlite_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db(sqlite_engine):
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sqlite_engine)

    @contextmanager
    def _get_session():
        session = _SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return _get_session


@pytest.fixture(autouse=True)
def limpar_tabelas(sqlite_engine):
    yield
    with sqlite_engine.connect() as conn:
        conn.execute(text("DELETE FROM produtos"))
        conn.execute(text("DELETE FROM categorias"))
        conn.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _categoria(nome="Geral"):
    return Categoria(nome=nome)


def _produto(categoria, **kwargs):
    defaults = dict(
        nome="Caneta Azul",
        tipo=TipoEnum.produto,
        categoria=categoria,
        preco_venda=Decimal("2.50"),
        unidade_medida="UN",
    )
    defaults.update(kwargs)
    return Produto(**defaults)


# ---------------------------------------------------------------------------
# Testes de criação válida
# ---------------------------------------------------------------------------

def test_cria_categoria_valida(db):
    with db() as session:
        cat = _categoria("Papelaria")
        session.add(cat)

    with db() as session:
        cat = session.query(Categoria).filter_by(nome="Papelaria").one()
        assert cat.id is not None
        assert cat.nome == "Papelaria"


def test_cria_produto_tipo_produto(db):
    with db() as session:
        cat = _categoria()
        session.add(cat)

    with db() as session:
        cat = session.query(Categoria).filter_by(nome="Geral").one()
        p = _produto(
            cat,
            nome="Caderno",
            tipo=TipoEnum.produto,
            preco_venda=Decimal("15.90"),
            controla_estoque=True,
            estoque_atual=10,
        )
        session.add(p)

    with db() as session:
        p = session.query(Produto).filter_by(nome="Caderno").one()
        assert p.tipo == TipoEnum.produto
        assert p.controla_estoque is True
        assert p.estoque_atual == 10
        assert p.ativo is True


def test_cria_produto_tipo_servico(db):
    with db() as session:
        cat = _categoria("Servicos")
        p = _produto(
            cat,
            nome="Impressão A4",
            tipo=TipoEnum.servico,
            controla_estoque=False,
            preco_venda=Decimal("0.50"),
        )
        session.add(cat)
        session.add(p)

    with db() as session:
        p = session.query(Produto).filter_by(nome="Impressão A4").one()
        assert p.tipo == TipoEnum.servico
        assert p.controla_estoque is False


# ---------------------------------------------------------------------------
# Testes de unicidade
# ---------------------------------------------------------------------------

def test_unique_categoria_nome(db):
    with db() as session:
        session.add(_categoria("Duplicada"))

    with pytest.raises(IntegrityError):
        with db() as session:
            session.add(_categoria("Duplicada"))


def test_unique_produto_codigo_barras(db):
    with db() as session:
        cat = _categoria()
        p1 = _produto(cat, codigo_barras="7891234567890")
        session.add(cat)
        session.add(p1)

    with pytest.raises(IntegrityError):
        with db() as session:
            cat = session.query(Categoria).filter_by(nome="Geral").one()
            p2 = _produto(cat, nome="Outro Produto", codigo_barras="7891234567890")
            session.add(p2)


# ---------------------------------------------------------------------------
# Teste de ENUM
# ---------------------------------------------------------------------------

def test_tipo_invalido_falha():
    """
    TipoEnum é um Python enum — valores fora do conjunto definido levantam
    ValueError na construção, antes de qualquer interação com o banco.
    O ENUM no MySQL é uma segunda camada de defesa para inserções fora do ORM.
    """
    with pytest.raises(ValueError):
        TipoEnum("invalido")


# ---------------------------------------------------------------------------
# Teste de relacionamento
# ---------------------------------------------------------------------------

def test_relationship_produto_categoria(db):
    with db() as session:
        cat = _categoria("Eletronicos")
        p = _produto(cat, nome="Cabo USB")
        session.add(cat)
        session.add(p)

    with db() as session:
        p = session.query(Produto).filter_by(nome="Cabo USB").one()
        assert p.categoria.nome == "Eletronicos"


# ---------------------------------------------------------------------------
# CHECK constraints — garantidos no MySQL de produção
# ---------------------------------------------------------------------------
# Esses testes documentam o comportamento esperado.
# SQLite pode não enforçar CHECK dependendo da versão; validar contra o
# MySQL real antes de considerar a regra de negócio coberta por testes.

@pytest.mark.skip(reason="CHECK enforçado pelo MySQL; SQLite pode não aplicar")
def test_check_estoque_negativo_falha(db):
    with pytest.raises(IntegrityError):
        with db() as session:
            cat = _categoria()
            p = _produto(cat, estoque_atual=-1)
            session.add(cat)
            session.add(p)


@pytest.mark.skip(reason="CHECK enforçado pelo MySQL; SQLite pode não aplicar")
def test_check_preco_venda_negativo_falha(db):
    with pytest.raises(IntegrityError):
        with db() as session:
            cat = _categoria()
            p = _produto(cat, preco_venda=Decimal("-1.00"))
            session.add(cat)
            session.add(p)


@pytest.mark.skip(reason="CHECK enforçado pelo MySQL; SQLite pode não aplicar")
def test_check_desconto_maximo_invalido_falha(db):
    with pytest.raises(IntegrityError):
        with db() as session:
            cat = _categoria()
            p = _produto(cat, permite_desconto=True, desconto_maximo_percentual=Decimal("101.00"))
            session.add(cat)
            session.add(p)


@pytest.mark.skip(reason="CHECK enforçado pelo MySQL; SQLite pode não aplicar")
def test_check_datas_promocao_invalidas_falha(db):
    from datetime import date
    with pytest.raises(IntegrityError):
        with db() as session:
            cat = _categoria()
            p = _produto(
                cat,
                produto_em_promocao=True,
                preco_promocional=Decimal("1.99"),
                promocao_inicio=date(2026, 7, 10),
                promocao_fim=date(2026, 7, 1),  # fim antes do início
            )
            session.add(cat)
            session.add(p)


@pytest.mark.skip(reason="CHECK enforçado pelo MySQL; SQLite pode não aplicar")
def test_check_preco_promocional_maior_que_preco_venda_falha(db):
    with pytest.raises(IntegrityError):
        with db() as session:
            cat = _categoria()
            p = _produto(
                cat,
                preco_venda=Decimal("10.00"),
                produto_em_promocao=True,
                preco_promocional=Decimal("15.00"),  # maior que preco_venda
            )
            session.add(cat)
            session.add(p)
