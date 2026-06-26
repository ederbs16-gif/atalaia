"""Testes unitários para o módulo whatsapp de orçamentos."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from atalaia.modules.orcamentos.whatsapp import (
    limpar_telefone,
    gerar_link_whatsapp,
    gerar_mensagem_orcamento,
)


# ── helpers ──────────────────────────────────────────────────────────────────

def _orc(
    numero=1,
    cliente_nome="João Silva",
    cliente_tel="11999999999",
    itens=None,
    desconto=Decimal("0"),
    data_validade=date(2025, 12, 31),
):
    orc = MagicMock()
    orc.numero = numero

    cliente = MagicMock()
    cliente.nome = cliente_nome
    cliente.telefone = cliente_tel
    orc.cliente = cliente

    if itens is None:
        item = MagicMock()
        item.quantidade = 2
        item.preco_unitario = Decimal("50.00")
        produto = MagicMock()
        produto.nome = "Produto Teste"
        item.produto = produto
        itens = [item]
    orc.itens = itens

    orc.desconto_percentual = desconto
    orc.data_validade = data_validade

    # numero_formatado é importado de service; mock direto no objeto
    return orc


# ── limpar_telefone ───────────────────────────────────────────────────────────

def test_limpar_telefone_com_mascara():
    assert limpar_telefone("(11) 99999-9999") == "5511999999999"


def test_limpar_telefone_so_digitos():
    assert limpar_telefone("11999999999") == "5511999999999"


def test_limpar_telefone_nao_duplica_55():
    assert limpar_telefone("5511999999999") == "5511999999999"


def test_limpar_telefone_com_espacos_e_tracos():
    assert limpar_telefone("+55 (11) 9 9999-9999") == "5511999999999"


# ── gerar_link_whatsapp ───────────────────────────────────────────────────────

def test_gerar_link_sem_cliente_retorna_none():
    orc = _orc()
    orc.cliente = None
    assert gerar_link_whatsapp(orc, "Empresa") is None


def test_gerar_link_sem_telefone_retorna_none():
    orc = _orc(cliente_tel="")
    assert gerar_link_whatsapp(orc, "Empresa") is None


def test_gerar_link_comeca_com_wa_me_55(monkeypatch):
    monkeypatch.setattr(
        "atalaia.modules.orcamentos.whatsapp.service.numero_formatado",
        lambda orc: "ORC-0001",
    )
    orc = _orc(cliente_tel="11999999999")
    link = gerar_link_whatsapp(orc, "Empresa Teste")
    assert link is not None
    assert link.startswith("https://wa.me/55")


# ── gerar_mensagem_orcamento ──────────────────────────────────────────────────

def test_mensagem_contem_numero_formatado(monkeypatch):
    monkeypatch.setattr(
        "atalaia.modules.orcamentos.whatsapp.service.numero_formatado",
        lambda orc: "ORC-0042",
    )
    msg = gerar_mensagem_orcamento(_orc(), "Empresa")
    assert "ORC-0042" in msg


def test_mensagem_contem_nome_cliente(monkeypatch):
    monkeypatch.setattr(
        "atalaia.modules.orcamentos.whatsapp.service.numero_formatado",
        lambda orc: "ORC-0001",
    )
    msg = gerar_mensagem_orcamento(_orc(cliente_nome="Maria Souza"), "Empresa")
    assert "Maria Souza" in msg


def test_mensagem_sem_desconto_nao_mostra_linha_desconto(monkeypatch):
    monkeypatch.setattr(
        "atalaia.modules.orcamentos.whatsapp.service.numero_formatado",
        lambda orc: "ORC-0001",
    )
    msg = gerar_mensagem_orcamento(_orc(desconto=Decimal("0")), "Empresa")
    assert "Desconto" not in msg


def test_mensagem_com_desconto_mostra_linha_desconto(monkeypatch):
    monkeypatch.setattr(
        "atalaia.modules.orcamentos.whatsapp.service.numero_formatado",
        lambda orc: "ORC-0001",
    )
    msg = gerar_mensagem_orcamento(_orc(desconto=Decimal("10")), "Empresa")
    assert "Desconto" in msg
    assert "10%" in msg
