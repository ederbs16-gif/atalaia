from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtCore import QAbstractTableModel, QDate, QModelIndex, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
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

from atalaia.modules.entrada_mercadorias import entrada_service, fornecedor_service
from atalaia.modules.entrada_mercadorias.exceptions import (
    EntradaJaConfirmadaError,
    FornecedorInativoError,
    FornecedorNaoEncontradoError,
    ProdutoInativoError,
    ProdutoNaoEncontradoError,
)
from atalaia.modules.entrada_mercadorias.ui.dialogo_fornecedor import DialogoFornecedor
from atalaia.modules.produtos import service as produto_service
from atalaia.modules.produtos.ui.formulario_produto import FormularioProduto

_COLUNAS_ITEM = ["Produto", "Qtd", "Custo Unitário", "Subtotal"]


class ItemEntradaTableModel(QAbstractTableModel):
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
                return f"R$ {item.custo_unitario:,.2f}"
            if col == 3:
                subtotal = item.quantidade * item.custo_unitario
                return f"R$ {subtotal:,.2f}"
        if role == Qt.TextAlignmentRole and col in (1, 2, 3):
            return Qt.AlignRight | Qt.AlignVCenter
        return None


class FormularioEntrada(QDialog):
    """
    Formulário para criar/editar/visualizar entrada de mercadoria.

    entrada_id=None              → modo Criação
    entrada_id=int, rascunho     → modo Edição (cabeçalho + itens editáveis)
    entrada_id=int, confirmada   → modo Somente Leitura
    """

    def __init__(self, entrada_id: int | None = None, parent=None):
        super().__init__(parent)
        self._entrada_id = entrada_id
        self._fornecedores: list = []
        self._produtos_busca: list = []
        self._modelo_itens = ItemEntradaTableModel()
        self._modo_readonly = False

        self.setWindowTitle("Entrada de Mercadoria")
        self.setMinimumWidth(700)
        self._setup_ui()
        self._popular_fornecedores()

        if entrada_id is not None:
            self._carregar_entrada(entrada_id)
        else:
            self._grp_itens.setEnabled(False)

    # ------------------------------------------------------------------
    # Construção da UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        self._lbl_readonly = QLabel("ENTRADA CONFIRMADA — somente leitura")
        self._lbl_readonly.setStyleSheet("color: #555; font-weight: bold; padding: 4px;")
        self._lbl_readonly.setVisible(False)
        layout.addWidget(self._lbl_readonly)

        layout.addWidget(self._criar_grp_cabecalho())
        layout.addWidget(self._criar_grp_itens())

        btn_fechar = QPushButton("Fechar")
        btn_fechar.clicked.connect(self.accept)
        layout.addWidget(btn_fechar)

    def _criar_grp_cabecalho(self) -> QGroupBox:
        grp = QGroupBox("Cabeçalho")
        form_layout = QVBoxLayout(grp)

        row_forn = QHBoxLayout()
        row_forn.addWidget(QLabel("Fornecedor *:"))
        self.combo_fornecedor = QComboBox()
        row_forn.addWidget(self.combo_fornecedor, 1)
        self.btn_novo_fornecedor = QPushButton("+")
        self.btn_novo_fornecedor.setMaximumWidth(32)
        self.btn_novo_fornecedor.setToolTip("Novo fornecedor")
        self.btn_novo_fornecedor.clicked.connect(self._abrir_dialogo_fornecedor)
        row_forn.addWidget(self.btn_novo_fornecedor)
        form_layout.addLayout(row_forn)

        row_nota = QHBoxLayout()
        row_nota.addWidget(QLabel("Nº Nota:"))
        self.txt_numero_nota = QLineEdit()
        self.txt_numero_nota.setPlaceholderText("opcional")
        row_nota.addWidget(self.txt_numero_nota)
        row_nota.addWidget(QLabel("Data:"))
        self.date_entrada = QDateEdit()
        self.date_entrada.setCalendarPopup(True)
        self.date_entrada.setDate(QDate.currentDate())
        row_nota.addWidget(self.date_entrada)
        form_layout.addLayout(row_nota)

        form_layout.addWidget(QLabel("Observações:"))
        self.txt_observacoes = QPlainTextEdit()
        self.txt_observacoes.setMaximumHeight(50)
        form_layout.addWidget(self.txt_observacoes)

        self.btn_salvar_cabecalho = QPushButton("Salvar Rascunho")
        self.btn_salvar_cabecalho.clicked.connect(self._salvar_cabecalho)
        form_layout.addWidget(self.btn_salvar_cabecalho)

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
        self.combo_produto.currentIndexChanged.connect(self._on_produto_selecionado)
        layout.addWidget(self.combo_produto)

        row_add = QHBoxLayout()
        row_add.addWidget(QLabel("Qtd:"))
        self.spin_quantidade = QSpinBox()
        self.spin_quantidade.setMinimum(1)
        self.spin_quantidade.setMaximum(999999)
        row_add.addWidget(self.spin_quantidade)
        row_add.addWidget(QLabel("Custo unitário:"))
        self.txt_custo = QLineEdit()
        self.txt_custo.setPlaceholderText("0.00")
        row_add.addWidget(self.txt_custo)
        btn_add = QPushButton("Adicionar Item")
        btn_add.clicked.connect(self._adicionar_item)
        row_add.addWidget(btn_add)
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

    def _popular_fornecedores(self, selecionar_id: int | None = None) -> None:
        try:
            self._fornecedores = fornecedor_service.listar_fornecedores(apenas_ativos=True)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao carregar fornecedores: {e}")
            self._fornecedores = []
        self.combo_fornecedor.clear()
        for f in self._fornecedores:
            self.combo_fornecedor.addItem(f.nome, f.id)
        if selecionar_id is not None:
            idx = self.combo_fornecedor.findData(selecionar_id)
            if idx >= 0:
                self.combo_fornecedor.setCurrentIndex(idx)

    def _carregar_entrada(self, entrada_id: int) -> None:
        try:
            entrada = entrada_service.obter_entrada(entrada_id)
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            self.reject()
            return

        confirmada = entrada.status.value == "confirmada"
        self._modo_readonly = confirmada

        idx = self.combo_fornecedor.findData(entrada.fornecedor_id)
        if idx >= 0:
            self.combo_fornecedor.setCurrentIndex(idx)
        self.txt_numero_nota.setText(entrada.numero_nota or "")
        self.date_entrada.setDate(QDate(entrada.data_entrada))
        self.txt_observacoes.setPlainText(entrada.observacoes or "")

        if confirmada:
            self._lbl_readonly.setVisible(True)
            self.combo_fornecedor.setEnabled(False)
            self.btn_novo_fornecedor.setEnabled(False)
            self.txt_numero_nota.setEnabled(False)
            self.date_entrada.setEnabled(False)
            self.txt_observacoes.setEnabled(False)
            self.btn_salvar_cabecalho.setEnabled(False)
            self._grp_itens.setEnabled(False)
        else:
            self.btn_salvar_cabecalho.setText("Atualizar Cabeçalho")
            self._grp_itens.setEnabled(True)

        self._recarregar_itens()

    def _recarregar_itens(self) -> None:
        if self._entrada_id is None:
            return
        try:
            entrada = entrada_service.obter_entrada(self._entrada_id)
            self._modelo_itens.atualizar(entrada.itens)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Ações de cabeçalho
    # ------------------------------------------------------------------

    def _abrir_dialogo_fornecedor(self) -> None:
        dlg = DialogoFornecedor(self)
        if dlg.exec() == QDialog.Accepted:
            novo = dlg.obter_fornecedor_criado()
            if novo is not None:
                self._popular_fornecedores(selecionar_id=novo.id)

    def _salvar_cabecalho(self) -> None:
        fornecedor_id = self.combo_fornecedor.currentData()
        if fornecedor_id is None:
            QMessageBox.warning(self, "Fornecedor obrigatório", "Selecione um fornecedor.")
            return
        numero_nota = self.txt_numero_nota.text().strip() or None
        data_entrada = self.date_entrada.date().toPython()
        observacoes = self.txt_observacoes.toPlainText().strip() or None

        try:
            if self._entrada_id is None:
                entrada = entrada_service.criar_entrada(
                    fornecedor_id=fornecedor_id,
                    numero_nota=numero_nota,
                    data_entrada=data_entrada,
                    observacoes=observacoes,
                )
                self._entrada_id = entrada.id
                self.btn_salvar_cabecalho.setText("Atualizar Cabeçalho")
                self._grp_itens.setEnabled(True)
            else:
                entrada_service.atualizar_rascunho(
                    entrada_id=self._entrada_id,
                    fornecedor_id=fornecedor_id,
                    numero_nota=numero_nota,
                    data_entrada=data_entrada,
                    observacoes=observacoes,
                )
        except (FornecedorNaoEncontradoError, FornecedorInativoError, EntradaJaConfirmadaError, ValueError) as e:
            QMessageBox.warning(self, "Não foi possível salvar", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro inesperado: {e}")
            return

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
            resposta = QMessageBox.question(
                self,
                "Produto não encontrado",
                "Produto não encontrado. Deseja cadastrar um novo produto agora?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No,
            )
            if resposta != QMessageBox.Yes:
                self.txt_busca_produto.clear()
                return
            dlg = FormularioProduto(produto_id=None, parent=self)
            dlg.exec()
            if not dlg.produto_salvo():
                return
            try:
                self._produtos_busca = produto_service.buscar_produtos_por_termo(
                    termo, apenas_ativos=True
                )
            except Exception:
                return
            if not self._produtos_busca:
                return
            self.combo_produto.clear()
            for p in self._produtos_busca:
                self.combo_produto.addItem(f"{p.nome} ({p.codigo_barras or '—'})", p.id)
            self.combo_produto.setCurrentIndex(0)
            primeiro = self._produtos_busca[0]
            if primeiro.preco_custo is not None:
                self.txt_custo.setText(str(primeiro.preco_custo))
            self.spin_quantidade.setFocus()
            return
        for p in self._produtos_busca:
            self.combo_produto.addItem(f"{p.nome} ({p.codigo_barras or '—'})", p.id)

    def _on_produto_selecionado(self, idx: int) -> None:
        if idx < 0 or idx >= len(self._produtos_busca):
            return
        p = self._produtos_busca[idx]
        if p.preco_custo is not None:
            self.txt_custo.setText(str(p.preco_custo))

    def _adicionar_item(self) -> None:
        if self._entrada_id is None:
            QMessageBox.warning(self, "Rascunho não salvo", "Salve o rascunho antes de adicionar itens.")
            return
        produto_id = self.combo_produto.currentData()
        if produto_id is None:
            QMessageBox.warning(self, "Produto não selecionado", "Busque e selecione um produto.")
            return
        quantidade = self.spin_quantidade.value()
        try:
            custo = Decimal(self.txt_custo.text().strip().replace(",", "."))
        except (InvalidOperation, ValueError):
            QMessageBox.warning(self, "Custo inválido", "Digite um valor numérico válido para o custo unitário.")
            return
        try:
            entrada_service.adicionar_item(
                entrada_id=self._entrada_id,
                produto_id=produto_id,
                quantidade=quantidade,
                custo_unitario=custo,
            )
        except (ProdutoNaoEncontradoError, ProdutoInativoError, EntradaJaConfirmadaError, ValueError) as e:
            QMessageBox.warning(self, "Não foi possível adicionar", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return
        self._recarregar_itens()
        self.spin_quantidade.setValue(1)
        self.txt_custo.clear()

    def _remover_item(self) -> None:
        indexes = self.tabela_itens.selectionModel().selectedRows()
        if not indexes:
            return
        item = self._modelo_itens.item_em_linha(indexes[0].row())
        if item is None:
            return
        try:
            entrada_service.remover_item(item.id)
        except (EntradaJaConfirmadaError, ValueError) as e:
            QMessageBox.warning(self, "Não foi possível remover", str(e))
            return
        self._recarregar_itens()
