"""
Testes da tela de listagem de produtos e da função buscar_produtos_por_termo.

Estratégia:
- Testes de buscar_produtos_por_termo usam SQLite em memória com monkeypatch de
  get_session no service (mesmo padrão de test_service_produto.py).
- Smoke tests da UI monkeypatch as funções de service diretamente (listar_categorias,
  listar_produtos, buscar_produtos_por_termo), isolando a tela de qualquer banco.
"""

from __future__ import annotations

from contextlib import contextmanager
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from atalaia.db.base import Base
import atalaia.db.models  # noqa: F401
from atalaia.db.models.categoria import Categoria
from atalaia.db.models.produto import Produto, TipoEnum
from atalaia.modules.produtos import service


# ---------------------------------------------------------------------------
# Fixtures compartilhadas — SQLite para testes de service
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

def _cat(nome="Geral"):
    return service.criar_categoria(nome)


def _prod(cat_id, nome="Caneta", barcode=None, ativo=True, **kw):
    dados = dict(
        nome=nome,
        tipo=TipoEnum.produto,
        categoria_id=cat_id,
        preco_venda=Decimal("2.50"),
        unidade_medida="UN",
        codigo_barras=barcode,
    )
    dados.update(kw)
    p = service.criar_produto(dados)
    if not ativo:
        service.inativar_produto(p.id)
        # recarrega para refletir ativo=False
        todos = service.listar_produtos(apenas_ativos=False)
        p = next(x for x in todos if x.id == p.id)
    return p


# ---------------------------------------------------------------------------
# Testes de buscar_produtos_por_termo
# ---------------------------------------------------------------------------

def test_buscar_por_barcode_exato_tem_prioridade():
    cat = _cat()
    _prod(cat.id, nome="Caneta Azul", barcode="111")
    _prod(cat.id, nome="Produto 111", barcode="999")  # nome contém "111" mas barcode diferente

    resultado = service.buscar_produtos_por_termo("111")

    assert len(resultado) == 1
    assert resultado[0].codigo_barras == "111"


def test_buscar_por_nome_parcial_case_insensitive():
    cat = _cat()
    _prod(cat.id, nome="Caderno Universitário")
    _prod(cat.id, nome="Caderno Espiral")
    _prod(cat.id, nome="Caneta Preta")

    resultado = service.buscar_produtos_por_termo("caderno")

    nomes = {p.nome for p in resultado}
    assert "Caderno Universitário" in nomes
    assert "Caderno Espiral" in nomes
    assert "Caneta Preta" not in nomes


def test_buscar_sem_correspondencia_retorna_vazio():
    cat = _cat()
    _prod(cat.id, nome="Borracha")

    resultado = service.buscar_produtos_por_termo("xyzxyz_inexistente")

    assert resultado == []


def test_buscar_termo_vazio_retorna_todos_ativos():
    cat = _cat()
    _prod(cat.id, nome="Produto A")
    _prod(cat.id, nome="Produto B")

    resultado = service.buscar_produtos_por_termo("")

    assert len(resultado) >= 2


# ---------------------------------------------------------------------------
# Smoke tests da UI (pytest-qt)
# ---------------------------------------------------------------------------

def _fake_categoria(nome):
    cat = MagicMock(spec=Categoria)
    cat.id = 1
    cat.nome = nome
    return cat


def _fake_produto(nome="Produto Teste", ativo=True):
    p = MagicMock(spec=Produto)
    p.id = 1
    p.nome = nome
    p.tipo = TipoEnum.produto
    p.ativo = ativo
    p.controla_estoque = True
    p.estoque_atual = 10
    p.preco_venda = Decimal("10.00")
    p.preco_promocional = None
    p.produto_em_promocao = False
    p.promocao_inicio = None
    p.promocao_fim = None
    p.categoria = _fake_categoria("Geral")
    p.categoria_id = 1
    p.codigo_barras = None
    return p


def test_smoke_instancia_sem_erro(qtbot, monkeypatch):
    """TelaProdutos instancia sem levantar exceção com dados mockados."""
    monkeypatch.setattr(service, "listar_categorias", lambda: [_fake_categoria("Papelaria")])
    monkeypatch.setattr(service, "listar_produtos", lambda **kw: [_fake_produto()])
    monkeypatch.setattr(service, "buscar_produtos_por_termo", lambda t: [])

    from atalaia.modules.produtos.ui.tela_produtos import TelaProdutos

    tela = TelaProdutos()
    qtbot.addWidget(tela)

    assert tela is not None


def test_smoke_combo_categoria_populado(qtbot, monkeypatch):
    """Combo de categoria deve refletir as categorias retornadas pelo service."""
    cats = [_fake_categoria("Papelaria"), _fake_categoria("Eletrônicos")]
    monkeypatch.setattr(service, "listar_categorias", lambda: cats)
    monkeypatch.setattr(service, "listar_produtos", lambda **kw: [])
    monkeypatch.setattr(service, "buscar_produtos_por_termo", lambda t: [])

    from atalaia.modules.produtos.ui.tela_produtos import TelaProdutos

    tela = TelaProdutos()
    qtbot.addWidget(tela)

    # índice 0 = "Todas", depois os nomes das categorias
    assert tela.combo_categoria.count() == 3
    assert tela.combo_categoria.itemText(1) == "Papelaria"
    assert tela.combo_categoria.itemText(2) == "Eletrônicos"


def test_smoke_tabela_exibe_produtos(qtbot, monkeypatch):
    """Model da tabela deve conter os produtos retornados pelo service."""
    produtos = [_fake_produto("Caneta"), _fake_produto("Borracha")]
    monkeypatch.setattr(service, "listar_categorias", lambda: [])
    monkeypatch.setattr(service, "listar_produtos", lambda **kw: produtos)
    monkeypatch.setattr(service, "buscar_produtos_por_termo", lambda t: [])

    from atalaia.modules.produtos.ui.tela_produtos import TelaProdutos

    tela = TelaProdutos()
    qtbot.addWidget(tela)

    assert tela._modelo.rowCount() == 2


# ---------------------------------------------------------------------------
# Testes de combinação de filtros na UI (combo + texto)
# ---------------------------------------------------------------------------

def test_filtro_combinado_categoria_e_texto(qtbot):
    """
    Categoria=Papelaria + texto='caneta': retorna apenas produtos de Papelaria
    cujo nome contém 'caneta', excluindo produtos de outras categorias com o
    mesmo nome parcial.
    """
    from atalaia.modules.produtos.ui.tela_produtos import TelaProdutos

    cat_papel = service.criar_categoria("Papelaria")
    cat_elet = service.criar_categoria("Eletronicos")

    service.criar_produto({
        "nome": "Caneta Azul", "tipo": TipoEnum.produto,
        "categoria_id": cat_papel.id, "preco_venda": Decimal("2.50"), "unidade_medida": "UN",
    })
    service.criar_produto({
        "nome": "Caneta Vermelha", "tipo": TipoEnum.produto,
        "categoria_id": cat_elet.id, "preco_venda": Decimal("2.50"), "unidade_medida": "UN",
    })
    service.criar_produto({
        "nome": "Caderno", "tipo": TipoEnum.produto,
        "categoria_id": cat_papel.id, "preco_venda": Decimal("10.00"), "unidade_medida": "UN",
    })

    tela = TelaProdutos()
    qtbot.addWidget(tela)

    # localiza o índice de "Papelaria" no combo (sorted, offset +1 por "Todas")
    cat_idx = next(i + 1 for i, c in enumerate(tela._categorias) if c.nome == "Papelaria")
    tela.combo_categoria.setCurrentIndex(cat_idx)
    tela.txt_buscar.setText("caneta")
    tela._aplicar_filtros()

    assert tela._modelo.rowCount() == 1
    assert tela._modelo.produto_em_linha(0).nome == "Caneta Azul"


def test_texto_com_status_inativos(qtbot):
    """
    Texto + Status=Inativos: produto inativo com nome correspondente deve aparecer;
    produto ativo com o mesmo termo não deve aparecer.
    Confirma que buscar_produtos_por_termo recebe apenas_ativos=False e que o
    pós-filtro de inativos funciona corretamente no caminho com texto.
    """
    from atalaia.modules.produtos.ui.tela_produtos import TelaProdutos

    cat = service.criar_categoria("Geral")
    service.criar_produto({
        "nome": "Caneta Ativa", "tipo": TipoEnum.produto,
        "categoria_id": cat.id, "preco_venda": Decimal("2.50"), "unidade_medida": "UN",
    })
    p_inativo = service.criar_produto({
        "nome": "Caneta Inativa", "tipo": TipoEnum.produto,
        "categoria_id": cat.id, "preco_venda": Decimal("2.50"), "unidade_medida": "UN",
    })
    service.inativar_produto(p_inativo.id)

    tela = TelaProdutos()
    qtbot.addWidget(tela)

    tela.combo_status.setCurrentIndex(1)  # Inativos
    tela.txt_buscar.setText("caneta")
    tela._aplicar_filtros()

    assert tela._modelo.rowCount() == 1
    assert tela._modelo.produto_em_linha(0).nome == "Caneta Inativa"


def test_filtro_combinado_tipo_e_texto(qtbot):
    """
    Tipo=Produto + texto='a4': retorna apenas produtos físicos cujo nome
    contém 'a4', excluindo serviços com o mesmo termo no nome.
    """
    from atalaia.modules.produtos.ui.tela_produtos import TelaProdutos

    cat = service.criar_categoria("Geral")

    service.criar_produto({
        "nome": "Papel A4", "tipo": TipoEnum.produto,
        "categoria_id": cat.id, "preco_venda": Decimal("15.00"), "unidade_medida": "PCT",
    })
    service.criar_produto({
        "nome": "Impressão A4", "tipo": TipoEnum.servico,
        "categoria_id": cat.id, "preco_venda": Decimal("0.50"), "unidade_medida": "UN",
        "controla_estoque": False,
    })

    tela = TelaProdutos()
    qtbot.addWidget(tela)

    tela.combo_tipo.setCurrentIndex(1)   # "Produto"
    tela.txt_buscar.setText("a4")
    tela._aplicar_filtros()

    assert tela._modelo.rowCount() == 1
    assert tela._modelo.produto_em_linha(0).nome == "Papel A4"
