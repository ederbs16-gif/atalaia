from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import joinedload

from atalaia.db.session import get_session
from atalaia.db.models.conta_pagar import ContaPagar, StatusContaEnum
from atalaia.db.models.conta_receber import ContaReceber
from atalaia.db.models.pagamento_conta_pagar import PagamentoContaPagar, FormaPagamentoEnum
from atalaia.db.models.pagamento_conta_receber import PagamentoContaReceber
from atalaia.modules.financeiro.exceptions import (
    ContaNaoEncontradaError,
    ContaJaPagaError,
    PagamentoExcedeValorError,
)


# ─── Contas a Pagar ──────────────────────────────────────────────────────────

def criar_conta_pagar(dados: dict) -> ContaPagar:
    descricao = (dados.get("descricao") or "").strip()
    if not descricao:
        raise ValueError("Descrição é obrigatória.")
    valor_total = Decimal(str(dados.get("valor_total", 0)))
    if valor_total <= 0:
        raise ValueError("Valor total deve ser maior que zero.")
    with get_session() as session:
        conta = ContaPagar(
            descricao=descricao,
            valor_total=valor_total,
            valor_pago=Decimal("0"),
            status=StatusContaEnum.pendente,
            vencimento=dados["vencimento"],
            fornecedor_id=dados.get("fornecedor_id"),
            observacoes=dados.get("observacoes"),
        )
        session.add(conta)
        session.flush()
        session.expunge_all()
        return conta


def criar_conta_pagar_parcelada(dados: dict, num_parcelas: int) -> list[ContaPagar]:
    descricao = (dados.get("descricao") or "").strip()
    if not descricao:
        raise ValueError("Descrição é obrigatória.")
    valor_total = Decimal(str(dados.get("valor_total", 0)))
    if valor_total <= 0:
        raise ValueError("Valor total deve ser maior que zero.")
    if num_parcelas < 2:
        raise ValueError("Número de parcelas deve ser ≥ 2.")

    grupo = str(uuid.uuid4())
    vencimento_base: date = dados["vencimento"]
    valor_parcela = (valor_total / num_parcelas).quantize(Decimal("0.01"))

    with get_session() as session:
        contas = []
        for i in range(num_parcelas):
            conta = ContaPagar(
                descricao=descricao,
                valor_total=valor_parcela,
                valor_pago=Decimal("0"),
                status=StatusContaEnum.pendente,
                vencimento=vencimento_base + timedelta(days=30 * i),
                fornecedor_id=dados.get("fornecedor_id"),
                parcela_numero=i + 1,
                parcela_total=num_parcelas,
                grupo_parcelas=grupo,
                observacoes=dados.get("observacoes"),
            )
            session.add(conta)
            contas.append(conta)
        session.flush()
        session.expunge_all()
        return contas


def registrar_pagamento_pagar(
    conta_id: int,
    valor: Decimal,
    forma: str,
    data: date,
    obs: str | None = None,
) -> PagamentoContaPagar:
    valor_float = float(valor)
    with get_session() as session:
        res = session.execute(
            text(
                "UPDATE contas_pagar"
                " SET valor_pago = valor_pago + :valor"
                " WHERE id = :id AND status != 'pago' AND (valor_pago + :valor) <= valor_total"
            ),
            {"valor": valor_float, "id": conta_id},
        )
        if res.rowcount == 0:
            conta = session.get(ContaPagar, conta_id)
            if conta is None:
                raise ContaNaoEncontradaError(f"Conta a pagar {conta_id} não encontrada.")
            if conta.status == StatusContaEnum.pago:
                raise ContaJaPagaError("Conta já está totalmente paga.")
            raise PagamentoExcedeValorError("Pagamento excede o valor restante da conta.")

        session.execute(
            text(
                "UPDATE contas_pagar"
                " SET status = CASE"
                "   WHEN valor_pago >= valor_total THEN 'pago'"
                "   WHEN valor_pago > 0 THEN 'pago_parcialmente'"
                "   ELSE 'pendente'"
                " END"
                " WHERE id = :id"
            ),
            {"id": conta_id},
        )

        try:
            forma_enum = FormaPagamentoEnum[forma]
        except KeyError:
            forma_enum = FormaPagamentoEnum(forma)

        pagamento = PagamentoContaPagar(
            conta_pagar_id=conta_id,
            valor=valor,
            forma_pagamento=forma_enum,
            data_pagamento=data,
            observacoes=obs,
        )
        session.add(pagamento)
        session.flush()
        session.expunge_all()
        return pagamento


def listar_contas_pagar(
    status: str | None = None,
    vencimento_ate: date | None = None,
) -> list[ContaPagar]:
    with get_session() as session:
        stmt = select(ContaPagar).options(
            joinedload(ContaPagar.fornecedor),
            joinedload(ContaPagar.pagamentos),
        )
        if status:
            stmt = stmt.where(ContaPagar.status == StatusContaEnum[status])
        if vencimento_ate:
            stmt = stmt.where(ContaPagar.vencimento <= vencimento_ate)
        stmt = stmt.order_by(ContaPagar.vencimento.asc())
        contas = session.execute(stmt).unique().scalars().all()
        session.expunge_all()
        return contas


def obter_conta_pagar(conta_id: int) -> ContaPagar:
    with get_session() as session:
        conta = session.execute(
            select(ContaPagar)
            .where(ContaPagar.id == conta_id)
            .options(
                joinedload(ContaPagar.fornecedor),
                joinedload(ContaPagar.pagamentos),
            )
        ).unique().scalar_one_or_none()
        if conta is None:
            raise ContaNaoEncontradaError(f"Conta a pagar {conta_id} não encontrada.")
        session.expunge_all()
        return conta


# ─── Contas a Receber ─────────────────────────────────────────────────────────

def criar_conta_receber(dados: dict) -> ContaReceber:
    descricao = (dados.get("descricao") or "").strip()
    if not descricao:
        raise ValueError("Descrição é obrigatória.")
    valor_total = Decimal(str(dados.get("valor_total", 0)))
    if valor_total <= 0:
        raise ValueError("Valor total deve ser maior que zero.")
    with get_session() as session:
        conta = ContaReceber(
            descricao=descricao,
            valor_total=valor_total,
            valor_pago=Decimal("0"),
            status=StatusContaEnum.pendente,
            vencimento=dados["vencimento"],
            cliente_id=dados.get("cliente_id"),
            orcamento_id=dados.get("orcamento_id"),
            observacoes=dados.get("observacoes"),
        )
        session.add(conta)
        session.flush()
        session.expunge_all()
        return conta


def criar_conta_receber_parcelada(dados: dict, num_parcelas: int) -> list[ContaReceber]:
    descricao = (dados.get("descricao") or "").strip()
    if not descricao:
        raise ValueError("Descrição é obrigatória.")
    valor_total = Decimal(str(dados.get("valor_total", 0)))
    if valor_total <= 0:
        raise ValueError("Valor total deve ser maior que zero.")
    if num_parcelas < 2:
        raise ValueError("Número de parcelas deve ser ≥ 2.")

    grupo = str(uuid.uuid4())
    vencimento_base: date = dados["vencimento"]
    valor_parcela = (valor_total / num_parcelas).quantize(Decimal("0.01"))

    with get_session() as session:
        contas = []
        for i in range(num_parcelas):
            conta = ContaReceber(
                descricao=descricao,
                valor_total=valor_parcela,
                valor_pago=Decimal("0"),
                status=StatusContaEnum.pendente,
                vencimento=vencimento_base + timedelta(days=30 * i),
                cliente_id=dados.get("cliente_id"),
                orcamento_id=dados.get("orcamento_id"),
                parcela_numero=i + 1,
                parcela_total=num_parcelas,
                grupo_parcelas=grupo,
                observacoes=dados.get("observacoes"),
            )
            session.add(conta)
            contas.append(conta)
        session.flush()
        session.expunge_all()
        return contas


def registrar_pagamento_receber(
    conta_id: int,
    valor: Decimal,
    forma: str,
    data: date,
    obs: str | None = None,
) -> PagamentoContaReceber:
    valor_float = float(valor)
    with get_session() as session:
        res = session.execute(
            text(
                "UPDATE contas_receber"
                " SET valor_pago = valor_pago + :valor"
                " WHERE id = :id AND status != 'pago' AND (valor_pago + :valor) <= valor_total"
            ),
            {"valor": valor_float, "id": conta_id},
        )
        if res.rowcount == 0:
            conta = session.get(ContaReceber, conta_id)
            if conta is None:
                raise ContaNaoEncontradaError(f"Conta a receber {conta_id} não encontrada.")
            if conta.status == StatusContaEnum.pago:
                raise ContaJaPagaError("Conta já está totalmente paga.")
            raise PagamentoExcedeValorError("Pagamento excede o valor restante da conta.")

        session.execute(
            text(
                "UPDATE contas_receber"
                " SET status = CASE"
                "   WHEN valor_pago >= valor_total THEN 'pago'"
                "   WHEN valor_pago > 0 THEN 'pago_parcialmente'"
                "   ELSE 'pendente'"
                " END"
                " WHERE id = :id"
            ),
            {"id": conta_id},
        )

        try:
            forma_enum = FormaPagamentoEnum[forma]
        except KeyError:
            forma_enum = FormaPagamentoEnum(forma)

        pagamento = PagamentoContaReceber(
            conta_receber_id=conta_id,
            valor=valor,
            forma_pagamento=forma_enum,
            data_pagamento=data,
            observacoes=obs,
        )
        session.add(pagamento)
        session.flush()
        session.expunge_all()
        return pagamento


def listar_contas_receber(
    status: str | None = None,
    vencimento_ate: date | None = None,
) -> list[ContaReceber]:
    with get_session() as session:
        stmt = select(ContaReceber).options(
            joinedload(ContaReceber.cliente),
            joinedload(ContaReceber.pagamentos),
        )
        if status:
            stmt = stmt.where(ContaReceber.status == StatusContaEnum[status])
        if vencimento_ate:
            stmt = stmt.where(ContaReceber.vencimento <= vencimento_ate)
        stmt = stmt.order_by(ContaReceber.vencimento.asc())
        contas = session.execute(stmt).unique().scalars().all()
        session.expunge_all()
        return contas


def obter_conta_receber(conta_id: int) -> ContaReceber:
    with get_session() as session:
        conta = session.execute(
            select(ContaReceber)
            .where(ContaReceber.id == conta_id)
            .options(
                joinedload(ContaReceber.cliente),
                joinedload(ContaReceber.orcamento),
                joinedload(ContaReceber.pagamentos),
            )
        ).unique().scalar_one_or_none()
        if conta is None:
            raise ContaNaoEncontradaError(f"Conta a receber {conta_id} não encontrada.")
        session.expunge_all()
        return conta
