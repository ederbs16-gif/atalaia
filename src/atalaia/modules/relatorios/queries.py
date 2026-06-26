from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import text

from atalaia.db.session import get_session


def vendas_por_periodo(data_inicio: date, data_fim: date) -> dict:
    with get_session() as session:
        # Totais gerais
        row = session.execute(
            text(
                "SELECT"
                "  COUNT(*) AS total_vendas,"
                "  COALESCE(SUM(total / (1 - desconto_percentual / 100)), 0) AS valor_bruto,"
                "  COALESCE(SUM(total * desconto_percentual / 100"
                "           / (1 - desconto_percentual / 100)), 0) AS valor_desconto,"
                "  COALESCE(SUM(total), 0) AS valor_liquido"
                " FROM vendas"
                " WHERE status = 'finalizada'"
                "   AND DATE(criado_em) BETWEEN :ini AND :fim"
            ),
            {"ini": data_inicio, "fim": data_fim},
        ).fetchone()

        total_vendas = int(row[0])
        valor_bruto = Decimal(str(row[1]))
        valor_desconto = Decimal(str(row[2]))
        valor_liquido = Decimal(str(row[3]))
        ticket_medio = (valor_liquido / total_vendas).quantize(Decimal("0.01")) if total_vendas else Decimal("0")

        # Agrupado por dia para gráfico
        dias = session.execute(
            text(
                "SELECT DATE(criado_em) AS dia, COALESCE(SUM(total), 0) AS valor"
                " FROM vendas"
                " WHERE status = 'finalizada'"
                "   AND DATE(criado_em) BETWEEN :ini AND :fim"
                " GROUP BY DATE(criado_em)"
                " ORDER BY dia"
            ),
            {"ini": data_inicio, "fim": data_fim},
        ).fetchall()

        return {
            "total_vendas": total_vendas,
            "valor_bruto": valor_bruto,
            "valor_desconto": valor_desconto,
            "valor_liquido": valor_liquido,
            "ticket_medio": ticket_medio,
            "agrupado_por_dia": [
                {"data": str(r[0]), "valor": Decimal(str(r[1]))}
                for r in dias
            ],
        }


def produtos_mais_vendidos(
    data_inicio: date, data_fim: date, limit: int = 10
) -> list[dict]:
    with get_session() as session:
        rows = session.execute(
            text(
                "SELECT p.nome, c.nome AS categoria,"
                "  SUM(iv.quantidade) AS quantidade_total,"
                "  SUM(iv.quantidade * iv.preco_unitario) AS valor_total"
                " FROM itens_venda iv"
                " JOIN vendas v ON v.id = iv.venda_id"
                " JOIN produtos p ON p.id = iv.produto_id"
                " LEFT JOIN categorias c ON c.id = p.categoria_id"
                " WHERE v.status = 'finalizada'"
                "   AND DATE(v.criado_em) BETWEEN :ini AND :fim"
                " GROUP BY p.id, p.nome, c.nome"
                " ORDER BY quantidade_total DESC"
                " LIMIT :lim"
            ),
            {"ini": data_inicio, "fim": data_fim, "lim": limit},
        ).fetchall()

        return [
            {
                "nome": r[0],
                "categoria": r[1] or "—",
                "quantidade_total": int(r[2]),
                "valor_total": Decimal(str(r[3])),
            }
            for r in rows
        ]


def estoque_baixo() -> list[dict]:
    with get_session() as session:
        rows = session.execute(
            text(
                "SELECT p.nome, c.nome AS categoria,"
                "  p.estoque_atual, p.estoque_minimo,"
                "  (p.estoque_atual - p.estoque_minimo) AS diferenca"
                " FROM produtos p"
                " LEFT JOIN categorias c ON c.id = p.categoria_id"
                " WHERE p.ativo = TRUE"
                "   AND p.controla_estoque = TRUE"
                "   AND p.estoque_atual <= p.estoque_minimo"
                " ORDER BY diferenca ASC, p.nome ASC"
            )
        ).fetchall()

        return [
            {
                "nome": r[0],
                "categoria": r[1] or "—",
                "estoque_atual": int(r[2]),
                "estoque_minimo": int(r[3]),
                "diferenca": int(r[4]),
            }
            for r in rows
        ]


def fluxo_de_caixa(data_inicio: date, data_fim: date) -> dict:
    with get_session() as session:
        # Entradas: pagamentos de venda no período
        entradas = session.execute(
            text(
                "SELECT pv.forma, COALESCE(SUM(pv.valor), 0)"
                " FROM pagamentos_venda pv"
                " JOIN vendas v ON v.id = pv.venda_id"
                " WHERE v.status = 'finalizada'"
                "   AND DATE(pv.criado_em) BETWEEN :ini AND :fim"
                " GROUP BY pv.forma"
            ),
            {"ini": data_inicio, "fim": data_fim},
        ).fetchall()

        por_forma = {"dinheiro": Decimal("0"), "pix": Decimal("0"),
                     "debito": Decimal("0"), "credito": Decimal("0")}
        for forma, valor in entradas:
            if forma in por_forma:
                por_forma[forma] = Decimal(str(valor))

        entradas_total = sum(por_forma.values())

        # Saídas: pagamentos de contas a pagar no período
        saidas_row = session.execute(
            text(
                "SELECT COALESCE(SUM(valor), 0)"
                " FROM pagamentos_conta_pagar"
                " WHERE DATE(criado_em) BETWEEN :ini AND :fim"
            ),
            {"ini": data_inicio, "fim": data_fim},
        ).fetchone()
        saidas_total = Decimal(str(saidas_row[0]))

        # Por dia para gráfico
        por_dia_entradas = session.execute(
            text(
                "SELECT DATE(pv.criado_em) AS dia, COALESCE(SUM(pv.valor), 0)"
                " FROM pagamentos_venda pv"
                " JOIN vendas v ON v.id = pv.venda_id"
                " WHERE v.status = 'finalizada'"
                "   AND DATE(pv.criado_em) BETWEEN :ini AND :fim"
                " GROUP BY DATE(pv.criado_em)"
                " ORDER BY dia"
            ),
            {"ini": data_inicio, "fim": data_fim},
        ).fetchall()

        por_dia_saidas = session.execute(
            text(
                "SELECT DATE(criado_em) AS dia, COALESCE(SUM(valor), 0)"
                " FROM pagamentos_conta_pagar"
                " WHERE DATE(criado_em) BETWEEN :ini AND :fim"
                " GROUP BY DATE(criado_em)"
                " ORDER BY dia"
            ),
            {"ini": data_inicio, "fim": data_fim},
        ).fetchall()

        dias_ent = {str(r[0]): Decimal(str(r[1])) for r in por_dia_entradas}
        dias_sai = {str(r[0]): Decimal(str(r[1])) for r in por_dia_saidas}
        todas_datas = sorted(set(dias_ent) | set(dias_sai))

        return {
            "entradas_total": entradas_total,
            "saidas_total": saidas_total,
            "saldo": entradas_total - saidas_total,
            "por_forma": por_forma,
            "por_dia": [
                {
                    "data": d,
                    "entrada": dias_ent.get(d, Decimal("0")),
                    "saida": dias_sai.get(d, Decimal("0")),
                }
                for d in todas_datas
            ],
        }


def contas_a_pagar_receber(data_inicio: date, data_fim: date) -> dict:
    hoje = date.today()

    with get_session() as session:
        def _resumo_pagar():
            rows = session.execute(
                text(
                    "SELECT descricao, vencimento, valor_total, valor_pago, status"
                    " FROM contas_pagar"
                    " WHERE vencimento BETWEEN :ini AND :fim"
                    " ORDER BY vencimento ASC"
                ),
                {"ini": data_inicio, "fim": data_fim},
            ).fetchall()

            total_pendente = Decimal("0")
            total_vencido = Decimal("0")
            total_pago = Decimal("0")
            itens = []
            for r in rows:
                descricao, vencimento, valor_total, valor_pago, status = r
                restante = Decimal(str(valor_total)) - Decimal(str(valor_pago))
                if status == "pago":
                    total_pago += Decimal(str(valor_total))
                elif vencimento < hoje:
                    total_vencido += restante
                else:
                    total_pendente += restante
                itens.append({
                    "descricao": descricao,
                    "vencimento": str(vencimento),
                    "valor_total": Decimal(str(valor_total)),
                    "valor_pago": Decimal(str(valor_pago)),
                    "status": status,
                    "vencido": status != "pago" and vencimento < hoje,
                })
            return {"total_pendente": total_pendente, "total_vencido": total_vencido,
                    "total_pago": total_pago, "itens": itens}

        def _resumo_receber():
            rows = session.execute(
                text(
                    "SELECT descricao, vencimento, valor_total, valor_pago, status"
                    " FROM contas_receber"
                    " WHERE vencimento BETWEEN :ini AND :fim"
                    " ORDER BY vencimento ASC"
                ),
                {"ini": data_inicio, "fim": data_fim},
            ).fetchall()

            total_pendente = Decimal("0")
            total_vencido = Decimal("0")
            total_pago = Decimal("0")
            itens = []
            for r in rows:
                descricao, vencimento, valor_total, valor_pago, status = r
                restante = Decimal(str(valor_total)) - Decimal(str(valor_pago))
                if status == "pago":
                    total_pago += Decimal(str(valor_total))
                elif vencimento < hoje:
                    total_vencido += restante
                else:
                    total_pendente += restante
                itens.append({
                    "descricao": descricao,
                    "vencimento": str(vencimento),
                    "valor_total": Decimal(str(valor_total)),
                    "valor_pago": Decimal(str(valor_pago)),
                    "status": status,
                    "vencido": status != "pago" and vencimento < hoje,
                })
            return {"total_pendente": total_pendente, "total_vencido": total_vencido,
                    "total_pago": total_pago, "itens": itens}

        return {"pagar": _resumo_pagar(), "receber": _resumo_receber()}
