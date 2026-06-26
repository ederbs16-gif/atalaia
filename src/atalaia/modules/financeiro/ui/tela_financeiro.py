from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from atalaia.modules.financeiro import caixa_service, contas_service
from atalaia.modules.financeiro.exceptions import (
    CaixaJaAbertoError,
    CaixaNaoAbertoError,
    CaixaJaFechadoError,
)
from atalaia.modules.financeiro.ui.dialogo_abrir_caixa import DialogoAbrirCaixa
from atalaia.modules.financeiro.ui.formulario_conta import FormularioConta
from atalaia.modules.financeiro.ui.dialogo_pagamento import DialogoPagamento

from PySide6.QtCore import QAbstractTableModel, QModelIndex


# ─── Table Models ─────────────────────────────────────────────────────────────

class CaixaTableModel(QAbstractTableModel):
    _HEADERS = ["Data abertura", "Hostname", "Saldo inicial", "Dinheiro",
                "PIX", "Débito", "Crédito", "Status"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._dados: list = []

    def atualizar(self, dados: list) -> None:
        self.beginResetModel()
        self._dados = dados
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._dados)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._HEADERS[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        c = self._dados[index.row()]
        col = index.column()
        if role == Qt.DisplayRole:
            if col == 0:
                return c.aberto_em.strftime("%d/%m/%Y %H:%M") if c.aberto_em else ""
            if col == 1:
                return c.hostname
            if col == 2:
                return f"R$ {c.saldo_inicial:,.2f}"
            if col == 3:
                return f"R$ {c.total_dinheiro:,.2f}"
            if col == 4:
                return f"R$ {c.total_pix:,.2f}"
            if col == 5:
                return f"R$ {c.total_debito:,.2f}"
            if col == 6:
                return f"R$ {c.total_credito:,.2f}"
            if col == 7:
                return c.status.value
        if role == Qt.ForegroundRole and c.status.value == "fechado":
            return QColor("#888888")
        if role == Qt.TextAlignmentRole and col in (2, 3, 4, 5, 6):
            return Qt.AlignRight | Qt.AlignVCenter
        return None

    def caixa_em_linha(self, row: int):
        return self._dados[row] if 0 <= row < len(self._dados) else None


class ContaTableModel(QAbstractTableModel):
    _HEADERS_PAGAR  = ["Descrição", "Fornecedor", "Vencimento", "Total", "Pago", "Status", "Parcela"]
    _HEADERS_RECEBER = ["Descrição", "Cliente", "Vencimento", "Total", "Pago", "Status", "Parcela"]

    def __init__(self, tipo: str = "pagar", parent=None):
        super().__init__(parent)
        self._tipo = tipo
        self._dados: list = []

    def atualizar(self, dados: list) -> None:
        self.beginResetModel()
        self._dados = dados
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._dados)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 7

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            headers = self._HEADERS_PAGAR if self._tipo == "pagar" else self._HEADERS_RECEBER
            return headers[section]
        return None

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        c = self._dados[index.row()]
        col = index.column()
        hoje = date.today()
        if role == Qt.DisplayRole:
            if col == 0:
                return c.descricao
            if col == 1:
                if self._tipo == "pagar":
                    return c.fornecedor.nome if c.fornecedor else "—"
                else:
                    return c.cliente.nome if c.cliente else "—"
            if col == 2:
                return c.vencimento.strftime("%d/%m/%Y")
            if col == 3:
                return f"R$ {c.valor_total:,.2f}"
            if col == 4:
                return f"R$ {c.valor_pago:,.2f}"
            if col == 5:
                return c.status.value.replace("_", " ")
            if col == 6:
                if c.parcela_numero and c.parcela_total:
                    return f"{c.parcela_numero}/{c.parcela_total}"
                return "—"
        if role == Qt.ForegroundRole:
            from atalaia.db.models.conta_pagar import StatusContaEnum
            if c.status == StatusContaEnum.pago:
                return QColor("#888888")
            if c.vencimento < hoje:
                return QColor("#cc3333")
            if c.vencimento == hoje:
                return QColor("#cc8800")
        if role == Qt.TextAlignmentRole and col in (3, 4):
            return Qt.AlignRight | Qt.AlignVCenter
        return None

    def conta_em_linha(self, row: int):
        return self._dados[row] if 0 <= row < len(self._dados) else None


# ─── Aba Caixa ────────────────────────────────────────────────────────────────

class _AbaCaixa(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self.atualizar()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        grp = QGroupBox("Caixa atual")
        grp_layout = QVBoxLayout(grp)
        self.lbl_status = QLabel("Nenhum caixa aberto")
        self.lbl_status.setStyleSheet("font-size: 14px;")
        grp_layout.addWidget(self.lbl_status)
        layout.addWidget(grp)

        row_btns = QHBoxLayout()
        self.btn_abrir = QPushButton("Abrir Caixa")
        self.btn_fechar = QPushButton("Fechar Caixa")
        self.btn_abrir.clicked.connect(self._abrir_caixa)
        self.btn_fechar.clicked.connect(self._fechar_caixa)
        row_btns.addWidget(self.btn_abrir)
        row_btns.addWidget(self.btn_fechar)
        row_btns.addStretch()
        layout.addLayout(row_btns)

        self._model = CaixaTableModel()
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self._table)

    def atualizar(self) -> None:
        try:
            caixa = caixa_service.obter_caixa_aberto()
            if caixa:
                total = (caixa.total_dinheiro + caixa.total_pix +
                         caixa.total_debito + caixa.total_credito)
                self.lbl_status.setText(
                    f"<b>ABERTO</b> — {caixa.hostname} | "
                    f"Saldo inicial: R$ {caixa.saldo_inicial:,.2f} | "
                    f"Total recebido: R$ {total:,.2f}"
                )
                self.btn_abrir.setEnabled(False)
                self.btn_fechar.setEnabled(True)
            else:
                self.lbl_status.setText("Nenhum caixa aberto")
                self.btn_abrir.setEnabled(True)
                self.btn_fechar.setEnabled(False)
            self._model.atualizar(caixa_service.listar_caixas())
        except Exception:
            pass

    def _abrir_caixa(self) -> None:
        dlg = DialogoAbrirCaixa(self)
        if dlg.exec() == QDialog.Accepted:
            self.atualizar()

    def _fechar_caixa(self) -> None:
        caixa = caixa_service.obter_caixa_aberto()
        if not caixa:
            QMessageBox.warning(self, "Aviso", "Nenhum caixa aberto.")
            return
        resp = QMessageBox.question(
            self, "Fechar caixa",
            "Confirma o fechamento do caixa?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resp == QMessageBox.Yes:
            try:
                caixa_service.fechar_caixa(caixa.id)
                self.atualizar()
            except Exception as e:
                QMessageBox.critical(self, "Erro", str(e))


# ─── Aba Contas (base reutilizável) ──────────────────────────────────────────

class _AbaContas(QWidget):
    def __init__(self, tipo: str, parent=None):
        super().__init__(parent)
        self._tipo = tipo
        self._build_ui()
        self.atualizar()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        filtros = QHBoxLayout()
        self.combo_status = QComboBox()
        self.combo_status.addItem("Todos", None)
        self.combo_status.addItem("Pendente", "pendente")
        self.combo_status.addItem("Pago parcialmente", "pago_parcialmente")
        self.combo_status.addItem("Pago", "pago")
        self.combo_status.currentIndexChanged.connect(self.atualizar)
        filtros.addWidget(QLabel("Status:"))
        filtros.addWidget(self.combo_status)
        filtros.addSpacing(16)

        self.chk_vencimento = QPushButton("Venc. até:")
        self.chk_vencimento.setCheckable(True)
        self.chk_vencimento.setFlat(True)
        self.date_venc = QDateEdit(QDate.currentDate())
        self.date_venc.setCalendarPopup(True)
        self.date_venc.setDisplayFormat("dd/MM/yyyy")
        self.date_venc.setEnabled(False)
        self.chk_vencimento.toggled.connect(self.date_venc.setEnabled)
        self.chk_vencimento.toggled.connect(lambda _: self.atualizar())
        self.date_venc.dateChanged.connect(lambda _: self.atualizar())
        filtros.addWidget(self.chk_vencimento)
        filtros.addWidget(self.date_venc)
        filtros.addStretch()
        layout.addLayout(filtros)

        self._model = ContaTableModel(tipo=self._tipo)
        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for col in range(1, 7):
            self._table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeToContents)
        layout.addWidget(self._table)

        row_btns = QHBoxLayout()
        self.btn_nova = QPushButton("Nova Conta")
        self.btn_nova_parc = QPushButton("Nova Parcelada")
        self.btn_pagar = QPushButton("Registrar Pagamento")
        self.btn_pagar.setEnabled(False)
        self.btn_nova.clicked.connect(self._nova_conta)
        self.btn_nova_parc.clicked.connect(self._nova_parcelada)
        self.btn_pagar.clicked.connect(self._registrar_pagamento)
        row_btns.addWidget(self.btn_nova)
        row_btns.addWidget(self.btn_nova_parc)
        row_btns.addWidget(self.btn_pagar)
        row_btns.addStretch()
        layout.addLayout(row_btns)

        self._table.selectionModel().selectionChanged.connect(self._on_selecao)

    def _on_selecao(self) -> None:
        rows = self._table.selectionModel().selectedRows()
        if rows:
            conta = self._model.conta_em_linha(rows[0].row())
            from atalaia.db.models.conta_pagar import StatusContaEnum
            self.btn_pagar.setEnabled(
                conta is not None and conta.status != StatusContaEnum.pago
            )
        else:
            self.btn_pagar.setEnabled(False)

    def atualizar(self) -> None:
        try:
            status = self.combo_status.currentData()
            venc_ate = None
            if self.chk_vencimento.isChecked():
                qd = self.date_venc.date()
                venc_ate = date(qd.year(), qd.month(), qd.day())
            if self._tipo == "pagar":
                dados = contas_service.listar_contas_pagar(status=status, vencimento_ate=venc_ate)
            else:
                dados = contas_service.listar_contas_receber(status=status, vencimento_ate=venc_ate)
            self._model.atualizar(dados)
        except Exception:
            pass

    def _nova_conta(self) -> None:
        dlg = FormularioConta(modo=self._tipo, parent=self)
        dlg.chk_parcelar.setChecked(False)
        if dlg.exec() == QDialog.Accepted:
            self.atualizar()

    def _nova_parcelada(self) -> None:
        dlg = FormularioConta(modo=self._tipo, parent=self)
        dlg.chk_parcelar.setChecked(True)
        if dlg.exec() == QDialog.Accepted:
            self.atualizar()

    def _registrar_pagamento(self) -> None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return
        conta = self._model.conta_em_linha(rows[0].row())
        if conta is None:
            return
        dlg = DialogoPagamento(conta, tipo=self._tipo, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.atualizar()


# ─── TelaFinanceiro ───────────────────────────────────────────────────────────

class TelaFinanceiro(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tabWidget = QTabWidget()
        self.tabWidget.addTab(_AbaCaixa(), "Caixa")
        self.tabWidget.addTab(_AbaContas("pagar"), "Contas a Pagar")
        self.tabWidget.addTab(_AbaContas("receber"), "Contas a Receber")
        layout.addWidget(self.tabWidget)
