from __future__ import annotations

from datetime import date

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QMessageBox,
    QTableView,
    QVBoxLayout,
)

from atalaia.modules.orcamentos import service as orc_service

_COLUNAS = ["Nº", "Cliente", "Criação", "Validade", "Status", "Total"]
_COR_VENCIDO = QColor("#c0392b")


class _OrcTableModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self._rows: list = []

    def atualizar(self, orcamentos: list) -> None:
        self.beginResetModel()
        self._rows = orcamentos
        self.endResetModel()

    def orc_em_linha(self, row: int):
        if 0 <= row < len(self._rows):
            return self._rows[row]
        return None

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(_COLUNAS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return _COLUNAS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        orc = self._rows[index.row()]
        col = index.column()
        eh_vencido = (
            orc.status.value == "aberto"
            and orc.data_validade
            and date.today() > orc.data_validade
        )

        if role == Qt.DisplayRole:
            if col == 0:
                return orc_service.numero_formatado(orc)
            if col == 1:
                return orc.cliente.nome if orc.cliente else "—"
            if col == 2:
                return str(orc.data_criacao) if orc.data_criacao else "—"
            if col == 3:
                return str(orc.data_validade) if orc.data_validade else "—"
            if col == 4:
                return orc.status.value.capitalize()
            if col == 5:
                from decimal import Decimal
                itens = orc.itens or []
                subtotal = sum(i.quantidade * i.preco_unitario for i in itens)
                if orc.desconto_percentual:
                    subtotal = subtotal * (1 - orc.desconto_percentual / Decimal("100"))
                return f"R$ {subtotal:,.2f}"

        if role == Qt.ForegroundRole and eh_vencido:
            return _COR_VENCIDO

        return None


class DialogoImportarOrcamento(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Importar Orçamento")
        self.setMinimumSize(700, 400)
        self.orcamento_id: int | None = None
        self._modelo = _OrcTableModel()
        self._setup_ui()
        self._carregar()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Selecione o orçamento a importar:"))

        self.tabela = QTableView()
        self.tabela.setModel(self._modelo)
        self.tabela.setSelectionBehavior(QTableView.SelectRows)
        self.tabela.setSelectionMode(QTableView.SingleSelection)
        self.tabela.setEditTriggers(QTableView.NoEditTriggers)
        self.tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.doubleClicked.connect(self._confirmar)
        layout.addWidget(self.tabela)

        buttons = QDialogButtonBox()
        self.btn_importar = buttons.addButton("Importar", QDialogButtonBox.AcceptRole)
        buttons.addButton(QDialogButtonBox.Cancel)
        self.btn_importar.clicked.connect(self._confirmar)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _carregar(self) -> None:
        try:
            abertos = orc_service.listar_orcamentos(status="aberto")
            aprovados = orc_service.listar_orcamentos(status="aprovado")
            self._modelo.atualizar(abertos + aprovados)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao carregar orçamentos: {e}")

    def _confirmar(self) -> None:
        indexes = self.tabela.selectionModel().selectedRows()
        if not indexes:
            QMessageBox.information(self, "Atenção", "Selecione um orçamento.")
            return
        orc = self._modelo.orc_em_linha(indexes[0].row())
        if orc is not None:
            self.orcamento_id = orc.id
            self.accept()
