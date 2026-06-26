from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import select, text
from sqlalchemy.orm import joinedload

from atalaia.db.session import get_session
from atalaia.db.models.venda import Venda, ItemVenda, StatusVendaEnum
from atalaia.db.models.orcamento import Orcamento, ItemOrcamento, StatusOrcamentoEnum
from atalaia.db.models.produto import Produto
from atalaia.db.models.pagamento_venda import PagamentoVenda
from atalaia.db.models.devolucao import Devolucao, ItemDevolucao, TipoDevolucaoEnum, StatusDevolucaoEnum
from atalaia.modules.financeiro import caixa_service
from atalaia.modules.financeiro.exceptions import CaixaNaoAbertoError
from atalaia.modules.produtos.service import obter_preco_vigente, validar_desconto
from atalaia.modules.produtos.exceptions import EstoqueInsuficienteError, DescontoNaoPermitidoError, DescontoExcedeLimiteError
from atalaia.modules.pdv.exceptions import (
    VendaNaoEncontradaError,
    VendaJaFinalizadaError,
    PagamentoInsuficienteError,
    DescontoInvalidoError,
    DevolucaoInvalidaError,
)


def iniciar_venda(cliente_id: int | None = None) -> Venda:
    caixa = caixa_service.obter_caixa_aberto()
    if caixa is None:
        raise CaixaNaoAbertoError("Nenhum caixa aberto. Abra o caixa antes de iniciar uma venda.")
    with get_session() as session:
        venda = Venda(
            status=StatusVendaEnum.aberta,
            caixa_id=caixa.id,
            cliente_id=cliente_id,
            desconto_percentual=Decimal("0"),
            total=Decimal("0"),
        )
        session.add(venda)
        session.flush()
        venda = session.execute(
            select(Venda)
            .where(Venda.id == venda.id)
            .options(
                joinedload(Venda.cliente),
                joinedload(Venda.itens),
                joinedload(Venda.pagamentos),
            )
        ).unique().scalar_one()
        session.expunge_all()
        return venda


def importar_orcamento(venda_id: int, orcamento_id: int) -> Venda:
    with get_session() as session:
        venda = session.execute(
            select(Venda)
            .where(Venda.id == venda_id)
            .options(joinedload(Venda.itens))
        ).unique().scalar_one_or_none()
        if venda is None:
            raise VendaNaoEncontradaError(f"Venda {venda_id} não encontrada.")
        if venda.status != StatusVendaEnum.aberta:
            raise VendaJaFinalizadaError("Venda já foi finalizada ou cancelada.")

        orc = session.execute(
            select(Orcamento)
            .where(Orcamento.id == orcamento_id)
            .options(joinedload(Orcamento.itens))
        ).unique().scalar_one_or_none()
        if orc is None:
            raise VendaNaoEncontradaError(f"Orçamento {orcamento_id} não encontrado.")
        if orc.status not in (StatusOrcamentoEnum.aberto, StatusOrcamentoEnum.aprovado):
            raise VendaJaFinalizadaError("Orçamento já foi recusado ou está em estado inválido.")

        for item_orc in orc.itens:
            item_venda = ItemVenda(
                venda_id=venda_id,
                produto_id=item_orc.produto_id,
                quantidade=item_orc.quantidade,
                preco_unitario=item_orc.preco_unitario,
            )
            session.add(item_venda)

        if orc.status == StatusOrcamentoEnum.aberto:
            orc.status = StatusOrcamentoEnum.aprovado

        venda.orcamento_id = orcamento_id
        if orc.desconto_percentual:
            venda.desconto_percentual = orc.desconto_percentual

        session.flush()
        venda = session.execute(
            select(Venda)
            .where(Venda.id == venda_id)
            .options(
                joinedload(Venda.cliente),
                joinedload(Venda.itens).joinedload(ItemVenda.produto),
                joinedload(Venda.pagamentos),
            )
        ).unique().scalar_one()
        session.expunge_all()
        return venda


def adicionar_item(venda_id: int, produto_id: int, quantidade: int) -> ItemVenda:
    with get_session() as session:
        venda = session.get(Venda, venda_id)
        if venda is None:
            raise VendaNaoEncontradaError(f"Venda {venda_id} não encontrada.")
        if venda.status != StatusVendaEnum.aberta:
            raise VendaJaFinalizadaError("Venda já foi finalizada ou cancelada.")

        prod = session.get(Produto, produto_id)
        if prod is None:
            raise VendaNaoEncontradaError(f"Produto {produto_id} não encontrado.")

        if prod.controla_estoque and prod.estoque_atual < quantidade:
            raise EstoqueInsuficienteError(
                f"Estoque insuficiente para '{prod.nome}': "
                f"disponível {prod.estoque_atual}, solicitado {quantidade}."
            )

        preco_unitario = obter_preco_vigente(prod, date.today())
        item = ItemVenda(
            venda_id=venda_id,
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
        item = session.get(ItemVenda, item_id)
        if item is None:
            return
        venda = session.get(Venda, item.venda_id)
        if venda and venda.status != StatusVendaEnum.aberta:
            raise VendaJaFinalizadaError("Venda já foi finalizada — não é possível remover itens.")
        session.delete(item)


def aplicar_desconto(
    venda_id: int,
    valor: Decimal | None = None,
    percentual: Decimal | None = None,
) -> Venda:
    if valor is None and percentual is None:
        raise DescontoInvalidoError("Informe valor ou percentual de desconto.")

    with get_session() as session:
        venda = session.execute(
            select(Venda)
            .where(Venda.id == venda_id)
            .options(joinedload(Venda.itens).joinedload(ItemVenda.produto))
        ).unique().scalar_one_or_none()
        if venda is None:
            raise VendaNaoEncontradaError(f"Venda {venda_id} não encontrada.")
        if venda.status != StatusVendaEnum.aberta:
            raise VendaJaFinalizadaError("Venda já foi finalizada ou cancelada.")

        subtotal = sum(
            item.quantidade * item.preco_unitario
            for item in venda.itens
        )
        if subtotal == 0:
            raise DescontoInvalidoError("Venda sem itens — não é possível aplicar desconto.")

        if valor is not None:
            if valor > subtotal:
                raise DescontoInvalidoError("Desconto maior que o subtotal da venda.")
            percentual = (valor / subtotal * 100).quantize(Decimal("0.01"))
        else:
            valor = (subtotal * percentual / 100).quantize(Decimal("0.01"))
            if valor > subtotal:
                raise DescontoInvalidoError("Desconto maior que o subtotal da venda.")

        for item in venda.itens:
            try:
                validar_desconto(item.produto, percentual)
            except (DescontoNaoPermitidoError, DescontoExcedeLimiteError) as e:
                raise DescontoInvalidoError(str(e)) from e

        venda.desconto_percentual = percentual
        session.flush()
        venda = session.execute(
            select(Venda)
            .where(Venda.id == venda_id)
            .options(
                joinedload(Venda.cliente),
                joinedload(Venda.itens).joinedload(ItemVenda.produto),
                joinedload(Venda.pagamentos),
            )
        ).unique().scalar_one()
        session.expunge_all()
        return venda


def calcular_totais(venda_id: int) -> dict:
    with get_session() as session:
        venda = session.execute(
            select(Venda)
            .where(Venda.id == venda_id)
            .options(
                joinedload(Venda.itens),
                joinedload(Venda.pagamentos),
            )
        ).unique().scalar_one_or_none()
        if venda is None:
            raise VendaNaoEncontradaError(f"Venda {venda_id} não encontrada.")

        subtotal = sum(
            item.quantidade * item.preco_unitario
            for item in venda.itens
        )
        desconto_valor = (subtotal * venda.desconto_percentual / 100).quantize(Decimal("0.01"))
        total = subtotal - desconto_valor
        total_pago = sum(p.valor for p in venda.pagamentos)
        troco = max(Decimal("0"), total_pago - total)
        falta_pagar = max(Decimal("0"), total - total_pago)

        return {
            "subtotal": subtotal,
            "desconto_percentual": venda.desconto_percentual,
            "desconto_valor": desconto_valor,
            "total": total,
            "total_pago": total_pago,
            "troco": troco,
            "falta_pagar": falta_pagar,
        }


def adicionar_pagamento(venda_id: int, forma: str, valor: Decimal) -> PagamentoVenda:
    formas_validas = {"dinheiro", "pix", "debito", "credito"}
    if forma not in formas_validas:
        raise ValueError(f"Forma inválida: {forma!r}. Use: {sorted(formas_validas)}")

    with get_session() as session:
        venda = session.get(Venda, venda_id)
        if venda is None:
            raise VendaNaoEncontradaError(f"Venda {venda_id} não encontrada.")
        if venda.status != StatusVendaEnum.aberta:
            raise VendaJaFinalizadaError("Venda já foi finalizada ou cancelada.")

        pagamento = PagamentoVenda(
            venda_id=venda_id,
            forma=forma,
            valor=valor,
        )
        session.add(pagamento)
        session.flush()
        session.expunge(pagamento)
        return pagamento


def remover_pagamento(pagamento_id: int) -> None:
    with get_session() as session:
        pag = session.get(PagamentoVenda, pagamento_id)
        if pag is None:
            return
        venda = session.get(Venda, pag.venda_id)
        if venda and venda.status != StatusVendaEnum.aberta:
            raise VendaJaFinalizadaError("Venda já finalizada — não é possível remover pagamento.")
        session.delete(pag)


def finalizar_venda(venda_id: int) -> Venda:
    pagamentos_para_caixa: list[tuple[int, str, Decimal]] = []

    with get_session() as session:
        venda = session.execute(
            select(Venda)
            .where(Venda.id == venda_id)
            .options(
                joinedload(Venda.itens),
                joinedload(Venda.pagamentos),
            )
        ).unique().scalar_one_or_none()
        if venda is None:
            raise VendaNaoEncontradaError(f"Venda {venda_id} não encontrada.")
        if venda.status != StatusVendaEnum.aberta:
            raise VendaJaFinalizadaError("Venda já foi finalizada ou cancelada.")

        subtotal = sum(item.quantidade * item.preco_unitario for item in venda.itens)
        desconto_valor = (subtotal * venda.desconto_percentual / 100).quantize(Decimal("0.01"))
        total = subtotal - desconto_valor

        total_pago = sum(p.valor for p in venda.pagamentos)
        if total_pago < total:
            raise PagamentoInsuficienteError(
                f"Pagamento insuficiente: total R${total:.2f}, pago R${total_pago:.2f}."
            )

        for item in venda.itens:
            res = session.execute(
                text(
                    "UPDATE produtos"
                    " SET estoque_atual = estoque_atual - :qtd"
                    " WHERE id = :id AND controla_estoque = TRUE AND estoque_atual >= :qtd"
                ),
                {"qtd": item.quantidade, "id": item.produto_id},
            )
            if res.rowcount == 0:
                prod = session.get(Produto, item.produto_id)
                if prod is not None and prod.controla_estoque:
                    raise EstoqueInsuficienteError(
                        f"Estoque insuficiente para '{prod.nome}': "
                        f"disponível {prod.estoque_atual}, solicitado {item.quantidade}."
                    )

        forma_principal = max(venda.pagamentos, key=lambda p: p.valor).forma if venda.pagamentos else None
        venda.status = StatusVendaEnum.finalizada
        venda.total = total
        venda.forma_pagamento_principal = forma_principal

        pagamentos_para_caixa = [
            (venda.caixa_id, p.forma, p.valor)
            for p in venda.pagamentos
            if venda.caixa_id is not None
        ]

        session.flush()
        venda = session.execute(
            select(Venda)
            .where(Venda.id == venda_id)
            .options(
                joinedload(Venda.cliente),
                joinedload(Venda.itens).joinedload(ItemVenda.produto),
                joinedload(Venda.pagamentos),
            )
        ).unique().scalar_one()
        session.expunge_all()

    for caixa_id, forma, valor in pagamentos_para_caixa:
        try:
            caixa_service.registrar_pagamento_caixa(caixa_id, forma, valor)
        except Exception:
            pass

    return venda


def cancelar_venda(venda_id: int) -> None:
    with get_session() as session:
        venda = session.get(Venda, venda_id)
        if venda is None:
            raise VendaNaoEncontradaError(f"Venda {venda_id} não encontrada.")
        if venda.status == StatusVendaEnum.finalizada:
            raise VendaJaFinalizadaError("Venda finalizada não pode ser cancelada.")
        if venda.status == StatusVendaEnum.cancelada:
            return
        venda.status = StatusVendaEnum.cancelada


def registrar_devolucao(
    venda_id: int,
    itens: list[dict],
    tipo: str,
    motivo: str,
    forma_reembolso: str | None = None,
) -> Devolucao:
    with get_session() as session:
        venda = session.execute(
            select(Venda)
            .where(Venda.id == venda_id)
            .options(joinedload(Venda.itens))
        ).unique().scalar_one_or_none()
        if venda is None:
            raise VendaNaoEncontradaError(f"Venda {venda_id} não encontrada.")
        if venda.status != StatusVendaEnum.finalizada:
            raise VendaJaFinalizadaError("Devoluções só são permitidas em vendas finalizadas.")

        qtd_por_produto = {item.produto_id: item.quantidade for item in venda.itens}
        preco_por_produto = {item.produto_id: item.preco_unitario for item in venda.itens}

        for item_dev in itens:
            pid = item_dev["produto_id"]
            qtd = item_dev["quantidade"]
            if qtd > qtd_por_produto.get(pid, 0):
                raise DevolucaoInvalidaError(
                    f"Quantidade devolvida ({qtd}) maior que a comprada "
                    f"({qtd_por_produto.get(pid, 0)}) para produto {pid}."
                )

        valor_reembolso = Decimal("0")
        fator_desconto = 1 - venda.desconto_percentual / 100

        devolucao = Devolucao(
            venda_id=venda_id,
            tipo=TipoDevolucaoEnum[tipo],
            motivo=motivo,
            forma_reembolso=forma_reembolso,
            status=StatusDevolucaoEnum.concluida,
        )
        session.add(devolucao)
        session.flush()

        for item_dev in itens:
            pid = item_dev["produto_id"]
            qtd = item_dev["quantidade"]
            sub_id = item_dev.get("produto_substituto_id")

            session.execute(
                text(
                    "UPDATE produtos SET estoque_atual = estoque_atual + :qtd"
                    " WHERE id = :id AND controla_estoque = TRUE"
                ),
                {"qtd": qtd, "id": pid},
            )

            if tipo == "troca" and sub_id is not None:
                res = session.execute(
                    text(
                        "UPDATE produtos SET estoque_atual = estoque_atual - :qtd"
                        " WHERE id = :id AND controla_estoque = TRUE AND estoque_atual >= :qtd"
                    ),
                    {"qtd": qtd, "id": sub_id},
                )
                if res.rowcount == 0:
                    prod_sub = session.get(Produto, sub_id)
                    if prod_sub is not None and prod_sub.controla_estoque:
                        raise EstoqueInsuficienteError(
                            f"Estoque insuficiente para produto substituto '{prod_sub.nome}'."
                        )

            valor_reembolso += preco_por_produto.get(pid, Decimal("0")) * qtd * fator_desconto

            item_devolucao = ItemDevolucao(
                devolucao_id=devolucao.id,
                produto_id=pid,
                quantidade=qtd,
                produto_substituto_id=sub_id,
            )
            session.add(item_devolucao)

        devolucao.valor_reembolso = valor_reembolso.quantize(Decimal("0.01"))
        session.flush()
        session.expunge_all()
        return devolucao


def listar_vendas(
    status: str | None = None,
    data_de: date | None = None,
    data_ate: date | None = None,
) -> list[Venda]:
    with get_session() as session:
        stmt = select(Venda).options(joinedload(Venda.cliente))
        if status:
            stmt = stmt.where(Venda.status == StatusVendaEnum[status])
        if data_de:
            stmt = stmt.where(Venda.criado_em >= data_de)
        if data_ate:
            stmt = stmt.where(Venda.criado_em <= data_ate)
        stmt = stmt.order_by(Venda.id.desc())
        vendas = session.execute(stmt).unique().scalars().all()
        session.expunge_all()
        return vendas


def obter_venda(venda_id: int) -> Venda:
    with get_session() as session:
        venda = session.execute(
            select(Venda)
            .where(Venda.id == venda_id)
            .options(
                joinedload(Venda.itens).joinedload(ItemVenda.produto),
                joinedload(Venda.pagamentos),
                joinedload(Venda.cliente),
                joinedload(Venda.devolucoes).joinedload(Devolucao.itens),
            )
        ).unique().scalar_one_or_none()
        if venda is None:
            raise VendaNaoEncontradaError(f"Venda {venda_id} não encontrada.")
        session.expunge_all()
        return venda
