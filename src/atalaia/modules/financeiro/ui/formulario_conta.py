from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from atalaia.modules.financeiro import contas_service
from atalaia.modules.entrada_mercadorias import fornecedor_service
from atalaia.modules.clientes import service as cliente_service
from atalaia.modules.clientes.ui.dialogo_cliente import DialogoCliente
from atalaia.modules.entrada_mercadorias.ui.dialogo_fornecedor import DialogoFornecedor


class FormularioConta(QDialog):

    def __init__(self, modo: str = "pagar", parent=None):
        super().__init__(parent)
        assert modo in ("pagar", "receber")
        self._modo = modo
        titulo = "Nova Conta a Pagar" if modo == "pagar" else "Nova Conta a Receber"
        self.setWindowTitle(titulo)
        self.setMinimumWidth(420)
        self._build_ui()
        self._popular_relacionados()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        from PySide6.QtWidgets import QLineEdit
        self.txt_descricao = QLineEdit()
        self.txt_descricao.setPlaceholderText("Descrição da conta *")
        form.addRow("Descrição *:", self.txt_descricao)

        self.spin_valor = QDoubleSpinBox()
        self.spin_valor.setRange(0.01, 999_999.99)
        self.spin_valor.setDecimals(2)
        self.spin_valor.setPrefix("R$ ")
        form.addRow("Valor total *:", self.spin_valor)

        self.date_vencimento = QDateEdit(QDate.currentDate())
        self.date_vencimento.setCalendarPopup(True)
        self.date_vencimento.setDisplayFormat("dd/MM/yyyy")
        form.addRow("Vencimento *:", self.date_vencimento)

        if self._modo == "pagar":
            row_forn = QHBoxLayout()
            self.combo_fornecedor = QComboBox()
            self.combo_fornecedor.setSizeAdjustPolicy(QComboBox.AdjustToContents)
            row_forn.addWidget(self.combo_fornecedor, 1)
            btn_novo_forn = QPushButton("+")
            btn_novo_forn.setMaximumWidth(32)
            btn_novo_forn.setToolTip("Novo fornecedor")
            btn_novo_forn.clicked.connect(self._abrir_dialogo_fornecedor)
            row_forn.addWidget(btn_novo_forn)
            w_forn = self._wrap(row_forn)
            form.addRow("Fornecedor:", w_forn)
        else:
            row_cli = QHBoxLayout()
            self.combo_cliente = QComboBox()
            self.combo_cliente.setSizeAdjustPolicy(QComboBox.AdjustToContents)
            row_cli.addWidget(self.combo_cliente, 1)
            btn_novo_cli = QPushButton("+")
            btn_novo_cli.setMaximumWidth(32)
            btn_novo_cli.setToolTip("Novo cliente")
            btn_novo_cli.clicked.connect(self._abrir_dialogo_cliente)
            row_cli.addWidget(btn_novo_cli)
            w_cli = self._wrap(row_cli)
            form.addRow("Cliente:", w_cli)

        self.chk_parcelar = QCheckBox("Parcelar")
        self.chk_parcelar.toggled.connect(self._toggle_parcelas)
        form.addRow("", self.chk_parcelar)

        self.spin_parcelas = QSpinBox()
        self.spin_parcelas.setRange(2, 60)
        self.spin_parcelas.setValue(2)
        self.spin_parcelas.setEnabled(False)
        self.lbl_parcelas = QLabel("Nº parcelas:")
        form.addRow(self.lbl_parcelas, self.spin_parcelas)

        self.txt_obs = QPlainTextEdit()
        self.txt_obs.setMaximumHeight(70)
        self.txt_obs.setPlaceholderText("Observações (opcional)")
        form.addRow("Obs.:", self.txt_obs)

        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Salvar")
        btns.button(QDialogButtonBox.Cancel).setText("Cancelar")
        btns.accepted.connect(self._salvar)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    @staticmethod
    def _wrap(layout) -> "QWidget":
        from PySide6.QtWidgets import QWidget
        w = QWidget()
        w.setLayout(layout)
        return w

    def _toggle_parcelas(self, checked: bool) -> None:
        self.spin_parcelas.setEnabled(checked)

    def _popular_relacionados(self) -> None:
        try:
            if self._modo == "pagar":
                self.combo_fornecedor.clear()
                self.combo_fornecedor.addItem("(nenhum)", None)
                for f in fornecedor_service.listar_fornecedores(apenas_ativos=True):
                    self.combo_fornecedor.addItem(f.nome, f.id)
            else:
                self.combo_cliente.clear()
                self.combo_cliente.addItem("(nenhum)", None)
                for c in cliente_service.listar_clientes(apenas_ativos=True):
                    self.combo_cliente.addItem(c.nome, c.id)
        except Exception:
            pass

    def _abrir_dialogo_fornecedor(self) -> None:
        dlg = DialogoFornecedor(self)
        if dlg.exec() == QDialog.Accepted:
            novo = dlg.obter_fornecedor_criado()
            if novo is not None:
                self._popular_relacionados()
                idx = self.combo_fornecedor.findData(novo.id)
                if idx >= 0:
                    self.combo_fornecedor.setCurrentIndex(idx)

    def _abrir_dialogo_cliente(self) -> None:
        dlg = DialogoCliente(self)
        if dlg.exec() == QDialog.Accepted:
            novo = dlg.obter_cliente_criado()
            if novo is not None:
                self._popular_relacionados()
                idx = self.combo_cliente.findData(novo.id)
                if idx >= 0:
                    self.combo_cliente.setCurrentIndex(idx)

    def _salvar(self) -> None:
        descricao = self.txt_descricao.text().strip()
        if not descricao:
            QMessageBox.warning(self, "Campo obrigatório", "Informe a descrição.")
            return
        valor = self.spin_valor.value()
        if valor <= 0:
            QMessageBox.warning(self, "Campo obrigatório", "Informe o valor total.")
            return

        qd = self.date_vencimento.date()
        vencimento = date(qd.year(), qd.month(), qd.day())
        parcelar = self.chk_parcelar.isChecked()
        num_parcelas = self.spin_parcelas.value()
        obs = self.txt_obs.toPlainText().strip() or None

        dados: dict = {
            "descricao": descricao,
            "valor_total": Decimal(str(valor)),
            "vencimento": vencimento,
            "observacoes": obs,
        }

        if self._modo == "pagar":
            dados["fornecedor_id"] = self.combo_fornecedor.currentData()
        else:
            dados["cliente_id"] = self.combo_cliente.currentData()

        try:
            if self._modo == "pagar":
                if parcelar:
                    contas_service.criar_conta_pagar_parcelada(dados, num_parcelas)
                else:
                    contas_service.criar_conta_pagar(dados)
            else:
                if parcelar:
                    contas_service.criar_conta_receber_parcelada(dados, num_parcelas)
                else:
                    contas_service.criar_conta_receber(dados)
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, "Erro ao salvar", str(e))
