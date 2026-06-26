from __future__ import annotations

from datetime import date
from decimal import Decimal

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from atalaia.modules.financeiro import contas_service
from atalaia.modules.financeiro.exceptions import (
    ContaJaPagaError,
    PagamentoExcedeValorError,
)

_FORMAS = [
    ("Dinheiro", "dinheiro"),
    ("PIX",      "pix"),
    ("Débito",   "debito"),
    ("Crédito",  "credito"),
]


class DialogoPagamento(QDialog):

    def __init__(self, conta, tipo: str, parent=None):
        super().__init__(parent)
        assert tipo in ("pagar", "receber")
        self._conta = conta
        self._tipo = tipo
        self.setWindowTitle("Registrar Pagamento")
        self.setMinimumWidth(380)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        saldo_restante = self._conta.valor_total - self._conta.valor_pago

        form.addRow("Descrição:", QLabel(self._conta.descricao))
        form.addRow(
            "Valor total:",
            QLabel(f"R$ {self._conta.valor_total:,.2f}"),
        )
        form.addRow(
            "Valor pago:",
            QLabel(f"R$ {self._conta.valor_pago:,.2f}"),
        )
        form.addRow(
            "Saldo restante:",
            QLabel(f"R$ {saldo_restante:,.2f}"),
        )

        self.spin_valor = QDoubleSpinBox()
        self.spin_valor.setRange(0.01, float(saldo_restante))
        self.spin_valor.setDecimals(2)
        self.spin_valor.setPrefix("R$ ")
        self.spin_valor.setValue(float(saldo_restante))
        form.addRow("Valor a pagar:", self.spin_valor)

        self.combo_forma = QComboBox()
        for label, valor in _FORMAS:
            self.combo_forma.addItem(label, valor)
        form.addRow("Forma:", self.combo_forma)

        self.date_pagamento = QDateEdit(QDate.currentDate())
        self.date_pagamento.setCalendarPopup(True)
        self.date_pagamento.setDisplayFormat("dd/MM/yyyy")
        form.addRow("Data:", self.date_pagamento)

        self.txt_obs = QPlainTextEdit()
        self.txt_obs.setMaximumHeight(60)
        self.txt_obs.setPlaceholderText("Observações (opcional)")
        form.addRow("Obs.:", self.txt_obs)

        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Registrar")
        btns.button(QDialogButtonBox.Cancel).setText("Cancelar")
        btns.accepted.connect(self._salvar)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _salvar(self) -> None:
        valor = Decimal(str(self.spin_valor.value()))
        forma = self.combo_forma.currentData()
        qd = self.date_pagamento.date()
        data_pag = date(qd.year(), qd.month(), qd.day())
        obs = self.txt_obs.toPlainText().strip() or None

        try:
            if self._tipo == "pagar":
                contas_service.registrar_pagamento_pagar(
                    self._conta.id, valor, forma, data_pag, obs
                )
            else:
                contas_service.registrar_pagamento_receber(
                    self._conta.id, valor, forma, data_pag, obs
                )
            self.accept()
        except ContaJaPagaError as e:
            QMessageBox.warning(self, "Conta já paga", str(e))
        except PagamentoExcedeValorError as e:
            QMessageBox.warning(self, "Valor excede saldo", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
