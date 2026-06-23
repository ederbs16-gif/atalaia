from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from atalaia.db.models.cliente import Cliente
from atalaia.modules.clientes import service


class DialogoCliente(QDialog):
    """
    Diálogo compacto para criação rápida de cliente.

    Uso inline no formulário de orçamento — mesmo padrão de DialogoFornecedor.
    Campos: Nome e Telefone apenas.
    Recuperar o cliente criado via obter_cliente_criado().
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cliente_criado: Cliente | None = None
        self.setWindowTitle("Novo Cliente")
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_nome = QLineEdit()
        self.txt_nome.setPlaceholderText("Nome do cliente (obrigatório)")
        form.addRow("Nome *:", self.txt_nome)

        self.txt_telefone = QLineEdit()
        self.txt_telefone.setPlaceholderText("opcional")
        form.addRow("Telefone:", self.txt_telefone)

        layout.addLayout(form)

        botoes = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        botoes.button(QDialogButtonBox.Save).setText("Salvar")
        botoes.button(QDialogButtonBox.Cancel).setText("Cancelar")
        botoes.accepted.connect(self._salvar)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)

    def _salvar(self) -> None:
        nome = self.txt_nome.text().strip()
        if not nome:
            QMessageBox.warning(self, "Nome obrigatório", "O nome do cliente não pode ser vazio.")
            return
        dados = {
            "nome": nome,
            "telefone": self.txt_telefone.text().strip() or None,
        }
        try:
            self._cliente_criado = service.criar_cliente(dados)
        except ValueError as e:
            QMessageBox.warning(self, "Cliente inválido", str(e))
            return
        self.accept()

    def obter_cliente_criado(self) -> Cliente | None:
        return self._cliente_criado
