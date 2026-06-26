"""
Script de seed para popular o banco MySQL com dados de simulação.
Idempotente: verifica existência antes de inserir, não duplica.

Uso:
    $env:PYTHONPATH = "src"; python scripts/popular_banco.py
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, text

from atalaia.db.session import get_session

# ── serviços ─────────────────────────────────────────────────────────────────
from atalaia.modules.produtos.service import criar_categoria, criar_produto, listar_categorias
from atalaia.modules.entrada_mercadorias.fornecedor_service import criar_fornecedor
from atalaia.modules.clientes.service import criar_cliente
from atalaia.modules.orcamentos.service import criar_orcamento, adicionar_item as orc_adicionar_item
from atalaia.modules.financeiro.caixa_service import abrir_caixa, obter_caixa_aberto
from atalaia.modules.pdv.venda_service import (
    iniciar_venda, adicionar_item as venda_adicionar_item,
    adicionar_pagamento, finalizar_venda,
)
from atalaia.modules.financeiro.contas_service import criar_conta_pagar, criar_conta_receber

# ── modelos (apenas para lookup) ─────────────────────────────────────────────
from atalaia.db.models.categoria import Categoria
from atalaia.db.models.produto import Produto
from atalaia.db.models.fornecedor import Fornecedor
from atalaia.db.models.cliente import Cliente
from atalaia.db.models.orcamento import Orcamento, StatusOrcamentoEnum

HOJE = date.today()


def _ok(msg: str) -> None:
    print(f"  ✓ {msg}")


def _skip(msg: str) -> None:
    print(f"  · {msg} (já existe, pulando)")


def _err(msg: str, e: Exception) -> None:
    print(f"  ✗ {msg}: {e}", file=sys.stderr)


# ── Categorias ────────────────────────────────────────────────────────────────

def _popular_categorias() -> dict[str, int]:
    print("\n[1/8] Categorias...")
    nomes = ["Papelaria", "Informática", "Impressão", "Encadernação", "Serviços"]
    with get_session() as session:
        existentes = {c.nome: c.id for c in session.execute(select(Categoria)).scalars()}

    ids: dict[str, int] = {}
    for nome in nomes:
        if nome in existentes:
            ids[nome] = existentes[nome]
            _skip(nome)
        else:
            try:
                cat = criar_categoria(nome)
                ids[nome] = cat.id
                _ok(f"Categoria '{nome}' criada (id={cat.id})")
            except Exception as e:
                _err(f"Categoria '{nome}'", e)
    return ids


# ── Produtos ──────────────────────────────────────────────────────────────────

def _popular_produtos(cat_ids: dict[str, int]) -> dict[str, int]:
    print("\n[2/8] Produtos...")

    PRODUTOS = [
        # (nome, tipo, categoria, preco_venda, controla, estoque_atual, estoque_minimo)
        ("Resma Papel A4",             "produto",  "Papelaria",    Decimal("25.90"), True,  50,  20),
        ("Caneta Azul BIC",            "produto",  "Papelaria",    Decimal("1.50"),  True,  200, 50),
        ("Lápis HB",                   "produto",  "Papelaria",    Decimal("0.80"),  True,  5,   30),
        ("Pasta L",                    "produto",  "Papelaria",    Decimal("3.50"),  True,  80,  20),
        ("Cartucho HP 664 Preto",      "produto",  "Informática",  Decimal("45.00"), True,  8,   10),
        ("Cartucho HP 664 Colorido",   "produto",  "Informática",  Decimal("55.00"), True,  3,   10),
        ("Pendrive 32GB",              "produto",  "Informática",  Decimal("35.00"), True,  15,  5),
        ("Mouse USB",                  "produto",  "Informática",  Decimal("28.00"), True,  4,   5),
        ("Impressão P&B A4",           "servico",  "Impressão",    Decimal("0.50"),  False, 0,   0),
        ("Impressão Colorida A4",      "servico",  "Impressão",    Decimal("1.50"),  False, 0,   0),
        ("Plastificação A4",           "servico",  "Impressão",    Decimal("3.00"),  False, 0,   0),
        ("Encadernação até 50 folhas", "servico",  "Encadernação", Decimal("8.00"),  False, 0,   0),
        ("Encadernação até 100 folhas","servico",  "Encadernação", Decimal("12.00"), False, 0,   0),
        ("Digitalização por página",   "servico",  "Serviços",     Decimal("1.00"),  False, 0,   0),
        ("Suporte Técnico hora",       "servico",  "Serviços",     Decimal("80.00"), False, 0,   0),
    ]

    with get_session() as session:
        existentes = {p.nome: p.id for p in session.execute(select(Produto)).scalars()}

    ids: dict[str, int] = {}
    for nome, tipo, cat_nome, preco, controla, estoque, minimo in PRODUTOS:
        if nome in existentes:
            ids[nome] = existentes[nome]
            _skip(nome)
            continue
        try:
            dados = {
                "nome": nome,
                "tipo": tipo,
                "categoria_id": cat_ids.get(cat_nome),
                "preco_venda": preco,
                "controla_estoque": controla,
                "estoque_atual": estoque,
                "estoque_minimo": minimo,
                "ativo": True,
            }
            p = criar_produto(dados)
            ids[nome] = p.id
            _ok(f"'{nome}' (id={p.id})")
        except Exception as e:
            _err(nome, e)

    return ids


# ── Fornecedores ──────────────────────────────────────────────────────────────

def _popular_fornecedores() -> dict[str, int]:
    print("\n[3/8] Fornecedores...")

    FORN = [
        ("Distribuidora Papelaria SP", "12.345.678/0001-90", "11 3333-4444"),
        ("InfoTech Distribuidora",     "98.765.432/0001-10", "11 5555-6666"),
        ("Suprimentos Office Ltda",    "11.222.333/0001-44", "11 7777-8888"),
    ]

    with get_session() as session:
        existentes = {f.nome: f.id for f in session.execute(select(Fornecedor)).scalars()}

    ids: dict[str, int] = {}
    for nome, cnpj, tel in FORN:
        if nome in existentes:
            ids[nome] = existentes[nome]
            _skip(nome)
            continue
        try:
            f = criar_fornecedor({"nome": nome, "documento": cnpj, "telefone": tel})
            ids[nome] = f.id
            _ok(f"'{nome}' (id={f.id})")
        except Exception as e:
            _err(nome, e)

    return ids


# ── Clientes ──────────────────────────────────────────────────────────────────

def _popular_clientes() -> dict[str, int]:
    print("\n[4/8] Clientes...")

    CLIENTES = [
        ("João Silva",       "11999991111", "111.222.333-44"),
        ("Maria Santos",     "11999992222", "222.333.444-55"),
        ("Pedro Oliveira",   "11999993333", "333.444.555-66"),
        ("Ana Costa",        "11999994444", "444.555.666-77"),
        ("Carlos Ferreira",  "11999995555", "555.666.777-88"),
        ("Lucia Mendes",     "11999996666", "666.777.888-99"),
        ("Roberto Lima",     "11999997777", "777.888.999-00"),
        ("Empresa ABC Ltda", "11999998888", "99.888.777/0001-66"),
    ]

    with get_session() as session:
        existentes = {c.nome: c.id for c in session.execute(select(Cliente)).scalars()}

    ids: dict[str, int] = {}
    for nome, tel, doc in CLIENTES:
        if nome in existentes:
            ids[nome] = existentes[nome]
            _skip(nome)
            continue
        try:
            c = criar_cliente({"nome": nome, "telefone": tel, "documento": doc})
            ids[nome] = c.id
            _ok(f"'{nome}' (id={c.id})")
        except Exception as e:
            _err(nome, e)

    return ids


# ── Orçamentos ────────────────────────────────────────────────────────────────

def _popular_orcamentos(cli_ids: dict[str, int], prod_ids: dict[str, int]) -> None:
    print("\n[5/8] Orçamentos...")

    # Verificar se já há orçamentos (por número)
    with get_session() as session:
        total = session.execute(text("SELECT COUNT(*) FROM orcamentos")).scalar()
    if total and total >= 5:
        _skip(f"já existem {total} orçamentos")
        return

    ORCAMENTOS = [
        # (cliente, [(produto, qtd)], status, obs)
        ("João Silva",     [("Impressão Colorida A4", 2), ("Plastificação A4", 1)], "aberto",   ""),
        ("Maria Santos",   [("Resma Papel A4", 1),        ("Caneta Azul BIC", 5)],  "aprovado", ""),
        ("Pedro Oliveira", [("Encadernação até 100 folhas", 1), ("Impressão P&B A4", 20)], "aberto", "URGENTE"),
        ("Ana Costa",      [("Suporte Técnico hora", 1),  ("Digitalização por página", 1)], "recusado", ""),
        ("Empresa ABC Ltda", [("Pendrive 32GB", 2),        ("Mouse USB", 1)],        "aberto",   ""),
    ]

    for cli_nome, itens, status, obs in ORCAMENTOS:
        cli_id = cli_ids.get(cli_nome)
        if not cli_id:
            _err(f"Orçamento para '{cli_nome}'", Exception("cliente não encontrado"))
            continue
        try:
            orc = criar_orcamento(cli_id, validade_dias=10, observacoes=obs or None)
            for prod_nome, qtd in itens:
                prod_id = prod_ids.get(prod_nome)
                if prod_id:
                    orc_adicionar_item(orc.id, prod_id, qtd)
            # Atualizar status se necessário
            if status != "aberto":
                with get_session() as session:
                    session.execute(
                        text("UPDATE orcamentos SET status = :s WHERE id = :id"),
                        {"s": status, "id": orc.id},
                    )
            _ok(f"Orçamento #{orc.numero} para '{cli_nome}' (status={status})")
        except Exception as e:
            _err(f"Orçamento para '{cli_nome}'", e)


# ── Caixa ─────────────────────────────────────────────────────────────────────

def _popular_caixa() -> int | None:
    print("\n[6/8] Caixa...")
    try:
        cx = obter_caixa_aberto()
        if cx:
            _skip(f"caixa já aberto (id={cx.id})")
            return cx.id
        cx = abrir_caixa(saldo_inicial=Decimal("150.00"))
        _ok(f"Caixa aberto (id={cx.id}, saldo_inicial=R$150,00)")
        return cx.id
    except Exception as e:
        _err("Abrir caixa", e)
        return None


# ── Vendas ────────────────────────────────────────────────────────────────────

def _popular_vendas(cli_ids: dict[str, int], prod_ids: dict[str, int], caixa_id: int | None) -> None:
    print("\n[7/8] Vendas...")

    with get_session() as session:
        total = session.execute(text("SELECT COUNT(*) FROM vendas WHERE status = 'finalizada'")).scalar()
    if total and total >= 6:
        _skip(f"já existem {total} vendas finalizadas")
        return

    VENDAS = [
        # (cliente_nome|None, [(prod, qtd)], forma, valor, dias_atras)
        ("João Silva",     [("Impressão P&B A4", 3), ("Plastificação A4", 1)], "dinheiro", Decimal("10.50"), 0),
        (None,             [("Resma Papel A4", 1)],                            "pix",      Decimal("25.90"), 0),
        ("Maria Santos",   [("Caneta Azul BIC", 2), ("Lápis HB", 1)],         "debito",   Decimal("3.80"),  1),
        ("Pedro Oliveira", [("Cartucho HP 664 Preto", 1)],                     "credito",  Decimal("45.00"), 3),
        (None,             [("Encadernação até 50 folhas", 1), ("Impressão Colorida A4", 5)], "dinheiro", Decimal("15.50"), 5),
        ("Carlos Ferreira",[("Mouse USB", 1), ("Pendrive 32GB", 1)],          "pix",      Decimal("63.00"), 6),
    ]

    for cli_nome, itens, forma, valor, dias_atras in VENDAS:
        cli_id = cli_ids.get(cli_nome) if cli_nome else None
        try:
            venda = iniciar_venda(cliente_id=cli_id)
            for prod_nome, qtd in itens:
                prod_id = prod_ids.get(prod_nome)
                if prod_id:
                    try:
                        venda_adicionar_item(venda.id, prod_id, qtd)
                    except Exception as ei:
                        _err(f"  item '{prod_nome}'", ei)
            adicionar_pagamento(venda.id, forma, valor)
            venda_fin = finalizar_venda(venda.id)
            # Ajustar data para simular vendas passadas
            if dias_atras > 0:
                data_passada = HOJE - timedelta(days=dias_atras)
                with get_session() as session:
                    session.execute(
                        text("UPDATE vendas SET criado_em = :d WHERE id = :id"),
                        {"d": data_passada, "id": venda_fin.id},
                    )
            _ok(f"Venda #{venda_fin.id} ({cli_nome or 'anônimo'}, {forma}, R${valor})")
        except Exception as e:
            _err(f"Venda para '{cli_nome or 'anônimo'}'", e)


# ── Contas a Pagar ────────────────────────────────────────────────────────────

def _popular_contas_pagar(forn_ids: dict[str, int]) -> None:
    print("\n[8a/8] Contas a Pagar...")

    with get_session() as session:
        total = session.execute(text("SELECT COUNT(*) FROM contas_pagar")).scalar()
    if total and total >= 6:
        _skip(f"já existem {total} contas a pagar")
        return

    CONTAS = [
        # (descricao, valor, dias_vencimento, fornecedor|None)
        ("Aluguel Dezembro",            Decimal("1200.00"),  0,  None),
        ("Energia Elétrica",            Decimal("280.00"),   1,  None),
        ("Internet Fibra",              Decimal("120.00"),   3,  None),
        ("Fornecedor Papelaria SP - NF 1234", Decimal("450.00"), 5, "Distribuidora Papelaria SP"),
        ("Conta de Água",               Decimal("85.00"),   -1,  None),
        ("InfoTech - Cartuchos",        Decimal("320.00"),  -3,  "InfoTech Distribuidora"),
    ]

    for desc, valor, dias, forn_nome in CONTAS:
        forn_id = forn_ids.get(forn_nome) if forn_nome else None
        venc = HOJE + timedelta(days=dias)
        try:
            criar_conta_pagar({
                "descricao": desc,
                "valor_total": valor,
                "vencimento": venc,
                "fornecedor_id": forn_id,
            })
            _ok(f"'{desc}' (venc={venc}, R${valor})")
        except Exception as e:
            _err(desc, e)


# ── Contas a Receber ──────────────────────────────────────────────────────────

def _popular_contas_receber(cli_ids: dict[str, int]) -> None:
    print("\n[8b/8] Contas a Receber...")

    with get_session() as session:
        total = session.execute(text("SELECT COUNT(*) FROM contas_receber")).scalar()
    if total and total >= 4:
        _skip(f"já existem {total} contas a receber")
        return

    CONTAS = [
        # (descricao, valor, dias_vencimento, cliente|None)
        ("Serviços Empresa ABC",    Decimal("240.00"),  0,  "Empresa ABC Ltda"),
        ("Impressão Roberto Lima",  Decimal("45.00"),   1,  "Roberto Lima"),
        ("Suporte Pedro Oliveira",  Decimal("160.00"),  4,  "Pedro Oliveira"),
        ("Serviços Lucia Mendes",   Decimal("80.00"),  -2,  "Lucia Mendes"),
    ]

    for desc, valor, dias, cli_nome in CONTAS:
        cli_id = cli_ids.get(cli_nome) if cli_nome else None
        venc = HOJE + timedelta(days=dias)
        try:
            criar_conta_receber({
                "descricao": desc,
                "valor_total": valor,
                "vencimento": venc,
                "cliente_id": cli_id,
            })
            _ok(f"'{desc}' (venc={venc}, R${valor})")
        except Exception as e:
            _err(desc, e)


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 60)
    print("  Atalaia — Popular Banco com Dados de Simulação")
    print("=" * 60)

    cat_ids  = _popular_categorias()
    prod_ids = _popular_produtos(cat_ids)
    forn_ids = _popular_fornecedores()
    cli_ids  = _popular_clientes()
    _popular_orcamentos(cli_ids, prod_ids)
    caixa_id = _popular_caixa()
    _popular_vendas(cli_ids, prod_ids, caixa_id)
    _popular_contas_pagar(forn_ids)
    _popular_contas_receber(cli_ids)

    print("\n" + "=" * 60)
    print("  Seed concluído.")
    print(f"  Categorias : {len(cat_ids)}")
    print(f"  Produtos   : {len(prod_ids)}")
    print(f"  Fornecedores: {len(forn_ids)}")
    print(f"  Clientes   : {len(cli_ids)}")
    print("=" * 60)


if __name__ == "__main__":
    main()
