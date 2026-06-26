from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from atalaia.db.session import get_session
from atalaia.db.models.categoria import Categoria
from atalaia.db.models.produto import Produto, TipoEnum
from atalaia.modules.produtos.exceptions import (
    CategoriaNaoEncontradaError,
    CodigoBarrasDuplicadoError,
    DescontoExcedeLimiteError,
    DescontoMaximoForaDoIntervaloError,
    DescontoNaoPermitidoError,
    EstoqueInsuficienteError,
    PromocaoInvalidaError,
)


def _validar_desconto_maximo(desconto_maximo) -> None:
    """Valida que desconto_maximo_percentual está em [0, 100], se presente."""
    if desconto_maximo is not None and (desconto_maximo < 0 or desconto_maximo > 100):
        raise DescontoMaximoForaDoIntervaloError(
            f"desconto_maximo_percentual deve estar entre 0 e 100; recebido {desconto_maximo}."
        )


def _validar_promocao(inicio, fim, preco_promocional, preco_venda) -> None:
    """
    Valida consistência da promoção a partir de valores já resolvidos (efetivos).
    Recebe None para campos ausentes. Não toca no banco.
    """
    if inicio is not None and fim is not None and fim < inicio:
        raise PromocaoInvalidaError(
            f"Data de fim da promoção ({fim}) não pode ser anterior à data de início ({inicio})."
        )
    if (
        preco_promocional is not None
        and preco_venda is not None
        and preco_promocional > preco_venda
    ):
        raise PromocaoInvalidaError(
            f"Preço promocional ({preco_promocional}) não pode ser maior que o preço de venda ({preco_venda})."
        )


def criar_categoria(nome: str) -> Categoria:
    if not nome or not nome.strip():
        raise ValueError("Nome da categoria não pode ser vazio.")
    with get_session() as session:
        try:
            cat = Categoria(nome=nome.strip())
            session.add(cat)
            session.flush()
            session.expunge(cat)
            return cat
        except IntegrityError:
            raise ValueError(f"Categoria '{nome}' já existe.")


def listar_categorias() -> list[Categoria]:
    with get_session() as session:
        cats = session.execute(select(Categoria).order_by(Categoria.nome)).scalars().all()
        for cat in cats:
            session.expunge(cat)
        return cats


def criar_produto(dados: dict) -> Produto:
    """
    Cria um produto a partir de um dicionário de campos.

    Normalização silenciosa: se tipo=servico e controla_estoque=True, força
    controla_estoque=False. Serviços nunca controlam estoque por definição de
    negócio; corrigir silenciosamente evita erro de cadastro sem necessidade de
    o chamador validar essa combinação antes de chamar a função.
    """
    dados = dict(dados)

    tipo = dados.get("tipo")
    if tipo in (TipoEnum.servico, "servico"):
        dados["controla_estoque"] = False

    if "preco_venda" in dados and dados["preco_venda"] < 0:
        raise ValueError("preco_venda não pode ser negativo.")

    _validar_desconto_maximo(dados.get("desconto_maximo_percentual"))
    _validar_promocao(
        dados.get("promocao_inicio"),
        dados.get("promocao_fim"),
        dados.get("preco_promocional"),
        dados.get("preco_venda"),
    )

    with get_session() as session:
        if "categoria_id" in dados:
            if session.get(Categoria, dados["categoria_id"]) is None:
                raise CategoriaNaoEncontradaError(
                    f"Categoria {dados['categoria_id']} não encontrada."
                )

        p = Produto(**dados)
        session.add(p)
        try:
            session.flush()
        except IntegrityError as e:
            if "codigo_barras" in str(e.orig).lower():
                raise CodigoBarrasDuplicadoError(
                    f"Código de barras '{dados.get('codigo_barras')}' já está em uso."
                )
            raise
        session.expunge(p)
        return p


def atualizar_produto(produto_id: int, dados: dict) -> Produto:
    """
    Atualiza campos parciais de um produto.

    Normalização silenciosa: se tipo=servico (novo ou já existente) e
    controla_estoque=True, força controla_estoque=False — mesma lógica de criar_produto.

    Restrição: 'estoque_atual' não pode ser passado em dados. Alterações de estoque
    devem sempre passar por dar_baixa_estoque() ou dar_entrada_estoque(), nunca por
    atualização direta de campo — mesmo nesta camada de service. Isso garante o padrão
    de UPDATE atômico e evita race condition entre sessões concorrentes.
    """
    dados = dict(dados)

    if "estoque_atual" in dados:
        raise ValueError(
            "Alteração direta de 'estoque_atual' não é permitida em atualizar_produto. "
            "Use dar_entrada_estoque() ou dar_baixa_estoque()."
        )

    if "preco_venda" in dados and dados["preco_venda"] < 0:
        raise ValueError("preco_venda não pode ser negativo.")

    _validar_desconto_maximo(dados.get("desconto_maximo_percentual"))

    with get_session() as session:
        p = session.get(Produto, produto_id)
        if p is None:
            raise ValueError(f"Produto {produto_id} não encontrado.")

        tipo_resultante = dados.get("tipo", p.tipo)
        if tipo_resultante in (TipoEnum.servico, "servico"):
            dados["controla_estoque"] = False

        if "categoria_id" in dados:
            if session.get(Categoria, dados["categoria_id"]) is None:
                raise CategoriaNaoEncontradaError(
                    f"Categoria {dados['categoria_id']} não encontrada."
                )

        # Promoção: mesclar valores do dict com os existentes em p (atualização parcial).
        _validar_promocao(
            dados.get("promocao_inicio", p.promocao_inicio),
            dados.get("promocao_fim", p.promocao_fim),
            dados.get("preco_promocional", p.preco_promocional),
            dados.get("preco_venda", p.preco_venda),
        )

        for campo, valor in dados.items():
            setattr(p, campo, valor)

        try:
            session.flush()
        except IntegrityError as e:
            if "codigo_barras" in str(e.orig).lower():
                raise CodigoBarrasDuplicadoError(
                    f"Código de barras '{dados.get('codigo_barras')}' já está em uso."
                )
            raise
        session.expunge(p)
        return p


def inativar_produto(produto_id: int) -> None:
    with get_session() as session:
        p = session.get(Produto, produto_id)
        if p is None:
            raise ValueError(f"Produto {produto_id} não encontrado.")
        p.ativo = False


def listar_produtos(
    tipo: str | None = None,
    categoria_id: int | None = None,
    apenas_ativos: bool = True,
    nome_contem: str | None = None,
) -> list[Produto]:
    with get_session() as session:
        stmt = select(Produto).options(joinedload(Produto.categoria))
        if apenas_ativos:
            stmt = stmt.where(Produto.ativo.is_(True))
        if tipo is not None:
            stmt = stmt.where(Produto.tipo == TipoEnum(tipo))
        if categoria_id is not None:
            stmt = stmt.where(Produto.categoria_id == categoria_id)
        if nome_contem is not None:
            stmt = stmt.where(Produto.nome.ilike(f"%{nome_contem}%"))
        stmt = stmt.order_by(Produto.nome)
        produtos = session.execute(stmt).unique().scalars().all()
        session.expunge_all()
        return produtos


def obter_produto(produto_id: int) -> Produto | None:
    with get_session() as session:
        p = session.execute(
            select(Produto)
            .options(joinedload(Produto.categoria))
            .where(Produto.id == produto_id)
        ).unique().scalar_one_or_none()
        if p is not None:
            session.expunge_all()
        return p


def buscar_por_codigo_barras(codigo: str) -> Produto | None:
    with get_session() as session:
        p = session.execute(
            select(Produto)
            .options(joinedload(Produto.categoria))
            .where(Produto.codigo_barras == codigo)
        ).unique().scalar_one_or_none()
        if p is not None:
            session.expunge_all()
        return p


def buscar_produtos_por_termo(
    termo: str,
    tipo: str | None = None,
    categoria_id: int | None = None,
    apenas_ativos: bool = True,
) -> list[Produto]:
    """
    Busca produtos por código de barras (prioridade) ou nome (contém, case-insensitive).

    Se o termo bater exatamente com um código de barras cadastrado, retorna apenas
    esse produto — comportamento esperado ao usar leitor de código de barras no PDV.
    Caso contrário, delega a listar_produtos() com nome_contem, garantindo que
    tipo, categoria_id e apenas_ativos sejam aplicados no SQL, não em Python.

    O filtro de apenas_ativos também se aplica ao resultado por código de barras:
    se apenas_ativos=True e o produto encontrado estiver inativo, retorna lista vazia.
    """
    termo = termo.strip()
    if not termo:
        return listar_produtos(tipo=tipo, categoria_id=categoria_id, apenas_ativos=apenas_ativos)
    por_barcode = buscar_por_codigo_barras(termo)
    if por_barcode is not None:
        if apenas_ativos and not por_barcode.ativo:
            return []
        if tipo and por_barcode.tipo != TipoEnum(tipo):
            return []
        if categoria_id and por_barcode.categoria_id != categoria_id:
            return []
        return [por_barcode]
    return listar_produtos(
        tipo=tipo, categoria_id=categoria_id, apenas_ativos=apenas_ativos, nome_contem=termo
    )


def dar_baixa_estoque(produto_id: int, quantidade: int) -> None:
    """
    Reduz o estoque do produto de forma atômica.

    Usa UPDATE com WHERE condicional (controla_estoque=TRUE AND estoque_atual>=qtd)
    para garantir que a verificação e a subtração ocorrem numa única operação no banco,
    eliminando race condition entre leitura e escrita em sessões concorrentes.

    Se controla_estoque=False (produto do tipo serviço), retorna sem erro:
    centraliza a checagem aqui para que PDV e Orçamento não precisem verificar
    o tipo do produto antes de chamar esta função.
    """
    with get_session() as session:
        result = session.execute(
            text(
                "UPDATE produtos"
                " SET estoque_atual = estoque_atual - :qtd"
                " WHERE id = :id AND controla_estoque = TRUE AND estoque_atual >= :qtd"
            ),
            {"qtd": quantidade, "id": produto_id},
        )
        if result.rowcount == 0:
            p = session.get(Produto, produto_id)
            if p is None or not p.controla_estoque:
                return
            raise EstoqueInsuficienteError(
                f"Estoque insuficiente para o produto {produto_id} ('{p.nome}'): "
                f"disponível {p.estoque_atual}, solicitado {quantidade}."
            )


def dar_entrada_estoque(produto_id: int, quantidade: int) -> None:
    """
    Incrementa o estoque do produto de forma atômica.

    Se controla_estoque=False, retorna sem erro — mesma lógica de dar_baixa_estoque.
    """
    with get_session() as session:
        session.execute(
            text(
                "UPDATE produtos"
                " SET estoque_atual = estoque_atual + :qtd"
                " WHERE id = :id AND controla_estoque = TRUE"
            ),
            {"qtd": quantidade, "id": produto_id},
        )


def obter_preco_vigente(produto: Produto, data_referencia: date | None = None) -> Decimal:
    if data_referencia is None:
        data_referencia = date.today()

    if (
        produto.produto_em_promocao
        and produto.preco_promocional is not None
        and produto.promocao_inicio is not None
        and produto.promocao_fim is not None
        and produto.promocao_inicio <= data_referencia <= produto.promocao_fim
    ):
        return produto.preco_promocional

    return produto.preco_venda


def validar_desconto(produto: Produto, percentual_solicitado: Decimal) -> None:
    if percentual_solicitado == 0:
        return
    if not produto.permite_desconto:
        raise DescontoNaoPermitidoError(
            f"Produto '{produto.nome}' não permite desconto."
        )
    if percentual_solicitado > produto.desconto_maximo_percentual:
        raise DescontoExcedeLimiteError(
            f"Desconto de {percentual_solicitado}% excede o limite de "
            f"{produto.desconto_maximo_percentual}% para '{produto.nome}'."
        )
