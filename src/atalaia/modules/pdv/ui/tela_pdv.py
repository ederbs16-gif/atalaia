from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from atalaia.modules.pdv import venda_service
from atalaia.modules.pdv.exceptions import (
    VendaNaoEncontradaError,
    VendaJaFinalizadaError,
    PagamentoInsuficienteError,
    DescontoInvalidoError,
)
from atalaia.modules.financeiro.exceptions import CaixaNaoAbertoError
from atalaia.modules.produtos.exceptions import EstoqueInsuficienteError
from atalaia.modules.produtos.service import buscar_produtos_por_termo
from atalaia.modules.clientes.service import buscar_clientes_por_termo

_COLUNAS_ITEM = ["Produto", "Qtd", "Preço Unit.", "Subtotal", ""]
_COLUNAS_PAG = ["Forma", "Valor", ""]
_COR_TROCO = QColor("#27ae60")


class ItemVendaTableModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self._itens: list = []

    def atualizar(self, itens: list) -> None:
        self.beginResetModel()
        self._itens = itens
        self.endResetModel()

    def item_em_linha(self, row: int):
        if 0 <= row < len(self._itens):
            return self._itens[row]
        return None

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._itens)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(_COLUNAS_ITEM)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return _COLUNAS_ITEM[section]
        return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        item = self._itens[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                return item.produto.nome if item.produto else f"Produto #{item.produto_id}"
            if col == 1:
                return str(item.quantidade)
            if col == 2:
                return f"R$ {item.preco_unitario:.2f}"
            if col == 3:
                return f"R$ {item.quantidade * item.preco_unitario:.2f}"
            if col == 4:
                return "Remover"

        if role == Qt.TextAlignmentRole:
            if col in (1, 2, 3):
                return Qt.AlignRight | Qt.AlignVCenter

        return None


class PagamentoTableModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self._pagamentos: list = []

    def atualizar(self, pagamentos: list) -> None:
        self.beginResetModel()
        self._pagamentos = pagamentos
        self.endResetModel()

    def pagamento_em_linha(self, row: int):
        if 0 <= row < len(self._pagamentos):
            return self._pagamentos[row]
        return None

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._pagamentos)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(_COLUNAS_PAG)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return _COLUNAS_PAG[section]
        return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        pag = self._pagamentos[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                return pag.forma.capitalize()
            if col == 1:
                return f"R$ {pag.valor:.2f}"
            if col == 2:
                return "Remover"

        if role == Qt.TextAlignmentRole and col == 1:
            return Qt.AlignRight | Qt.AlignVCenter

        return None


class TelaPDV(QWidget):
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("PDV — Ponto de Venda")
        self._venda_id: int | None = None
        self._modelo_itens = ItemVendaTableModel()
        self._modelo_pagamentos = PagamentoTableModel()
        self._atualizando_desconto = False
        self._setup_ui()
        self._nova_venda()

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self._criar_painel_esquerdo())
        splitter.addWidget(self._criar_painel_direito())
        splitter.setSizes([600, 400])

        root.addWidget(splitter)

    def _criar_painel_esquerdo(self) -> QWidget:
        painel = QWidget()
        layout = QVBoxLayout(painel)
        layout.setContentsMargins(8, 8, 4, 8)

        self.lbl_cabecalho = QLabel("VENDA — aguardando...")
        font = QFont()
        font.setBold(True)
        font.setPointSize(12)
        self.lbl_cabecalho.setFont(font)
        layout.addWidget(self.lbl_cabecalho)

        self.tabela_itens = QTableView()
        self.tabela_itens.setModel(self._modelo_itens)
        self.tabela_itens.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabela_itens.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabela_itens.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tabela_itens.verticalHeader().setVisible(False)
        self.tabela_itens.clicked.connect(self._on_clique_tabela_itens)
        layout.addWidget(self.tabela_itens)

        grp_busca = QGroupBox("Adicionar produto")
        form_busca = QVBoxLayout(grp_busca)

        row1 = QHBoxLayout()
        self.txt_busca = QLineEdit()
        self.txt_busca.setPlaceholderText("Código de barras ou nome do produto...")
        self.txt_busca.returnPressed.connect(self._adicionar_item)
        row1.addWidget(self.txt_busca)

        self.spin_quantidade = QSpinBox()
        self.spin_quantidade.setMinimum(1)
        self.spin_quantidade.setMaximum(9999)
        self.spin_quantidade.setValue(1)
        self.spin_quantidade.setFixedWidth(80)
        row1.addWidget(QLabel("Qtd:"))
        row1.addWidget(self.spin_quantidade)

        btn_add = QPushButton("Adicionar")
        btn_add.clicked.connect(self._adicionar_item)
        row1.addWidget(btn_add)
        form_busca.addLayout(row1)

        layout.addWidget(grp_busca)
        return painel

    def _criar_painel_direito(self) -> QWidget:
        painel = QWidget()
        layout = QVBoxLayout(painel)
        layout.setContentsMargins(4, 8, 8, 8)

        row_topo = QHBoxLayout()
        btn_importar = QPushButton("Importar Orçamento")
        btn_importar.clicked.connect(self._importar_orcamento)
        row_topo.addWidget(btn_importar)

        btn_dev = QPushButton("Devolução")
        btn_dev.clicked.connect(self._devolucao)
        row_topo.addWidget(btn_dev)

        self.btn_sair = QPushButton("✕ Sair do PDV")
        self.btn_sair.clicked.connect(self.close)
        row_topo.addWidget(self.btn_sair)
        layout.addLayout(row_topo)

        grp_cliente = QGroupBox("Cliente (opcional)")
        row_cli = QHBoxLayout(grp_cliente)
        self.txt_cliente = QLineEdit()
        self.txt_cliente.setPlaceholderText("Nome do cliente...")
        self.txt_cliente.returnPressed.connect(self._buscar_cliente)
        row_cli.addWidget(self.txt_cliente)
        btn_buscar_cli = QPushButton("Buscar")
        btn_buscar_cli.clicked.connect(self._buscar_cliente)
        row_cli.addWidget(btn_buscar_cli)
        self.lbl_cliente_sel = QLabel("Anônimo")
        row_cli.addWidget(self.lbl_cliente_sel)
        self._cliente_id: int | None = None
        layout.addWidget(grp_cliente)

        grp_desc = QGroupBox("Desconto")
        row_desc = QHBoxLayout(grp_desc)
        row_desc.addWidget(QLabel("R$:"))
        self.spin_desconto_rs = QDoubleSpinBox()
        self.spin_desconto_rs.setMinimum(0)
        self.spin_desconto_rs.setMaximum(999999)
        self.spin_desconto_rs.setDecimals(2)
        self.spin_desconto_rs.valueChanged.connect(self._on_desconto_rs_mudou)
        row_desc.addWidget(self.spin_desconto_rs)
        row_desc.addWidget(QLabel("%:"))
        self.spin_desconto_pct = QDoubleSpinBox()
        self.spin_desconto_pct.setMinimum(0)
        self.spin_desconto_pct.setMaximum(100)
        self.spin_desconto_pct.setDecimals(2)
        self.spin_desconto_pct.valueChanged.connect(self._on_desconto_pct_mudou)
        row_desc.addWidget(self.spin_desconto_pct)
        btn_desc = QPushButton("Aplicar")
        btn_desc.clicked.connect(self._aplicar_desconto)
        row_desc.addWidget(btn_desc)
        layout.addWidget(grp_desc)

        grp_totais = QGroupBox("Totais")
        form_totais = QVBoxLayout(grp_totais)
        self.lbl_subtotal = QLabel("Subtotal: R$ 0,00")
        self.lbl_desconto = QLabel("Desconto: R$ 0,00")
        self.lbl_total = QLabel("TOTAL: R$ 0,00")
        font_total = QFont()
        font_total.setBold(True)
        font_total.setPointSize(14)
        self.lbl_total.setFont(font_total)
        form_totais.addWidget(self.lbl_subtotal)
        form_totais.addWidget(self.lbl_desconto)
        form_totais.addWidget(self.lbl_total)
        layout.addWidget(grp_totais)

        grp_pag = QGroupBox("Pagamento")
        layout_pag = QVBoxLayout(grp_pag)

        row_formas = QHBoxLayout()
        for forma, rotulo in [("dinheiro", "💵 Dinheiro"), ("pix", "📱 PIX"),
                               ("debito", "💳 Débito"), ("credito", "💳 Crédito")]:
            btn = QPushButton(rotulo)
            btn.clicked.connect(lambda checked, f=forma: self._selecionar_forma(f))
            row_formas.addWidget(btn)
        layout_pag.addLayout(row_formas)

        row_valor_pag = QHBoxLayout()
        self.combo_forma_sel = QComboBox()
        self.combo_forma_sel.addItems(["dinheiro", "pix", "debito", "credito"])
        self.combo_forma_sel.setVisible(False)
        row_valor_pag.addWidget(self.combo_forma_sel)
        self.spin_valor_pag = QDoubleSpinBox()
        self.spin_valor_pag.setMinimum(0.01)
        self.spin_valor_pag.setMaximum(999999)
        self.spin_valor_pag.setDecimals(2)
        self.spin_valor_pag.setVisible(False)
        row_valor_pag.addWidget(self.spin_valor_pag)
        btn_conf_pag = QPushButton("Confirmar pagamento")
        btn_conf_pag.setVisible(False)
        btn_conf_pag.clicked.connect(self._confirmar_pagamento)
        self._btn_conf_pag = btn_conf_pag
        row_valor_pag.addWidget(btn_conf_pag)
        layout_pag.addLayout(row_valor_pag)
        self._row_valor_pag_widgets = [self.combo_forma_sel, self.spin_valor_pag, btn_conf_pag]

        self.tabela_pagamentos = QTableView()
        self.tabela_pagamentos.setModel(self._modelo_pagamentos)
        self.tabela_pagamentos.setMaximumHeight(120)
        self.tabela_pagamentos.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tabela_pagamentos.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tabela_pagamentos.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tabela_pagamentos.verticalHeader().setVisible(False)
        self.tabela_pagamentos.clicked.connect(self._on_clique_tabela_pagamentos)
        layout_pag.addWidget(self.tabela_pagamentos)

        self.lbl_total_pago = QLabel("Valor pago: R$ 0,00")
        self.lbl_troco = QLabel("Troco: R$ 0,00")
        layout_pag.addWidget(self.lbl_total_pago)
        layout_pag.addWidget(self.lbl_troco)

        layout.addWidget(grp_pag)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        self.btn_finalizar = QPushButton("FINALIZAR VENDA")
        self.btn_finalizar.setMinimumHeight(48)
        self.btn_finalizar.setStyleSheet("background-color: #27ae60; color: white; font-size: 16px; font-weight: bold;")
        self.btn_finalizar.clicked.connect(self._finalizar_venda)
        layout.addWidget(self.btn_finalizar)

        self.btn_cancelar = QPushButton("CANCELAR VENDA")
        self.btn_cancelar.setStyleSheet("background-color: #c0392b; color: white;")
        self.btn_cancelar.clicked.connect(self._cancelar_venda)
        layout.addWidget(self.btn_cancelar)

        return painel

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def showEvent(self, event):
        super().showEvent(event)
        self.txt_busca.setFocus()

    def _nova_venda(self) -> None:
        try:
            venda = venda_service.iniciar_venda()
            self._venda_id = venda.id
            self._atualizar_cabecalho(venda)
        except CaixaNaoAbertoError as e:
            QMessageBox.critical(self, "Caixa fechado", str(e))
            self._venda_id = None
            self.lbl_cabecalho.setText("CAIXA FECHADO — Abra o caixa no módulo Financeiro")
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Erro", f"Erro ao iniciar venda: {e}")
            self._venda_id = None

    def _atualizar_cabecalho(self, venda=None) -> None:
        if self._venda_id is None:
            return
        cliente = "Anônimo"
        if venda and venda.cliente:
            cliente = venda.cliente.nome
        self.lbl_cabecalho.setText(f"VENDA #{self._venda_id} | Cliente: {cliente}")

    def _recarregar(self) -> None:
        if self._venda_id is None:
            return
        try:
            venda = venda_service.obter_venda(self._venda_id)
            self._modelo_itens.atualizar(venda.itens)
            self._modelo_pagamentos.atualizar(venda.pagamentos)
            self._atualizar_cabecalho(venda)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao recarregar venda: {e}")
            return

        try:
            totais = venda_service.calcular_totais(self._venda_id)
            self.lbl_subtotal.setText(f"Subtotal: R$ {totais['subtotal']:.2f}")
            self.lbl_desconto.setText(f"Desconto: R$ {totais['desconto_valor']:.2f} ({totais['desconto_percentual']:.2f}%)")
            self.lbl_total.setText(f"TOTAL: R$ {totais['total']:.2f}")
            self.lbl_total_pago.setText(f"Valor pago: R$ {totais['total_pago']:.2f}")
            troco = totais["troco"]
            self.lbl_troco.setText(f"Troco: R$ {troco:.2f}")
            self.lbl_troco.setStyleSheet("color: #27ae60; font-weight: bold;" if troco > 0 else "")

            subtotal = float(totais["subtotal"])
            pct = float(totais["desconto_percentual"])
            rs = subtotal * pct / 100
            self._atualizando_desconto = True
            self.spin_desconto_pct.setValue(pct)
            self.spin_desconto_rs.setValue(rs)
            self._atualizando_desconto = False
        except Exception:
            pass

    def _adicionar_item(self) -> None:
        if self._venda_id is None:
            return
        termo = self.txt_busca.text().strip()
        if not termo:
            return

        try:
            produtos = buscar_produtos_por_termo(termo, apenas_ativos=True)
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return

        if not produtos:
            resp = QMessageBox.question(
                self, "Produto não encontrado",
                f"Nenhum produto encontrado para '{termo}'.\nDeseja cadastrar um novo produto?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if resp == QMessageBox.Yes:
                from atalaia.modules.produtos.ui.formulario_produto import FormularioProduto
                dlg = FormularioProduto(parent=self)
                dlg.exec()
            return

        if len(produtos) == 1:
            produto = produtos[0]
        else:
            from PySide6.QtWidgets import QInputDialog
            nomes = [f"{p.nome} ({p.codigo_barras or '—'})" for p in produtos]
            escolha, ok = QInputDialog.getItem(self, "Selecionar produto", "Produto:", nomes, 0, False)
            if not ok:
                return
            produto = produtos[nomes.index(escolha)]

        quantidade = self.spin_quantidade.value()
        try:
            venda_service.adicionar_item(self._venda_id, produto.id, quantidade)
        except EstoqueInsuficienteError as e:
            QMessageBox.warning(self, "Estoque insuficiente", str(e))
            return
        except VendaJaFinalizadaError as e:
            QMessageBox.warning(self, "Venda finalizada", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return

        self.txt_busca.clear()
        self.spin_quantidade.setValue(1)
        self.txt_busca.setFocus()
        self._recarregar()

    def _on_clique_tabela_itens(self, index: QModelIndex) -> None:
        if index.column() == 4:
            item = self._modelo_itens.item_em_linha(index.row())
            if item is not None:
                self._remover_item(item.id)

    def _remover_item(self, item_id: int) -> None:
        try:
            venda_service.remover_item(item_id)
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return
        self._recarregar()

    def _buscar_cliente(self) -> None:
        termo = self.txt_cliente.text().strip()
        if not termo:
            return
        try:
            clientes = buscar_clientes_por_termo(termo, apenas_ativos=True)
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return
        if not clientes:
            QMessageBox.information(self, "Não encontrado", "Nenhum cliente encontrado.")
            return
        if len(clientes) == 1:
            cli = clientes[0]
        else:
            from PySide6.QtWidgets import QInputDialog
            nomes = [c.nome for c in clientes]
            escolha, ok = QInputDialog.getItem(self, "Selecionar cliente", "Cliente:", nomes, 0, False)
            if not ok:
                return
            cli = clientes[nomes.index(escolha)]
        self._cliente_id = cli.id
        self.lbl_cliente_sel.setText(cli.nome)

    def _on_desconto_rs_mudou(self, valor: float) -> None:
        if self._atualizando_desconto:
            return
        totais = self._totais_rapidos()
        if totais is None or totais["subtotal"] == 0:
            return
        self._atualizando_desconto = True
        pct = valor / float(totais["subtotal"]) * 100
        self.spin_desconto_pct.setValue(round(pct, 2))
        self._atualizando_desconto = False

    def _on_desconto_pct_mudou(self, pct: float) -> None:
        if self._atualizando_desconto:
            return
        totais = self._totais_rapidos()
        if totais is None:
            return
        self._atualizando_desconto = True
        rs = float(totais["subtotal"]) * pct / 100
        self.spin_desconto_rs.setValue(round(rs, 2))
        self._atualizando_desconto = False

    def _totais_rapidos(self) -> dict | None:
        if self._venda_id is None:
            return None
        try:
            return venda_service.calcular_totais(self._venda_id)
        except Exception:
            return None

    def _aplicar_desconto(self) -> None:
        if self._venda_id is None:
            return
        valor = Decimal(str(self.spin_desconto_rs.value()))
        try:
            venda_service.aplicar_desconto(self._venda_id, valor=valor)
        except DescontoInvalidoError as e:
            QMessageBox.warning(self, "Desconto inválido", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return
        self._recarregar()

    def _selecionar_forma(self, forma: str) -> None:
        self.combo_forma_sel.setCurrentText(forma)
        for w in self._row_valor_pag_widgets:
            w.setVisible(True)
        self.spin_valor_pag.setFocus()

    def _confirmar_pagamento(self) -> None:
        if self._venda_id is None:
            return
        forma = self.combo_forma_sel.currentText()
        valor = Decimal(str(self.spin_valor_pag.value()))
        try:
            venda_service.adicionar_pagamento(self._venda_id, forma, valor)
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return
        for w in self._row_valor_pag_widgets:
            w.setVisible(False)
        self.spin_valor_pag.setValue(0.01)
        self._recarregar()

    def _on_clique_tabela_pagamentos(self, index: QModelIndex) -> None:
        if index.column() == 2:
            pag = self._modelo_pagamentos.pagamento_em_linha(index.row())
            if pag is not None:
                try:
                    venda_service.remover_pagamento(pag.id)
                except Exception as e:
                    QMessageBox.critical(self, "Erro", str(e))
                    return
                self._recarregar()

    def _finalizar_venda(self) -> None:
        if self._venda_id is None:
            return
        resp = QMessageBox.question(
            self, "Finalizar venda",
            "Confirmar finalização da venda?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return
        try:
            venda_service.finalizar_venda(self._venda_id)
        except PagamentoInsuficienteError as e:
            QMessageBox.warning(self, "Pagamento insuficiente", str(e))
            return
        except EstoqueInsuficienteError as e:
            QMessageBox.warning(self, "Estoque insuficiente", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return

        QMessageBox.information(self, "Venda finalizada", f"Venda #{self._venda_id} finalizada com sucesso!")
        self._venda_id = None
        self._modelo_itens.atualizar([])
        self._modelo_pagamentos.atualizar([])
        self.lbl_subtotal.setText("Subtotal: R$ 0,00")
        self.lbl_desconto.setText("Desconto: R$ 0,00")
        self.lbl_total.setText("TOTAL: R$ 0,00")
        self.lbl_total_pago.setText("Valor pago: R$ 0,00")
        self.lbl_troco.setText("Troco: R$ 0,00")
        self._nova_venda()

    def _cancelar_venda(self) -> None:
        if self._venda_id is None:
            return
        resp = QMessageBox.question(
            self, "Cancelar venda",
            f"Cancelar venda #{self._venda_id}? Esta ação não pode ser desfeita.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return
        try:
            venda_service.cancelar_venda(self._venda_id)
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return
        self._venda_id = None
        self._modelo_itens.atualizar([])
        self._modelo_pagamentos.atualizar([])
        self._nova_venda()

    def _importar_orcamento(self) -> None:
        if self._venda_id is None:
            return
        from atalaia.modules.pdv.ui.dialogo_importar_orcamento import DialogoImportarOrcamento
        dlg = DialogoImportarOrcamento(parent=self)
        if dlg.exec() and dlg.orcamento_id is not None:
            try:
                venda_service.importar_orcamento(self._venda_id, dlg.orcamento_id)
            except Exception as e:
                QMessageBox.critical(self, "Erro", str(e))
                return
            self._recarregar()

    def _devolucao(self) -> None:
        from atalaia.modules.pdv.ui.dialogo_devolucao import DialogoDevolucao
        dlg = DialogoDevolucao(parent=self)
        dlg.exec()
