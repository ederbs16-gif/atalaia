from __future__ import annotations

from PySide6.QtPrintSupport import QPrintDialog, QPrinter
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
)

from atalaia.modules.orcamentos import service


class VisualizacaoOrcamento(QDialog):
    def __init__(self, orcamento_id: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Visualizar Orçamento")
        self.setMinimumSize(600, 500)
        self._orcamento_id = orcamento_id
        self._setup_ui()
        self._carregar()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._browser = QTextBrowser()
        layout.addWidget(self._browser)

        row = QHBoxLayout()
        row.addStretch()
        btn_imprimir = QPushButton("Imprimir")
        btn_imprimir.clicked.connect(self._imprimir)
        row.addWidget(btn_imprimir)
        btn_fechar = QPushButton("Fechar")
        btn_fechar.clicked.connect(self.accept)
        row.addWidget(btn_fechar)
        layout.addLayout(row)

    def _carregar(self) -> None:
        try:
            orc = service.obter_orcamento(self._orcamento_id)
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            self.reject()
            return

        configs = service.carregar_configs([
            "empresa_nome", "empresa_endereco", "empresa_telefone", "empresa_cnpj"
        ])
        self._browser.setHtml(self._gerar_html(orc, configs))

    def _gerar_html(self, orc, configs: dict) -> str:
        empresa = configs.get("empresa_nome", "")
        endereco = configs.get("empresa_endereco", "")
        telefone = configs.get("empresa_telefone", "")
        cnpj = configs.get("empresa_cnpj", "")

        numero = service.numero_formatado(orc)
        cliente_nome = orc.cliente.nome if orc.cliente else "—"
        criacao = str(orc.data_criacao) if orc.data_criacao else "—"
        validade = str(orc.data_validade) if orc.data_validade else "—"

        linhas_itens = ""
        for item in (orc.itens or []):
            nome_prod = item.produto.nome if item.produto else str(item.produto_id)
            subtotal = item.quantidade * item.preco_unitario
            linhas_itens += (
                f"<tr>"
                f"<td>{nome_prod}</td>"
                f"<td align='center'>{item.quantidade}</td>"
                f"<td align='right'>R$ {item.preco_unitario:,.2f}</td>"
                f"<td align='right'>R$ {subtotal:,.2f}</td>"
                f"</tr>"
            )

        from decimal import Decimal
        itens = orc.itens or []
        subtotal_total = sum(i.quantidade * i.preco_unitario for i in itens)
        desconto = Decimal(str(orc.desconto_percentual or 0))
        total = subtotal_total * (1 - desconto / Decimal("100"))

        desconto_linha = ""
        if desconto:
            desconto_linha = f"<tr><td colspan='3'>Desconto ({desconto}%)</td><td align='right'>- R$ {subtotal_total - total:,.2f}</td></tr>"

        return f"""
        <html><body style='font-family: Arial, sans-serif; font-size: 12px;'>
        <h2 style='text-align:center'>{empresa}</h2>
        <p style='text-align:center'>{endereco}<br>{telefone} — CNPJ: {cnpj}</p>
        <hr>
        <h3>ORÇAMENTO {numero}</h3>
        <p><b>Cliente:</b> {cliente_nome}<br>
        <b>Data de criação:</b> {criacao}<br>
        <b>Válido até:</b> {validade}</p>
        <table width='100%' border='1' cellspacing='0' cellpadding='4'
               style='border-collapse:collapse'>
          <thead style='background:#eeeeee'>
            <tr>
              <th align='left'>Produto</th>
              <th>Qtd</th>
              <th align='right'>Preço Unit.</th>
              <th align='right'>Subtotal</th>
            </tr>
          </thead>
          <tbody>
            {linhas_itens}
            {desconto_linha}
            <tr>
              <td colspan='3'><b>TOTAL</b></td>
              <td align='right'><b>R$ {total:,.2f}</b></td>
            </tr>
          </tbody>
        </table>
        {f"<p><i>Observações: {orc.observacoes}</i></p>" if orc.observacoes else ""}
        </body></html>
        """

    def _imprimir(self) -> None:
        printer = QPrinter(QPrinter.HighResolution)
        dlg = QPrintDialog(printer, self)
        if dlg.exec() == QPrintDialog.Accepted:
            self._browser.print_(printer)
