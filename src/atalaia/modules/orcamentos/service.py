from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, text
from sqlalchemy.orm import joinedload

from atalaia.db.session import get_session
from atalaia.db.models.orcamento import Orcamento, ItemOrcamento, StatusOrcamentoEnum
from atalaia.db.models.venda import Venda, ItemVenda, StatusVendaEnum
from atalaia.db.models.produto import Produto
from atalaia.db.models.cliente import Cliente
from atalaia.db.models.configuracao import Configuracao
from atalaia.modules.orcamentos.exceptions import (
    OrcamentoNaoEncontradoError,
    OrcamentoJaFinalizadoError,
    OrcamentoVencidoError,
    EstoqueInsuficienteError,
    ClienteNaoEncontradoError,
    ClienteInativoError,
    ProdutoNaoEncontradoError,
    ProdutoInativoError,
)
from atalaia.modules.produtos.service import obter_preco_vigente


def _get_validade_padrao() -> int:
    with get_session() as session:
        cfg = session.query(Configuracao).filter(
            Configuracao.chave == "validade_orcamento_dias"
        ).first()
        if cfg is None:
            return 10
        try:
            return int(cfg.valor)
        except (TypeError, ValueError):
            return 10


def carregar_configs(chaves: list[str]) -> dict[str, str]:
    with get_session() as session:
        rows = session.query(Configuracao).filter(Configuracao.chave.in_(chaves)).all()
        return {r.chave: (r.valor or "") for r in rows}


def numero_formatado(orcamento: Orcamento) -> str:
    return f"ORC-{orcamento.numero:04d}"


def criar_orcamento(
    cliente_id: int,
    validade_dias: int | None = None,
    desconto_percentual: Decimal = Decimal("0"),
    observacoes: str | None = None,
) -> Orcamento:
    if validade_dias is None:
        validade_dias = _get_validade_padrao()
    with get_session() as session:
        cliente = session.get(Cliente, cliente_id)
        if cliente is None:
            raise ClienteNaoEncontradoError(f"Cliente {cliente_id} não encontrado.")
        if not cliente.ativo:
            raise ClienteInativoError(f"Cliente '{cliente.nome}' está inativo.")
        max_numero = session.query(func.max(Orcamento.numero)).scalar() or 0
        hoje = date.today()
        orc = Orcamento(
            numero=max_numero + 1,
            cliente_id=cliente_id,
            status=StatusOrcamentoEnum.aberto,
            validade_dias=validade_dias,
            data_criacao=hoje,
            data_validade=hoje + timedelta(days=validade_dias),
            desconto_percentual=desconto_percentual,
            observacoes=observacoes,
        )
        session.add(orc)
        session.flush()
        session.expunge(orc)
        return orc


def adicionar_item(orcamento_id: int, produto_id: int, quantidade: int) -> ItemOrcamento:
    with get_session() as session:
        orc = session.get(Orcamento, orcamento_id)
        if orc is None:
            raise OrcamentoNaoEncontradoError(f"Orçamento {orcamento_id} não encontrado.")
        if orc.status != StatusOrcamentoEnum.aberto:
            raise OrcamentoJaFinalizadoError("Orçamento já finalizado — não é possível adicionar itens.")
        prod = session.get(Produto, produto_id)
        if prod is None:
            raise ProdutoNaoEncontradoError(f"Produto {produto_id} não encontrado.")
        if not prod.ativo:
            raise ProdutoInativoError(f"Produto '{prod.nome}' está inativo.")
        preco_unitario = obter_preco_vigente(prod)
        item = ItemOrcamento(
            orcamento_id=orcamento_id,
            produto_id=produto_id,
            quantidade=quantidade,
            preco_unitario=preco_unitario,
        )
        session.add(item)
        session.flush()
        session.expunge_all()
        return item


def remover_item(item_id: int) -> None:
    with get_session() as session:
        item = session.get(ItemOrcamento, item_id)
        if item is None:
            return
        orc = session.get(Orcamento, item.orcamento_id)
        if orc and orc.status != StatusOrcamentoEnum.aberto:
            raise OrcamentoJaFinalizadoError("Orçamento já finalizado — não é possível remover itens.")
        session.delete(item)


def atualizar_orcamento(orcamento_id: int, dados: dict) -> Orcamento:
    with get_session() as session:
        orc = session.get(Orcamento, orcamento_id)
        if orc is None:
            raise OrcamentoNaoEncontradoError(f"Orçamento {orcamento_id} não encontrado.")
        if orc.status != StatusOrcamentoEnum.aberto:
            raise OrcamentoJaFinalizadoError("Orçamento já finalizado.")
        for campo, valor in dados.items():
            setattr(orc, campo, valor)
        if "validade_dias" in dados:
            orc.data_validade = orc.data_criacao + timedelta(days=orc.validade_dias)
        session.flush()
        session.expunge(orc)
        return orc


def aprovar_orcamento(orcamento_id: int) -> Venda:
    with get_session() as session:
        orc = session.get(
            Orcamento, orcamento_id,
            options=[joinedload(Orcamento.itens).joinedload(ItemOrcamento.produto)],
        )
        if orc is None:
            raise OrcamentoNaoEncontradoError(f"Orçamento {orcamento_id} não encontrado.")
        if orc.status != StatusOrcamentoEnum.aberto:
            raise OrcamentoJaFinalizadoError("Orçamento já foi aprovado ou recusado.")
        if date.today() > orc.data_validade:
            raise OrcamentoVencidoError("Orçamento vencido — renove a validade antes de aprovar.")

        orc.status = StatusOrcamentoEnum.aprovado

        subtotal = sum(i.quantidade * i.preco_unitario for i in orc.itens)
        total = subtotal * (1 - orc.desconto_percentual / Decimal("100"))

        venda = Venda(
            orcamento_id=orc.id,
            cliente_id=orc.cliente_id,
            status=StatusVendaEnum.finalizada,
            desconto_percentual=orc.desconto_percentual,
            total=total,
        )
        session.add(venda)
        session.flush()

        for item in orc.itens:
            session.add(ItemVenda(
                venda_id=venda.id,
                produto_id=item.produto_id,
                quantidade=item.quantidade,
                preco_unitario=item.preco_unitario,
            ))
            res = session.execute(
                text(
                    "UPDATE produtos"
                    " SET estoque_atual = estoque_atual - :qtd"
                    " WHERE id = :id AND controla_estoque = TRUE AND estoque_atual >= :qtd"
                ),
                {"qtd": item.quantidade, "id": item.produto_id},
            )
            if res.rowcount == 0:
                prod_check = session.get(Produto, item.produto_id)
                if prod_check and prod_check.controla_estoque:
                    raise EstoqueInsuficienteError(
                        f"Estoque insuficiente para '{prod_check.nome}'."
                    )

        session.expunge_all()
        return venda


def recusar_orcamento(orcamento_id: int) -> None:
    with get_session() as session:
        orc = session.get(Orcamento, orcamento_id)
        if orc is None:
            raise OrcamentoNaoEncontradoError(f"Orçamento {orcamento_id} não encontrado.")
        if orc.status != StatusOrcamentoEnum.aberto:
            raise OrcamentoJaFinalizadoError("Orçamento já foi aprovado ou recusado.")
        orc.status = StatusOrcamentoEnum.recusado


def obter_orcamento(orcamento_id: int) -> Orcamento:
    with get_session() as session:
        orc = session.get(
            Orcamento, orcamento_id,
            options=[
                joinedload(Orcamento.cliente),
                joinedload(Orcamento.itens).joinedload(ItemOrcamento.produto),
            ],
        )
        if orc is None:
            raise OrcamentoNaoEncontradoError(f"Orçamento {orcamento_id} não encontrado.")
        session.expunge_all()
        return orc


def listar_orcamentos(
    status: str | None = None,
    cliente_id: int | None = None,
) -> list[Orcamento]:
    with get_session() as session:
        q = session.query(Orcamento).options(joinedload(Orcamento.cliente))
        if status:
            q = q.filter(Orcamento.status == StatusOrcamentoEnum[status])
        if cliente_id:
            q = q.filter(Orcamento.cliente_id == cliente_id)
        orcamentos = q.order_by(Orcamento.id.desc()).all()
        session.expunge_all()
        return orcamentos
