from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Numeric, bindparam, select, text
from sqlalchemy.orm import joinedload

from atalaia.db.session import get_session
from atalaia.db.models.fornecedor import Fornecedor
from atalaia.db.models.produto import Produto
from atalaia.db.models.entrada_mercadoria import EntradaMercadoria, ItemEntrada, StatusEntradaEnum
from atalaia.modules.entrada_mercadorias.exceptions import (
    EntradaJaConfirmadaError,
    FornecedorInativoError,
    FornecedorNaoEncontradoError,
    ProdutoInativoError,
    ProdutoNaoEncontradoError,
)


def criar_entrada(
    fornecedor_id: int,
    numero_nota: str | None = None,
    data_entrada: date | None = None,
    observacoes: str | None = None,
) -> EntradaMercadoria:
    with get_session() as session:
        fornecedor = session.get(Fornecedor, fornecedor_id)
        if fornecedor is None:
            raise FornecedorNaoEncontradoError(
                f"Fornecedor {fornecedor_id} não encontrado."
            )
        if not fornecedor.ativo:
            raise FornecedorInativoError(
                f"Fornecedor '{fornecedor.nome}' está inativo."
            )
        kwargs: dict = {
            "fornecedor_id": fornecedor_id,
            "numero_nota": numero_nota,
            "observacoes": observacoes,
            "status": StatusEntradaEnum.rascunho,
            "data_entrada": data_entrada if data_entrada is not None else date.today(),
        }
        entrada = EntradaMercadoria(**kwargs)
        session.add(entrada)
        session.flush()
        session.expunge(entrada)
        return entrada


def adicionar_item(
    entrada_id: int,
    produto_id: int,
    quantidade: int,
    custo_unitario: Decimal,
) -> ItemEntrada:
    if quantidade <= 0:
        raise ValueError("quantidade deve ser maior que zero.")
    if custo_unitario < 0:
        raise ValueError("custo_unitario não pode ser negativo.")

    with get_session() as session:
        entrada = session.get(EntradaMercadoria, entrada_id)
        if entrada is None:
            raise ValueError(f"Entrada {entrada_id} não encontrada.")
        if entrada.status == StatusEntradaEnum.confirmada:
            raise EntradaJaConfirmadaError(
                f"Entrada {entrada_id} já está confirmada e não pode ser alterada."
            )
        produto = session.get(Produto, produto_id)
        if produto is None:
            raise ProdutoNaoEncontradoError(f"Produto {produto_id} não encontrado.")
        if not produto.ativo:
            raise ProdutoInativoError(f"Produto '{produto.nome}' está inativo.")

        item = ItemEntrada(
            entrada_id=entrada_id,
            produto_id=produto_id,
            quantidade=quantidade,
            custo_unitario=custo_unitario,
        )
        session.add(item)
        session.flush()
        session.expunge(item)
        return item


def remover_item(item_id: int) -> None:
    with get_session() as session:
        item = session.get(ItemEntrada, item_id)
        if item is None:
            raise ValueError(f"Item {item_id} não encontrado.")
        entrada = session.get(EntradaMercadoria, item.entrada_id)
        if entrada is not None and entrada.status == StatusEntradaEnum.confirmada:
            raise EntradaJaConfirmadaError(
                f"Entrada {item.entrada_id} já está confirmada e não pode ser alterada."
            )
        session.delete(item)


def confirmar_entrada(entrada_id: int) -> None:
    """
    Confirma uma entrada de mercadoria de forma atômica.

    Toda a operação ocorre numa única sessão/transação:
    para cada item, incrementa o estoque via UPDATE atômico e atualiza
    preco_custo, preco_custo_anterior e custo_medio do produto em um único UPDATE.

    O UPDATE de custo usa preco_custo_anterior na cláusula CASE porque MySQL
    avalia as expressões SET da esquerda para a direita: após a atribuição
    `preco_custo_anterior = preco_custo`, preco_custo_anterior carrega o valor
    original (antigo) de preco_custo, que é exatamente o que queremos comparar
    ao calcular custo_medio.
    """
    with get_session() as session:
        entrada = session.execute(
            select(EntradaMercadoria)
            .where(EntradaMercadoria.id == entrada_id)
            .options(joinedload(EntradaMercadoria.itens))
        ).unique().scalar_one_or_none()
        if entrada is None:
            raise ValueError(f"Entrada {entrada_id} não encontrada.")
        if entrada.status == StatusEntradaEnum.confirmada:
            raise EntradaJaConfirmadaError(
                f"Entrada {entrada_id} já está confirmada."
            )

        for item in entrada.itens:
            session.execute(
                text(
                    "UPDATE produtos"
                    " SET estoque_atual = estoque_atual + :qtd"
                    " WHERE id = :id AND controla_estoque = TRUE"
                ),
                {"qtd": item.quantidade, "id": item.produto_id},
            )
            # item.produto já carregado via lazy='joined'; usamos seu preco_custo
            # como parâmetro para que o CASE funcione corretamente em MySQL e SQLite
            # (MySQL e SQLite divergem na semântica de avaliação do SET).
            custo_anterior = item.produto.preco_custo
            session.execute(
                text(
                    "UPDATE produtos SET"
                    "  preco_custo_anterior = preco_custo,"
                    "  preco_custo = :novo_custo,"
                    "  custo_medio = CASE"
                    "    WHEN :custo_anterior IS NULL THEN :novo_custo"
                    "    ELSE (:custo_anterior + :novo_custo) / 2"
                    "  END"
                    " WHERE id = :produto_id"
                ).bindparams(
                    bindparam("novo_custo", type_=Numeric(10, 2)),
                    bindparam("custo_anterior", type_=Numeric(10, 2)),
                ),
                {
                    "novo_custo": item.custo_unitario,
                    "custo_anterior": custo_anterior,
                    "produto_id": item.produto_id,
                },
            )

        entrada.status = StatusEntradaEnum.confirmada


def obter_entrada(entrada_id: int) -> EntradaMercadoria:
    with get_session() as session:
        entrada = session.execute(
            select(EntradaMercadoria)
            .options(
                joinedload(EntradaMercadoria.fornecedor),
                joinedload(EntradaMercadoria.itens).joinedload(ItemEntrada.produto),
            )
            .where(EntradaMercadoria.id == entrada_id)
        ).unique().scalar_one_or_none()
        if entrada is None:
            raise ValueError(f"Entrada {entrada_id} não encontrada.")
        session.expunge_all()
        return entrada


def atualizar_rascunho(
    entrada_id: int,
    fornecedor_id: int | None = None,
    numero_nota: str | None = None,
    data_entrada: date | None = None,
    observacoes: str | None = None,
) -> EntradaMercadoria:
    with get_session() as session:
        entrada = session.get(EntradaMercadoria, entrada_id)
        if entrada is None:
            raise ValueError(f"Entrada {entrada_id} não encontrada.")
        if entrada.status == StatusEntradaEnum.confirmada:
            raise EntradaJaConfirmadaError(
                f"Entrada {entrada_id} já está confirmada e não pode ser alterada."
            )
        if fornecedor_id is not None:
            fornecedor = session.get(Fornecedor, fornecedor_id)
            if fornecedor is None:
                raise FornecedorNaoEncontradoError(f"Fornecedor {fornecedor_id} não encontrado.")
            if not fornecedor.ativo:
                raise FornecedorInativoError(f"Fornecedor '{fornecedor.nome}' está inativo.")
            entrada.fornecedor_id = fornecedor_id
        if numero_nota is not None:
            entrada.numero_nota = numero_nota
        if data_entrada is not None:
            entrada.data_entrada = data_entrada
        if observacoes is not None:
            entrada.observacoes = observacoes
        session.flush()
        session.expunge(entrada)
        return entrada


def excluir_rascunho(entrada_id: int) -> None:
    with get_session() as session:
        entrada = session.get(EntradaMercadoria, entrada_id)
        if entrada is None:
            raise ValueError(f"Entrada {entrada_id} não encontrada.")
        if entrada.status == StatusEntradaEnum.confirmada:
            raise EntradaJaConfirmadaError(
                f"Entrada {entrada_id} está confirmada e não pode ser excluída."
            )
        session.delete(entrada)


def listar_entradas(
    status: str | None = None,
    fornecedor_id: int | None = None,
    data_de: date | None = None,
    data_ate: date | None = None,
) -> list[EntradaMercadoria]:
    with get_session() as session:
        stmt = select(EntradaMercadoria).options(
            joinedload(EntradaMercadoria.fornecedor),
            joinedload(EntradaMercadoria.itens),
        )
        if status is not None:
            stmt = stmt.where(EntradaMercadoria.status == StatusEntradaEnum(status))
        if fornecedor_id is not None:
            stmt = stmt.where(EntradaMercadoria.fornecedor_id == fornecedor_id)
        if data_de is not None:
            stmt = stmt.where(EntradaMercadoria.data_entrada >= data_de)
        if data_ate is not None:
            stmt = stmt.where(EntradaMercadoria.data_entrada <= data_ate)
        stmt = stmt.order_by(EntradaMercadoria.data_entrada.desc())
        entradas = session.execute(stmt).unique().scalars().all()
        session.expunge_all()
        return entradas
