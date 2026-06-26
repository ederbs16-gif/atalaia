from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from atalaia.modules.financeiro import caixa_service
from atalaia.modules.financeiro.exceptions import CaixaJaAbertoError


class DialogoAbrirCaixa(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Abrir Caixa")
        self.setMinimumWidth(360)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()

        self.spin_saldo = QDoubleSpinBox()
        self.spin_saldo.setRange(0, 999_999.99)
        self.spin_saldo.setDecimals(2)
        self.spin_saldo.setPrefix("R$ ")
        self.spin_saldo.setValue(0.0)
        form.addRow("Saldo inicial:", self.spin_saldo)

        self.txt_obs = QPlainTextEdit()
        self.txt_obs.setMaximumHeight(80)
        self.txt_obs.setPlaceholderText("Observações (opcional)")
        form.addRow("Observações:", self.txt_obs)

        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.button(QDialogButtonBox.Ok).setText("Abrir")
        btns.button(QDialogButtonBox.Cancel).setText("Cancelar")
        btns.accepted.connect(self._salvar)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _salvar(self) -> None:
        saldo = Decimal(str(self.spin_saldo.value()))
        obs = self.txt_obs.toPlainText().strip() or None
        try:
            caixa_service.abrir_caixa(saldo_inicial=saldo, observacoes=obs)
            self.accept()
        except CaixaJaAbertoError as e:
            QMessageBox.warning(self, "Caixa já aberto", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
