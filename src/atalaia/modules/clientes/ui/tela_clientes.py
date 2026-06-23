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

from atalaia.modules.clientes import service
from atalaia.modules.clientes.ui.formulario_cliente import FormularioCliente

_COLUNAS = ["Nome", "Telefone", "Documento", "Status"]
_COR_INATIVO = QColor("#AAAAAA")


class ClienteTableModel(QAbstractTableModel):

    def __init__(self):
        super().__init__()
        self._clientes: list = []

    def atualizar(self, clientes: list) -> None:
        self.beginResetModel()
        self._clientes = clientes
        self.endResetModel()

    def cliente_em_linha(self, row: int):
        if 0 <= row < len(self._clientes):
            return self._clientes[row]
        return None

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._clientes)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(_COLUNAS)

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return _COLUNAS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        c = self._clientes[index.row()]
        col = index.column()

        if role == Qt.DisplayRole:
            if col == 0:
                return c.nome
            if col == 1:
                return c.telefone or "—"
            if col == 2:
                return c.documento or "—"
            if col == 3:
                return "Ativo" if c.ativo else "Inativo"

        if role == Qt.ForegroundRole:
            if not c.ativo:
                return _COR_INATIVO

        if role == Qt.TextAlignmentRole:
            return Qt.AlignLeft | Qt.AlignVCenter

        return None


class TelaClientes(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._modelo = ClienteTableModel()
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

        self.btn_novo = QPushButton("Novo Cliente")
        self.btn_novo.clicked.connect(self._novo_cliente)
        row.addWidget(self.btn_novo)

        self.btn_editar = QPushButton("Editar")
        self.btn_editar.setEnabled(False)
        self.btn_editar.clicked.connect(self._editar_cliente)
        row.addWidget(self.btn_editar)

        self.btn_inativar = QPushButton("Inativar")
        self.btn_inativar.setEnabled(False)
        self.btn_inativar.clicked.connect(self._inativar_cliente)
        row.addWidget(self.btn_inativar)

        self.btn_historico = QPushButton("Histórico")
        self.btn_historico.setEnabled(False)
        self.btn_historico.clicked.connect(self._abrir_historico)
        row.addWidget(self.btn_historico)

        return row

    def _aplicar_filtros(self) -> None:
        termo = self.txt_buscar.text().strip()
        status_idx = self.combo_status.currentIndex()
        apenas_ativos = (status_idx == 0)

        try:
            clientes = service.buscar_clientes_por_termo(termo, apenas_ativos=apenas_ativos)
            if status_idx == 1:
                clientes = [c for c in clientes if not c.ativo]
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao buscar clientes: {e}")
            return

        self._modelo.atualizar(clientes)
        self._on_selecao_mudou()

    def _limpar_filtros(self) -> None:
        self.txt_buscar.clear()
        self.combo_status.setCurrentIndex(0)
        self._aplicar_filtros()

    def _on_selecao_mudou(self, *_) -> None:
        c = self._cliente_selecionado()
        self.btn_editar.setEnabled(c is not None)
        self.btn_inativar.setEnabled(c is not None and c.ativo)
        self.btn_historico.setEnabled(c is not None)

    def _cliente_selecionado(self):
        indexes = self.tabela.selectionModel().selectedRows()
        if not indexes:
            return None
        return self._modelo.cliente_em_linha(indexes[0].row())

    def _novo_cliente(self) -> None:
        formulario = FormularioCliente(parent=self)
        if formulario.exec() == QDialog.Accepted:
            self._aplicar_filtros()

    def _editar_cliente(self) -> None:
        c = self._cliente_selecionado()
        if c is None:
            return
        formulario = FormularioCliente(cliente_id=c.id, parent=self)
        if formulario.exec() == QDialog.Accepted:
            self._aplicar_filtros()

    def _inativar_cliente(self) -> None:
        c = self._cliente_selecionado()
        if c is None:
            return

        resposta = QMessageBox.question(
            self,
            "Confirmar inativação",
            f"Inativar o cliente '{c.nome}'?\n\nEle não aparecerá mais nas listagens ativas.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resposta != QMessageBox.Yes:
            return

        try:
            service.inativar_cliente(c.id)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao inativar cliente: {e}")
            return

        self._aplicar_filtros()

    def _abrir_historico(self) -> None:
        c = self._cliente_selecionado()
        nome = c.nome if c else ""
        QMessageBox.information(
            self,
            "Histórico",
            f"Histórico de compras de '{nome}'\n\nEm desenvolvimento — disponível após módulo de Orçamentos e PDV.",
        )
