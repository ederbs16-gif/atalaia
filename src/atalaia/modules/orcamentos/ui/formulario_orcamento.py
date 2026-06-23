from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QTableView,
    QVBoxLayout,
)

from atalaia.modules.orcamentos import service
from atalaia.modules.orcamentos.exceptions import (
    OrcamentoJaFinalizadoError,
    ClienteInativoError,
    ClienteNaoEncontradoError,
    ProdutoInativoError,
    ProdutoNaoEncontradoError,
)
from atalaia.modules.clientes import service as cliente_service
from atalaia.modules.produtos import service as produto_service

_COLUNAS_ITEM = ["Produto", "Qtd", "Preço Unit.", "Subtotal"]


class ItemOrcamentoTableModel(QAbstractTableModel):
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
                return item.produto.nome if item.produto else str(item.produto_id)
            if col == 1:
                return str(item.quantidade)
            if col == 2:
                return f"R$ {item.preco_unitario:,.2f}"
            if col == 3:
                subtotal = item.quantidade * item.preco_unitario
                return f"R$ {subtotal:,.2f}"
        if role == Qt.TextAlignmentRole and col in (1, 2, 3):
            return Qt.AlignRight | Qt.AlignVCenter
        return None


class FormularioOrcamento(QDialog):
    """
    Formulário de orçamento em três modos:
      orcamento_id=None            → criação
      orcamento_id=int, aberto     → edição (cabeçalho + itens)
      orcamento_id=int, finalizado → somente leitura
    """

    def __init__(self, orcamento_id: int | None = None, parent=None):
        super().__init__(parent)
        self._orc_id = orcamento_id
        self._clientes: list = []
        self._produtos_busca: list = []
        self._modelo_itens = ItemOrcamentoTableModel()
        self._modo_readonly = False

        self.setWindowTitle("Orçamento")
        self.setMinimumWidth(720)
        self._setup_ui()
        self._popular_clientes()

        if orcamento_id is not None:
            self._carregar_orcamento(orcamento_id)
        else:
            self._grp_itens.setEnabled(False)

    # ------------------------------------------------------------------
    # Construção da UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._lbl_readonly = QLabel("ORÇAMENTO FINALIZADO — somente leitura")
        self._lbl_readonly.setStyleSheet("color: #555; font-weight: bold; padding: 4px;")
        self._lbl_readonly.setVisible(False)
        layout.addWidget(self._lbl_readonly)

        layout.addWidget(self._criar_grp_cabecalho())
        layout.addWidget(self._criar_grp_itens())

        row_total = QHBoxLayout()
        row_total.addStretch()
        self.lbl_total = QLabel("Total: R$ 0,00")
        self.lbl_total.setStyleSheet("font-size: 14px; font-weight: bold;")
        row_total.addWidget(self.lbl_total)
        layout.addLayout(row_total)

        btn_fechar = QPushButton("Fechar")
        btn_fechar.clicked.connect(self.accept)
        layout.addWidget(btn_fechar)

    def _criar_grp_cabecalho(self) -> QGroupBox:
        grp = QGroupBox("Cabeçalho")
        form = QVBoxLayout(grp)

        row_cli = QHBoxLayout()
        row_cli.addWidget(QLabel("Cliente *:"))
        self.combo_cliente = QComboBox()
        row_cli.addWidget(self.combo_cliente, 1)
        form.addLayout(row_cli)

        row_cfg = QHBoxLayout()
        row_cfg.addWidget(QLabel("Validade (dias):"))
        self.spin_validade = QSpinBox()
        self.spin_validade.setMinimum(1)
        self.spin_validade.setMaximum(365)
        self.spin_validade.setValue(10)
        row_cfg.addWidget(self.spin_validade)
        row_cfg.addWidget(QLabel("Desconto (%):"))
        self.spin_desconto = QDoubleSpinBox()
        self.spin_desconto.setMinimum(0.0)
        self.spin_desconto.setMaximum(100.0)
        self.spin_desconto.setDecimals(2)
        self.spin_desconto.setSingleStep(0.5)
        row_cfg.addWidget(self.spin_desconto)
        row_cfg.addStretch()
        form.addLayout(row_cfg)

        form.addWidget(QLabel("Observações:"))
        self.txt_observacoes = QPlainTextEdit()
        self.txt_observacoes.setMaximumHeight(50)
        form.addWidget(self.txt_observacoes)

        self.btn_salvar_cabecalho = QPushButton("Criar Orçamento")
        self.btn_salvar_cabecalho.clicked.connect(self._salvar_cabecalho)
        form.addWidget(self.btn_salvar_cabecalho)

        return grp

    def _criar_grp_itens(self) -> QGroupBox:
        self._grp_itens = QGroupBox("Itens")
        layout = QVBoxLayout(self._grp_itens)

        row_busca = QHBoxLayout()
        row_busca.addWidget(QLabel("Buscar produto:"))
        self.txt_busca_produto = QLineEdit()
        self.txt_busca_produto.setPlaceholderText("Nome ou código de barras")
        self.txt_busca_produto.returnPressed.connect(self._buscar_produto)
        row_busca.addWidget(self.txt_busca_produto, 1)
        btn_buscar = QPushButton("Buscar")
        btn_buscar.clicked.connect(self._buscar_produto)
        row_busca.addWidget(btn_buscar)
        layout.addLayout(row_busca)

        self.combo_produto = QComboBox()
        layout.addWidget(self.combo_produto)

        row_add = QHBoxLayout()
        row_add.addWidget(QLabel("Qtd:"))
        self.spin_quantidade = QSpinBox()
        self.spin_quantidade.setMinimum(1)
        self.spin_quantidade.setMaximum(999999)
        row_add.addWidget(self.spin_quantidade)
        btn_add = QPushButton("Adicionar Item")
        btn_add.clicked.connect(self._adicionar_item)
        row_add.addWidget(btn_add)
        row_add.addStretch()
        layout.addLayout(row_add)

        self.tabela_itens = QTableView()
        self.tabela_itens.setModel(self._modelo_itens)
        self.tabela_itens.setSelectionBehavior(QTableView.SelectRows)
        self.tabela_itens.setSelectionMode(QTableView.SingleSelection)
        self.tabela_itens.setEditTriggers(QTableView.NoEditTriggers)
        self.tabela_itens.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tabela_itens.verticalHeader().setVisible(False)
        layout.addWidget(self.tabela_itens)

        self.btn_remover_item = QPushButton("Remover Selecionado")
        self.btn_remover_item.clicked.connect(self._remover_item)
        layout.addWidget(self.btn_remover_item)

        return self._grp_itens

    # ------------------------------------------------------------------
    # Carregamento de dados
    # ------------------------------------------------------------------

    def _popular_clientes(self, selecionar_id: int | None = None) -> None:
        try:
            self._clientes = cliente_service.listar_clientes(apenas_ativos=True)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao carregar clientes: {e}")
            self._clientes = []
        self.combo_cliente.clear()
        for c in self._clientes:
            self.combo_cliente.addItem(c.nome, c.id)
        if selecionar_id is not None:
            idx = self.combo_cliente.findData(selecionar_id)
            if idx >= 0:
                self.combo_cliente.setCurrentIndex(idx)

    def _carregar_orcamento(self, orcamento_id: int) -> None:
        try:
            orc = service.obter_orcamento(orcamento_id)
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            self.reject()
            return

        finalizado = orc.status.value in ("aprovado", "recusado")
        self._modo_readonly = finalizado

        idx = self.combo_cliente.findData(orc.cliente_id)
        if idx >= 0:
            self.combo_cliente.setCurrentIndex(idx)
        self.spin_validade.setValue(orc.validade_dias or 10)
        self.spin_desconto.setValue(float(orc.desconto_percentual or 0))
        self.txt_observacoes.setPlainText(orc.observacoes or "")

        if finalizado:
            self._lbl_readonly.setVisible(True)
            self.combo_cliente.setEnabled(False)
            self.spin_validade.setEnabled(False)
            self.spin_desconto.setEnabled(False)
            self.txt_observacoes.setEnabled(False)
            self.btn_salvar_cabecalho.setEnabled(False)
            self._grp_itens.setEnabled(False)
        else:
            self.btn_salvar_cabecalho.setText("Salvar Alterações")
            self._grp_itens.setEnabled(True)

        self._recarregar_itens()

    def _recarregar_itens(self) -> None:
        if self._orc_id is None:
            return
        try:
            orc = service.obter_orcamento(self._orc_id)
            self._modelo_itens.atualizar(orc.itens)
            self._atualizar_total(orc)
        except Exception:
            pass

    def _atualizar_total(self, orc) -> None:
        itens = orc.itens if orc.itens else []
        subtotal = sum(i.quantidade * i.preco_unitario for i in itens)
        desconto = Decimal(str(orc.desconto_percentual or 0))
        total = subtotal * (1 - desconto / Decimal("100"))
        self.lbl_total.setText(f"Total: R$ {total:,.2f}")

    # ------------------------------------------------------------------
    # Ações de cabeçalho
    # ------------------------------------------------------------------

    def _salvar_cabecalho(self) -> None:
        cliente_id = self.combo_cliente.currentData()
        if cliente_id is None:
            QMessageBox.warning(self, "Cliente obrigatório", "Selecione um cliente.")
            return
        validade_dias = self.spin_validade.value()
        desconto = Decimal(str(self.spin_desconto.value()))
        observacoes = self.txt_observacoes.toPlainText().strip() or None

        try:
            if self._orc_id is None:
                orc = service.criar_orcamento(
                    cliente_id=cliente_id,
                    validade_dias=validade_dias,
                    desconto_percentual=desconto,
                    observacoes=observacoes,
                )
                self._orc_id = orc.id
                self.btn_salvar_cabecalho.setText("Salvar Alterações")
                self._grp_itens.setEnabled(True)
            else:
                service.atualizar_orcamento(
                    self._orc_id,
                    {
                        "cliente_id": cliente_id,
                        "validade_dias": validade_dias,
                        "desconto_percentual": desconto,
                        "observacoes": observacoes,
                    },
                )
                self._recarregar_itens()
        except (ClienteNaoEncontradoError, ClienteInativoError, OrcamentoJaFinalizadoError) as e:
            QMessageBox.warning(self, "Não foi possível salvar", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro inesperado: {e}")

    # ------------------------------------------------------------------
    # Ações de itens
    # ------------------------------------------------------------------

    def _buscar_produto(self) -> None:
        termo = self.txt_busca_produto.text().strip()
        if not termo:
            return
        try:
            self._produtos_busca = produto_service.buscar_produtos_por_termo(
                termo, apenas_ativos=True
            )
        except Exception as e:
            QMessageBox.warning(self, "Erro na busca", str(e))
            return
        self.combo_produto.clear()
        if not self._produtos_busca:
            QMessageBox.information(self, "Não encontrado", "Nenhum produto encontrado.")
            return
        for p in self._produtos_busca:
            self.combo_produto.addItem(f"{p.nome} ({p.codigo_barras or '—'})", p.id)

    def _adicionar_item(self) -> None:
        if self._orc_id is None:
            QMessageBox.warning(self, "Orçamento não salvo", "Salve o orçamento antes de adicionar itens.")
            return
        produto_id = self.combo_produto.currentData()
        if produto_id is None:
            QMessageBox.warning(self, "Produto não selecionado", "Busque e selecione um produto.")
            return
        quantidade = self.spin_quantidade.value()
        try:
            service.adicionar_item(
                orcamento_id=self._orc_id,
                produto_id=produto_id,
                quantidade=quantidade,
            )
        except (ProdutoNaoEncontradoError, ProdutoInativoError, OrcamentoJaFinalizadoError) as e:
            QMessageBox.warning(self, "Não foi possível adicionar", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return
        self._recarregar_itens()
        self.spin_quantidade.setValue(1)

    def _remover_item(self) -> None:
        indexes = self.tabela_itens.selectionModel().selectedRows()
        if not indexes:
            return
        item = self._modelo_itens.item_em_linha(indexes[0].row())
        if item is None:
            return
        try:
            service.remover_item(item.id)
        except OrcamentoJaFinalizadoError as e:
            QMessageBox.warning(self, "Não foi possível remover", str(e))
            return
        self._recarregar_itens()
