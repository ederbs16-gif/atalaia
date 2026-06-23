from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from atalaia.modules.entrada_mercadorias import fornecedor_service
from atalaia.modules.entrada_mercadorias.ui.formulario_fornecedor import FormularioFornecedor

_COLUNAS = ["Nome", "Documento", "Telefone", "E-mail", "Status"]
_COR_INATIVO = QColor("#AAAAAA")


class FornecedorTableModel(QAbstractTableModel):

    def __init__(self):
        super().__init__()
        self._fornecedores: list = []

    def atualizar(self, fornecedores: list) -> None:
        self.beginResetModel()
        self._fornecedores = fornecedores
        self.endResetModel()

    def fornecedor_em_linha(self, row: int):
        if 0 <= row < len(self._fornecedores):
            return self._fornecedores[row]
        return None

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._fornecedores)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(_COLUNAS)

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return _COLUNAS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        f = self._fornecedores[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                return f.nome
            if col == 1:
                return f.documento or "—"
            if col == 2:
                return f.telefone or "—"
            if col == 3:
                return f.email or "—"
            if col == 4:
                return "Ativo" if f.ativo else "Inativo"

        if role == Qt.ForegroundRole:
            if not f.ativo:
                return _COR_INATIVO

        if role == Qt.TextAlignmentRole:
            return Qt.AlignLeft | Qt.AlignVCenter

        return None


class TelaFornecedores(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._modelo = FornecedorTableModel()
        self._setup_ui()
        self._aplicar_filtros()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addLayout(self._criar_painel_filtros())
        layout.addWidget(self._criar_tabela())
        layout.addLayout(self._criar_painel_acoes())

    def _criar_painel_filtros(self) -> QHBoxLayout:
        row = QHBoxLayout()

        row.addWidget(QLabel("Buscar:"))
        self.txt_buscar = QLineEdit()
        self.txt_buscar.setPlaceholderText("Nome ou documento")
        self.txt_buscar.returnPressed.connect(self._aplicar_filtros)
        row.addWidget(self.txt_buscar)

        row.addWidget(QLabel("Status:"))
        self.combo_status = QComboBox()
        self.combo_status.addItems(["Ativos", "Inativos", "Todos"])
        row.addWidget(self.combo_status)

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
        self.tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.selectionModel().selectionChanged.connect(self._on_selecao_mudou)
        return self.tabela

    def _criar_painel_acoes(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch()

        self.btn_novo = QPushButton("Novo Fornecedor")
        self.btn_novo.clicked.connect(self._novo_fornecedor)
        row.addWidget(self.btn_novo)

        self.btn_editar = QPushButton("Editar")
        self.btn_editar.setEnabled(False)
        self.btn_editar.clicked.connect(self._editar_fornecedor)
        row.addWidget(self.btn_editar)

        self.btn_inativar = QPushButton("Inativar")
        self.btn_inativar.setEnabled(False)
        self.btn_inativar.clicked.connect(self._inativar_fornecedor)
        row.addWidget(self.btn_inativar)

        return row

    def _aplicar_filtros(self) -> None:
        termo = self.txt_buscar.text().strip()
        status_idx = self.combo_status.currentIndex()
        # 0=Ativos → apenas_ativos=True; 1=Inativos ou 2=Todos → apenas_ativos=False
        apenas_ativos = (status_idx == 0)

        try:
            fornecedores = fornecedor_service.buscar_fornecedores_por_termo(
                termo, apenas_ativos=apenas_ativos
            )
            if status_idx == 1:
                fornecedores = [f for f in fornecedores if not f.ativo]
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao buscar fornecedores: {e}")
            return

        self._modelo.atualizar(fornecedores)
        self._on_selecao_mudou()

    def _limpar_filtros(self) -> None:
        self.txt_buscar.clear()
        self.combo_status.setCurrentIndex(0)
        self._aplicar_filtros()

    def _on_selecao_mudou(self, *_) -> None:
        f = self._fornecedor_selecionado()
        self.btn_editar.setEnabled(f is not None)
        self.btn_inativar.setEnabled(f is not None and f.ativo)

    def _fornecedor_selecionado(self):
        indexes = self.tabela.selectionModel().selectedRows()
        if not indexes:
            return None
        return self._modelo.fornecedor_em_linha(indexes[0].row())

    def _novo_fornecedor(self) -> None:
        formulario = FormularioFornecedor(parent=self)
        if formulario.exec() == QDialog.Accepted:
            self._aplicar_filtros()

    def _editar_fornecedor(self) -> None:
        f = self._fornecedor_selecionado()
        if f is None:
            return
        formulario = FormularioFornecedor(fornecedor_id=f.id, parent=self)
        if formulario.exec() == QDialog.Accepted:
            self._aplicar_filtros()

    def _inativar_fornecedor(self) -> None:
        f = self._fornecedor_selecionado()
        if f is None:
            return

        resposta = QMessageBox.question(
            self,
            "Confirmar inativação",
            f"Inativar o fornecedor '{f.nome}'?\n\nEle não aparecerá mais nas listagens ativas.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resposta != QMessageBox.Yes:
            return

        try:
            fornecedor_service.inativar_fornecedor(f.id)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao inativar fornecedor: {e}")
            return

        self._aplicar_filtros()
