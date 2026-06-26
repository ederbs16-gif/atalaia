from __future__ import annotations

import socket
from datetime import datetime
from decimal import Decimal

from sqlalchemy import select, text

from atalaia.db.session import get_session
from atalaia.db.models.caixa import Caixa, StatusCaixaEnum
from atalaia.db.models.configuracao import Configuracao
from atalaia.modules.financeiro.exceptions import (
    CaixaJaAbertoError,
    CaixaNaoAbertoError,
    CaixaJaFechadoError,
)

_COL = {
    "dinheiro": "total_dinheiro",
    "pix": "total_pix",
    "debito": "total_debito",
    "credito": "total_credito",
}


def _caixa_individual() -> bool:
    with get_session() as session:
        cfg = session.execute(
            select(Configuracao).where(Configuracao.chave == "caixa_individual")
        ).scalar_one_or_none()
        if cfg is None:
            return False
        return (cfg.valor or "").lower() in ("true", "1", "sim")


def abrir_caixa(saldo_inicial: Decimal = Decimal("0"), observacoes: str | None = None) -> Caixa:
    individual = _caixa_individual()
    hostname = socket.gethostname()
    with get_session() as session:
        stmt = select(Caixa).where(Caixa.status == StatusCaixaEnum.aberto)
        if individual:
            stmt = stmt.where(Caixa.hostname == hostname)
        existente = session.execute(stmt).scalars().first()
        if existente is not None:
            raise CaixaJaAbertoError("Já existe um caixa aberto.")
        caixa = Caixa(
            hostname=hostname,
            saldo_inicial=saldo_inicial,
            total_dinheiro=Decimal("0"),
            total_pix=Decimal("0"),
            total_debito=Decimal("0"),
            total_credito=Decimal("0"),
            status=StatusCaixaEnum.aberto,
            observacoes=observacoes,
        )
        session.add(caixa)
        session.flush()
        session.expunge(caixa)
        return caixa


def fechar_caixa(caixa_id: int, observacoes: str | None = None) -> Caixa:
    with get_session() as session:
        caixa = session.get(Caixa, caixa_id)
        if caixa is None:
            raise CaixaNaoAbertoError(f"Caixa {caixa_id} não encontrado.")
        if caixa.status == StatusCaixaEnum.fechado:
            raise CaixaJaFechadoError("Caixa já está fechado.")
        caixa.status = StatusCaixaEnum.fechado
        caixa.fechado_em = datetime.now()
        if observacoes:
            caixa.observacoes = observacoes
        session.flush()
        session.expunge(caixa)
        return caixa


def obter_caixa_aberto() -> Caixa | None:
    individual = _caixa_individual()
    hostname = socket.gethostname()
    with get_session() as session:
        stmt = select(Caixa).where(Caixa.status == StatusCaixaEnum.aberto)
        if individual:
            stmt = stmt.where(Caixa.hostname == hostname)
        caixa = session.execute(stmt).scalars().first()
        if caixa is not None:
            session.expunge(caixa)
        return caixa


def registrar_pagamento_caixa(caixa_id: int, forma: str, valor: Decimal) -> None:
    if forma not in _COL:
        raise ValueError(f"Forma de pagamento inválida: {forma!r}. Use: {list(_COL)}")
    col = _COL[forma]
    with get_session() as session:
        session.execute(
            text(f"UPDATE caixas SET {col} = {col} + :valor WHERE id = :id"),
            {"valor": valor, "id": caixa_id},
        )


def listar_caixas(limit: int = 30) -> list[Caixa]:
    with get_session() as session:
        caixas = session.execute(
            select(Caixa).order_by(Caixa.aberto_em.desc()).limit(limit)
        ).scalars().all()
        session.expunge_all()
        return caixas
