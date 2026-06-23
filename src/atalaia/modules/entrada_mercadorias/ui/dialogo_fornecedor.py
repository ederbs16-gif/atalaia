from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from atalaia.db.models.fornecedor import Fornecedor
from atalaia.modules.entrada_mercadorias import fornecedor_service
from atalaia.modules.entrada_mercadorias.exceptions import FornecedorNaoEncontradoError


class DialogoFornecedor(QDialog):
    """
    Diálogo modal para criação rápida de fornecedor.

    Uso: abrir com exec(); se retornar QDialog.Accepted, recuperar o fornecedor
    criado via obter_fornecedor_criado(). Não acessa o banco diretamente.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._fornecedor_criado: Fornecedor | None = None
        self.setWindowTitle("Novo Fornecedor")
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_nome = QLineEdit()
        self.txt_nome.setPlaceholderText("Nome do fornecedor (obrigatório)")
        form.addRow("Nome *:", self.txt_nome)

        self.txt_documento = QLineEdit()
        self.txt_documento.setPlaceholderText("CNPJ, CPF ou outro (opcional)")
        form.addRow("Documento:", self.txt_documento)

        self.txt_telefone = QLineEdit()
        self.txt_telefone.setPlaceholderText("opcional")
        form.addRow("Telefone:", self.txt_telefone)

        self.txt_email = QLineEdit()
        self.txt_email.setPlaceholderText("opcional")
        form.addRow("E-mail:", self.txt_email)

        self.txt_observacoes = QPlainTextEdit()
        self.txt_observacoes.setMaximumHeight(60)
        form.addRow("Observações:", self.txt_observacoes)

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
            QMessageBox.warning(self, "Nome obrigatório", "O nome do fornecedor não pode ser vazio.")
            return
        dados = {
            "nome": nome,
            "documento": self.txt_documento.text().strip() or None,
            "telefone": self.txt_telefone.text().strip() or None,
            "email": self.txt_email.text().strip() or None,
            "observacoes": self.txt_observacoes.toPlainText().strip() or None,
        }
        try:
            self._fornecedor_criado = fornecedor_service.criar_fornecedor(dados)
        except ValueError as e:
            QMessageBox.warning(self, "Fornecedor inválido", str(e))
            return
        self.accept()

    def obter_fornecedor_criado(self) -> Fornecedor | None:
        return self._fornecedor_criado
