from __future__ import annotations

import re
import webbrowser
from urllib.parse import quote

from atalaia.modules.orcamentos import service


def limpar_telefone(telefone: str) -> str:
    digitos = re.sub(r"\D", "", telefone)
    if digitos.startswith("55") and len(digitos) >= 12:
        return digitos
    return "55" + digitos


def gerar_mensagem_orcamento(orcamento, nome_empresa: str) -> str:
    from decimal import Decimal

    numero = service.numero_formatado(orcamento)
    cliente_nome = orcamento.cliente.nome if orcamento.cliente else "Cliente"
    itens = orcamento.itens or []

    subtotal = sum(i.quantidade * i.preco_unitario for i in itens)
    desconto_pct = Decimal(str(orcamento.desconto_percentual or 0))
    valor_desconto = (subtotal * desconto_pct / Decimal("100")).quantize(Decimal("0.01"))
    total = subtotal - valor_desconto

    linhas = ""
    for item in itens:
        nome_prod = item.produto.nome if item.produto else f"Produto #{item.produto_id}"
        sub = item.quantidade * item.preco_unitario
        linhas += f"• {nome_prod} x{item.quantidade} — R$ {sub:.2f}\n"

    msg = (
        f"Olá {cliente_nome}! 😊\n\n"
        f"Segue seu orçamento *{numero}* da {nome_empresa}.\n\n"
        f"{linhas}"
        f"\n*Subtotal:* R$ {subtotal:.2f}"
    )

    if desconto_pct > 0:
        msg += f"\n*Desconto:* {desconto_pct}% (R$ {valor_desconto:.2f})"

    msg += f"\n*Total:* R$ {total:.2f}"

    if orcamento.data_validade:
        msg += f"\n\n*Validade:* {orcamento.data_validade.strftime('%d/%m/%Y')}"

    msg += "\n\nQualquer dúvida estamos à disposição! 🙏"
    return msg


def gerar_link_whatsapp(orcamento, nome_empresa: str) -> str | None:
    tel = orcamento.cliente.telefone if orcamento.cliente else None
    if not tel or not tel.strip():
        return None
    telefone_limpo = limpar_telefone(tel)
    mensagem = gerar_mensagem_orcamento(orcamento, nome_empresa)
    return f"https://wa.me/{telefone_limpo}?text={quote(mensagem)}"


def abrir_whatsapp(orcamento, nome_empresa: str) -> bool:
    link = gerar_link_whatsapp(orcamento, nome_empresa)
    if link is None:
        return False
    webbrowser.open(link)
    return True
