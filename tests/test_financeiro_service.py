"""Testes de service do módulo Financeiro."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from atalaia.db.base import Base
import atalaia.db.models  # noqa: F401

from atalaia.db.models.caixa import Caixa, StatusCaixaEnum
from atalaia.db.models.conta_pagar import ContaPagar, StatusContaEnum
from atalaia.modules.financeiro import caixa_service, contas_service
from atalaia.modules.financeiro.exceptions import (
    CaixaJaAbertoError,
    ContaJaPagaError,
    PagamentoExcedeValorError,
)


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
def patch_services(SM, monkeypatch):
    @contextmanager
    def _session():
        s = SM()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    monkeypatch.setattr(caixa_service, "get_session", _session)
    monkeypatch.setattr(contas_service, "get_session", _session)
    yield
    with SM() as s:
        s.execute(text("DELETE FROM pagamentos_conta_receber"))
        s.execute(text("DELETE FROM pagamentos_conta_pagar"))
        s.execute(text("DELETE FROM contas_receber"))
        s.execute(text("DELETE FROM contas_pagar"))
        s.execute(text("DELETE FROM caixas"))
        s.commit()


def _abrir_caixa(SM) -> int:
    with SM() as s:
        c = Caixa(
            hostname="test",
            saldo_inicial=Decimal("100"),
            total_dinheiro=Decimal("0"),
            total_pix=Decimal("0"),
            total_debito=Decimal("0"),
            total_credito=Decimal("0"),
            status=StatusCaixaEnum.aberto,
        )
        s.add(c)
        s.commit()
        s.refresh(c)
        return c.id


def _criar_conta(SM, valor_total: Decimal = Decimal("100")) -> int:
    with SM() as s:
        c = ContaPagar(
            descricao="Teste",
            valor_total=valor_total,
            valor_pago=Decimal("0"),
            status=StatusContaEnum.pendente,
            vencimento=date.today(),
        )
        s.add(c)
        s.commit()
        s.refresh(c)
        return c.id


# ─── Caixa ────────────────────────────────────────────────────────────────────

def test_abrir_caixa_ja_aberto_levanta_erro(SM):
    _abrir_caixa(SM)
    with pytest.raises(CaixaJaAbertoError):
        caixa_service.abrir_caixa(saldo_inicial=Decimal("50"))


def test_fechar_caixa_seta_status_e_fechado_em(SM):
    caixa_id = _abrir_caixa(SM)
    caixa = caixa_service.fechar_caixa(caixa_id)
    assert caixa.status == StatusCaixaEnum.fechado
    assert caixa.fechado_em is not None


# ─── Contas a Pagar ───────────────────────────────────────────────────────────

def test_registrar_pagamento_pagar_atualiza_valor_pago_e_status(SM):
    conta_id = _criar_conta(SM, Decimal("100"))
    contas_service.registrar_pagamento_pagar(conta_id, Decimal("60"), "dinheiro", date.today())
    contas_service.registrar_pagamento_pagar(conta_id, Decimal("40"), "pix", date.today())
    with SM() as s:
        conta = s.get(ContaPagar, conta_id)
        assert conta.valor_pago == Decimal("100")
        assert conta.status == StatusContaEnum.pago


def test_registrar_pagamento_pagar_excedendo_valor_levanta_erro(SM):
    conta_id = _criar_conta(SM, Decimal("100"))
    with pytest.raises(PagamentoExcedeValorError):
        contas_service.registrar_pagamento_pagar(conta_id, Decimal("150"), "dinheiro", date.today())


def test_criar_conta_pagar_parcelada_cria_N_contas(SM):
    dados = {
        "descricao": "Parcela teste",
        "valor_total": Decimal("300"),
        "vencimento": date.today(),
    }
    contas = contas_service.criar_conta_pagar_parcelada(dados, 3)
    assert len(contas) == 3
    grupos = {c.grupo_parcelas for c in contas}
    assert len(grupos) == 1
    numeros = {c.parcela_numero for c in contas}
    assert numeros == {1, 2, 3}


def test_conta_ja_paga_levanta_erro(SM):
    conta_id = _criar_conta(SM, Decimal("100"))
    contas_service.registrar_pagamento_pagar(conta_id, Decimal("100"), "dinheiro", date.today())
    with pytest.raises(ContaJaPagaError):
        contas_service.registrar_pagamento_pagar(conta_id, Decimal("1"), "pix", date.today())
