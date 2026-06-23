from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QDate, QModelIndex, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from atalaia.modules.entrada_mercadorias import entrada_service, fornecedor_service
from atalaia.modules.entrada_mercadorias.exceptions import EntradaJaConfirmadaError
from atalaia.modules.entrada_mercadorias.ui.formulario_entrada import FormularioEntrada

_COLUNAS = ["Data", "Fornecedor", "Nº Nota", "Qtd Itens", "Status"]


class EntradaTableModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self._entradas: list = []

    def atualizar(self, entradas: list) -> None:
        self.beginResetModel()
        self._entradas = entradas
        self.endResetModel()

    def entrada_em_linha(self, row: int):
        if 0 <= row < len(self._entradas):
            return self._entradas[row]
        return None

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._entradas)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(_COLUNAS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return _COLUNAS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        e = self._entradas[index.row()]
        col = index.column()
        eh_rascunho = e.status.value == "rascunho"

        if role == Qt.DisplayRole:
            if col == 0:
                return str(e.data_entrada)
            if col == 1:
                return e.fornecedor.nome if e.fornecedor else "—"
            if col == 2:
                return e.numero_nota or "—"
            if col == 3:
                return str(len(e.itens))
            if col == 4:
                return "Rascunho" if eh_rascunho else "Confirmada"

        if role == Qt.FontRole and eh_rascunho:
            f = QFont()
            f.setItalic(True)
            return f

        if role == Qt.TextAlignmentRole and col == 3:
            return Qt.AlignCenter | Qt.AlignVCenter

        return None


class TelaEntradas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._fornecedores: list = []
        self._modelo = EntradaTableModel()
        self._setup_ui()
        self._popular_combo_fornecedores()
        self._aplicar_filtros()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addLayout(self._criar_painel_filtros())
        layout.addWidget(self._criar_tabela())
        layout.addLayout(self._criar_painel_acoes())

    def _criar_painel_filtros(self) -> QHBoxLayout:
        row = QHBoxLayout()

        row.addWidget(QLabel("Status:"))
        self.combo_status = QComboBox()
        self.combo_status.addItems(["Todos", "Rascunho", "Confirmada"])
        row.addWidget(self.combo_status)

        row.addWidget(QLabel("Fornecedor:"))
        self.combo_fornecedor = QComboBox()
        self.combo_fornecedor.addItem("Todos")
        row.addWidget(self.combo_fornecedor)

        row.addWidget(QLabel("De:"))
        self.date_de = QDateEdit()
        self.date_de.setCalendarPopup(True)
        self.date_de.setDate(QDate.currentDate().addMonths(-1))
        self.date_de.setSpecialValueText("—")
        row.addWidget(self.date_de)

        row.addWidget(QLabel("Até:"))
        self.date_ate = QDateEdit()
        self.date_ate.setCalendarPopup(True)
        self.date_ate.setDate(QDate.currentDate())
        self.date_ate.setSpecialValueText("—")
        row.addWidget(self.date_ate)

        self._usar_periodo = False

        btn_buscar = QPushButton("Buscar")
        btn_buscar.clicked.connect(self._aplicar_filtros)
        row.addWidget(btn_buscar)

        btn_limpar = QPushButton("Limpar")
        btn_limpar.clicked.connect(self._limpar_filtros)
        row.addWidget(btn_limpar)

        row.addStretch()
        return row

    def _criar_tabela(self) -> QTableView:
        self.tabela = QTableView()
        self.tabela.setModel(self._modelo)
        self.tabela.setSelectionBehavior(QTableView.SelectRows)
        self.tabela.setSelectionMode(QTableView.SingleSelection)
        self.tabela.setEditTriggers(QTableView.NoEditTriggers)
        self.tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.selectionModel().selectionChanged.connect(self._on_selecao_mudou)
        return self.tabela

    def _criar_painel_acoes(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch()

        self.btn_nova = QPushButton("Nova Entrada")
        self.btn_nova.clicked.connect(self._nova_entrada)
        row.addWidget(self.btn_nova)

        self.btn_abrir = QPushButton("Abrir / Editar")
        self.btn_abrir.setEnabled(False)
        self.btn_abrir.clicked.connect(self._abrir_entrada)
        row.addWidget(self.btn_abrir)

        self.btn_confirmar = QPushButton("Confirmar")
        self.btn_confirmar.setEnabled(False)
        self.btn_confirmar.clicked.connect(self._confirmar_entrada)
        row.addWidget(self.btn_confirmar)

        self.btn_excluir = QPushButton("Excluir Rascunho")
        self.btn_excluir.setEnabled(False)
        self.btn_excluir.clicked.connect(self._excluir_rascunho)
        row.addWidget(self.btn_excluir)

        return row

    def _popular_combo_fornecedores(self) -> None:
        try:
            self._fornecedores = fornecedor_service.listar_fornecedores(apenas_ativos=False)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao carregar fornecedores: {e}")
            self._fornecedores = []
        self.combo_fornecedor.clear()
        self.combo_fornecedor.addItem("Todos")
        for f in self._fornecedores:
            self.combo_fornecedor.addItem(f.nome, f.id)

    def _aplicar_filtros(self) -> None:
        status_idx = self.combo_status.currentIndex()
        status = {1: "rascunho", 2: "confirmada"}.get(status_idx)

        forn_idx = self.combo_fornecedor.currentIndex()
        fornecedor_id = self.combo_fornecedor.itemData(forn_idx) if forn_idx > 0 else None

        data_de = self.date_de.date().toPython()
        data_ate = self.date_ate.date().toPython()

        try:
            entradas = entrada_service.listar_entradas(
                status=status,
                fornecedor_id=fornecedor_id,
                data_de=data_de,
                data_ate=data_ate,
            )
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao buscar entradas: {e}")
            return
        self._modelo.atualizar(entradas)
        self._on_selecao_mudou()

    def _limpar_filtros(self) -> None:
        self.combo_status.setCurrentIndex(0)
        self.combo_fornecedor.setCurrentIndex(0)
        self.date_de.setDate(QDate.currentDate().addMonths(-1))
        self.date_ate.setDate(QDate.currentDate())
        self._aplicar_filtros()

    def _on_selecao_mudou(self, *_) -> None:
        e = self._entrada_selecionada()
        eh_rascunho = e is not None and e.status.value == "rascunho"
        self.btn_abrir.setEnabled(e is not None)
        self.btn_confirmar.setEnabled(eh_rascunho)
        self.btn_excluir.setEnabled(eh_rascunho)

    def _entrada_selecionada(self):
        indexes = self.tabela.selectionModel().selectedRows()
        if not indexes:
            return None
        return self._modelo.entrada_em_linha(indexes[0].row())

    def _nova_entrada(self) -> None:
        dlg = FormularioEntrada(parent=self)
        dlg.exec()
        self._aplicar_filtros()

    def _abrir_entrada(self) -> None:
        e = self._entrada_selecionada()
        if e is None:
            return
        dlg = FormularioEntrada(entrada_id=e.id, parent=self)
        dlg.exec()
        self._aplicar_filtros()

    def _confirmar_entrada(self) -> None:
        e = self._entrada_selecionada()
        if e is None:
            return
        resposta = QMessageBox.question(
            self,
            "Confirmar entrada",
            "Esta ação é irreversível. Confirmar a entrada atualizará o estoque e o custo dos produtos. Deseja continuar?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resposta != QMessageBox.Yes:
            return
        try:
            entrada_service.confirmar_entrada(e.id)
        except EntradaJaConfirmadaError as ex:
            QMessageBox.warning(self, "Não foi possível confirmar", str(ex))
            return
        except Exception as ex:
            QMessageBox.critical(self, "Erro", f"Erro ao confirmar entrada: {ex}")
            return
        self._aplicar_filtros()

    def _excluir_rascunho(self) -> None:
        e = self._entrada_selecionada()
        if e is None:
            return
        resposta = QMessageBox.question(
            self,
            "Excluir rascunho",
            "Excluir este rascunho permanentemente? Os itens também serão removidos.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resposta != QMessageBox.Yes:
            return
        try:
            entrada_service.excluir_rascunho(e.id)
        except EntradaJaConfirmadaError as ex:
            QMessageBox.warning(self, "Não foi possível excluir", str(ex))
            return
        except Exception as ex:
            QMessageBox.critical(self, "Erro", f"Erro ao excluir rascunho: {ex}")
            return
        self._aplicar_filtros()
