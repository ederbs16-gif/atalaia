from __future__ import annotations

from decimal import Decimal

from sqlalchemy import text

from atalaia.db.session import get_session


def obter_dados_dashboard() -> dict:
    with get_session() as session:
        # ── Vendas hoje ──────────────────────────────────────────────────
        row = session.execute(text("""
            SELECT
                COUNT(*)                      AS total,
                COALESCE(SUM(total), 0)       AS valor
            FROM vendas
            WHERE status = 'finalizada'
              AND DATE(criado_em) = CURDATE()
        """)).fetchone()
        total_vendas = int(row[0])
        valor_vendas = Decimal(str(row[1]))
        ticket_medio = (valor_vendas / total_vendas).quantize(Decimal("0.01")) if total_vendas else Decimal("0")

        # ── Caixa aberto ─────────────────────────────────────────────────
        row_cx = session.execute(text("""
            SELECT status, saldo_inicial,
                   COALESCE(total_dinheiro,0) + COALESCE(total_pix,0)
                   + COALESCE(total_debito,0) + COALESCE(total_credito,0) AS total_vendas
            FROM caixas
            WHERE status = 'aberto'
            ORDER BY id DESC
            LIMIT 1
        """)).fetchone()
        if row_cx:
            caixa_status = {
                "aberto": True,
                "saldo_inicial": Decimal(str(row_cx[1])),
                "total_vendas": Decimal(str(row_cx[2])),
            }
        else:
            caixa_status = {"aberto": False, "saldo_inicial": Decimal("0"), "total_vendas": Decimal("0")}

        # ── Orçamentos pendentes ──────────────────────────────────────────
        r_orc = session.execute(text("""
            SELECT
                SUM(CASE WHEN status = 'aberto' THEN 1 ELSE 0 END)                          AS abertos,
                SUM(CASE WHEN status = 'aberto' AND data_validade = CURDATE() THEN 1 ELSE 0 END) AS vencendo_hoje,
                SUM(CASE WHEN status = 'aberto' AND data_validade < CURDATE() THEN 1 ELSE 0 END) AS vencidos
            FROM orcamentos
        """)).fetchone()
        orcamentos_pendentes = {
            "abertos":        int(r_orc[0] or 0),
            "vencendo_hoje":  int(r_orc[1] or 0),
            "vencidos":       int(r_orc[2] or 0),
        }

        # ── Estoque baixo (top 5 mais críticos) ──────────────────────────
        rows_est = session.execute(text("""
            SELECT nome, estoque_atual, estoque_minimo,
                   (estoque_minimo - estoque_atual) AS diferenca
            FROM produtos
            WHERE ativo = TRUE
              AND controla_estoque = TRUE
              AND estoque_atual < estoque_minimo
            ORDER BY diferenca DESC
            LIMIT 5
        """)).fetchall()
        estoque_itens = [
            {
                "nome": r[0],
                "estoque_atual": int(r[1]),
                "estoque_minimo": int(r[2]),
                "diferenca": int(r[3]),
            }
            for r in rows_est
        ]

        r_est_count = session.execute(text("""
            SELECT COUNT(*) FROM produtos
            WHERE ativo = TRUE AND controla_estoque = TRUE
              AND estoque_atual < estoque_minimo
        """)).scalar()
        estoque_baixo = {"count": int(r_est_count or 0), "itens": estoque_itens}

        # ── Contas a pagar — listas detalhadas ───────────────────────────
        rows_cp_hoje = session.execute(text("""
            SELECT descricao, (valor_total - valor_pago) AS saldo, status
            FROM contas_pagar
            WHERE vencimento = CURDATE()
              AND status != 'pago'
            ORDER BY saldo DESC
        """)).fetchall()
        contas_pagar_hoje = [
            {"descricao": r[0], "valor": Decimal(str(r[1])), "status": r[2]}
            for r in rows_cp_hoje
        ]

        rows_cp_semana = session.execute(text("""
            SELECT descricao, vencimento, (valor_total - valor_pago) AS saldo, status
            FROM contas_pagar
            WHERE vencimento > CURDATE()
              AND vencimento <= DATE_ADD(CURDATE(), INTERVAL 7 DAY)
              AND status != 'pago'
            ORDER BY vencimento ASC, saldo DESC
        """)).fetchall()
        contas_pagar_semana = [
            {"descricao": r[0], "vencimento": r[1], "valor": Decimal(str(r[2])), "status": r[3]}
            for r in rows_cp_semana
        ]

        contas_vencer_hoje = {
            "count": len(contas_pagar_hoje),
            "valor": sum((c["valor"] for c in contas_pagar_hoje), Decimal("0")),
        }
        contas_vencer_semana = {
            "count": len(contas_pagar_semana),
            "valor": sum((c["valor"] for c in contas_pagar_semana), Decimal("0")),
        }

        # ── Contas a receber — listas detalhadas ──────────────────────────
        rows_cr_hoje = session.execute(text("""
            SELECT descricao, (valor_total - valor_pago) AS saldo, status
            FROM contas_receber
            WHERE vencimento = CURDATE()
              AND status != 'pago'
            ORDER BY saldo DESC
        """)).fetchall()
        contas_receber_hoje_lista = [
            {"descricao": r[0], "valor": Decimal(str(r[1])), "status": r[2]}
            for r in rows_cr_hoje
        ]

        rows_cr_semana = session.execute(text("""
            SELECT descricao, vencimento, (valor_total - valor_pago) AS saldo, status
            FROM contas_receber
            WHERE vencimento > CURDATE()
              AND vencimento <= DATE_ADD(CURDATE(), INTERVAL 7 DAY)
              AND status != 'pago'
            ORDER BY vencimento ASC, saldo DESC
        """)).fetchall()
        contas_receber_semana = [
            {"descricao": r[0], "vencimento": r[1], "valor": Decimal(str(r[2])), "status": r[3]}
            for r in rows_cr_semana
        ]

        contas_receber_hoje = {
            "count": len(contas_receber_hoje_lista),
            "valor": sum((c["valor"] for c in contas_receber_hoje_lista), Decimal("0")),
        }

    return {
        "vendas_hoje": {
            "total": total_vendas,
            "valor": valor_vendas,
            "ticket_medio": ticket_medio,
        },
        "caixa_status": caixa_status,
        "orcamentos_pendentes": orcamentos_pendentes,
        "estoque_baixo": estoque_baixo,
        # listas detalhadas
        "contas_pagar_hoje":         contas_pagar_hoje,
        "contas_pagar_semana":       contas_pagar_semana,
        "contas_receber_hoje_lista": contas_receber_hoje_lista,
        "contas_receber_semana":     contas_receber_semana,
        # totais agregados (retrocompatibilidade)
        "contas_vencer_hoje":   contas_vencer_hoje,
        "contas_vencer_semana": contas_vencer_semana,
        "contas_receber_hoje":  contas_receber_hoje,
    }
