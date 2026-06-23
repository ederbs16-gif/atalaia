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

from atalaia.modules.entrada_mercadorias import fornecedor_service
from atalaia.modules.entrada_mercadorias.exceptions import FornecedorNaoEncontradoError


class FormularioFornecedor(QDialog):
    """
    Formulário completo de criar/editar fornecedor.

    fornecedor_id=None  -> modo Criar
    fornecedor_id=int   -> modo Editar (carrega dados existentes)

    Nunca acessa get_session() diretamente — toda persistência passa por fornecedor_service.
    """

    def __init__(self, fornecedor_id: int | None = None, parent=None):
        super().__init__(parent)
        self._fornecedor_id = fornecedor_id
        self._modo_editar = fornecedor_id is not None

        self.setWindowTitle("Editar Fornecedor" if self._modo_editar else "Novo Fornecedor")
        self.setMinimumWidth(400)
        self._setup_ui()
        if self._modo_editar:
            self._carregar_fornecedor()

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
        self.txt_observacoes.setMaximumHeight(80)
        form.addRow("Observações:", self.txt_observacoes)

        layout.addLayout(form)

        botoes = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        botoes.button(QDialogButtonBox.Save).setText("Salvar")
        botoes.button(QDialogButtonBox.Cancel).setText("Cancelar")
        botoes.accepted.connect(self._salvar)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)

    def _carregar_fornecedor(self) -> None:
        try:
            f = fornecedor_service.obter_fornecedor(self._fornecedor_id)
        except FornecedorNaoEncontradoError:
            QMessageBox.critical(self, "Erro", f"Fornecedor {self._fornecedor_id} não encontrado.")
            self.reject()
            return

        self.txt_nome.setText(f.nome)
        self.txt_documento.setText(f.documento or "")
        self.txt_telefone.setText(f.telefone or "")
        self.txt_email.setText(f.email or "")
        self.txt_observacoes.setPlainText(f.observacoes or "")

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
            if self._modo_editar:
                fornecedor_service.atualizar_fornecedor(self._fornecedor_id, dados)
            else:
                fornecedor_service.criar_fornecedor(dados)
        except ValueError as e:
            QMessageBox.warning(self, "Dados inválidos", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro inesperado ao salvar: {e}")
            return

        self.accept()
