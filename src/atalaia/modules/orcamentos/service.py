from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from atalaia.db.session import get_session
from atalaia.db.models.orcamento import Orcamento, ItemOrcamento, StatusOrcamentoEnum
from atalaia.db.models.produto import Produto
from atalaia.db.models.cliente import Cliente
from atalaia.db.models.configuracao import Configuracao
from atalaia.modules.orcamentos.exceptions import (
    OrcamentoNaoEncontradoError,
    OrcamentoJaFinalizadoError,
    OrcamentoVencidoError,
    ClienteNaoEncontradoError,
    ClienteInativoError,
    ProdutoNaoEncontradoError,
    ProdutoInativoError,
)
from atalaia.modules.produtos.service import obter_preco_vigente


def _get_validade_padrao() -> int:
    with get_session() as session:
        cfg = session.execute(
            select(Configuracao).where(Configuracao.chave == "validade_orcamento_dias")
        ).scalar_one_or_none()
        if cfg is None:
            return 10
        try:
            return int(cfg.valor)
        except (TypeError, ValueError):
            return 10


def carregar_configs(chaves: list[str]) -> dict[str, str]:
    with get_session() as session:
        rows = session.execute(
            select(Configuracao).where(Configuracao.chave.in_(chaves))
        ).scalars().all()
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
        max_numero = session.execute(select(func.max(Orcamento.numero))).scalar() or 0
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


def aprovar_orcamento(orcamento_id: int) -> None:
    with get_session() as session:
        orc = session.get(Orcamento, orcamento_id)
        if orc is None:
            raise OrcamentoNaoEncontradoError(f"Orçamento {orcamento_id} não encontrado.")
        if orc.status != StatusOrcamentoEnum.aberto:
            raise OrcamentoJaFinalizadoError("Orçamento já foi aprovado ou recusado.")
        if date.today() > orc.data_validade:
            raise OrcamentoVencidoError("Orçamento vencido — renove a validade antes de aprovar.")
        orc.status = StatusOrcamentoEnum.aprovado


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
        orc = session.execute(
            select(Orcamento)
            .where(Orcamento.id == orcamento_id)
            .options(
                joinedload(Orcamento.cliente),
                joinedload(Orcamento.itens).joinedload(ItemOrcamento.produto),
            )
        ).unique().scalar_one_or_none()
        if orc is None:
            raise OrcamentoNaoEncontradoError(f"Orçamento {orcamento_id} não encontrado.")
        session.expunge_all()
        return orc


def listar_orcamentos(
    status: str | None = None,
    cliente_id: int | None = None,
) -> list[Orcamento]:
    with get_session() as session:
        stmt = (
            select(Orcamento)
            .options(
                joinedload(Orcamento.cliente),
                joinedload(Orcamento.itens).joinedload(ItemOrcamento.produto),
            )
            .order_by(Orcamento.id.desc())
        )
        if status:
            stmt = stmt.where(Orcamento.status == StatusOrcamentoEnum[status])
        if cliente_id:
            stmt = stmt.where(Orcamento.cliente_id == cliente_id)
        orcamentos = session.execute(stmt).unique().scalars().all()
        session.expunge_all()
        return list(orcamentos)
