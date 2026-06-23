from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from atalaia.modules.clientes import service
from atalaia.modules.clientes.exceptions import ClienteNaoEncontradoError


class FormularioCliente(QDialog):
    """
    Formulário completo de criar/editar cliente.

    cliente_id=None  -> modo Criar
    cliente_id=int   -> modo Editar (carrega dados via obter_cliente)

    Nunca acessa get_session() diretamente.
    """

    def __init__(self, cliente_id: int | None = None, parent=None):
        super().__init__(parent)
        self._cliente_id = cliente_id
        self._modo_editar = cliente_id is not None

        self.setWindowTitle("Editar Cliente" if self._modo_editar else "Novo Cliente")
        self.setMinimumWidth(380)
        self._setup_ui()
        if self._modo_editar:
            self._carregar_cliente()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_nome = QLineEdit()
        self.txt_nome.setPlaceholderText("Nome do cliente (obrigatório)")
        form.addRow("Nome *:", self.txt_nome)

        self.txt_telefone = QLineEdit()
        self.txt_telefone.setPlaceholderText("opcional")
        form.addRow("Telefone:", self.txt_telefone)

        self.txt_documento = QLineEdit()
        self.txt_documento.setPlaceholderText("CPF, CNPJ ou outro (opcional)")
        form.addRow("Documento:", self.txt_documento)

        layout.addLayout(form)

        botoes = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        botoes.button(QDialogButtonBox.Save).setText("Salvar")
        botoes.button(QDialogButtonBox.Cancel).setText("Cancelar")
        botoes.accepted.connect(self._salvar)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)

    def _carregar_cliente(self) -> None:
        try:
            c = service.obter_cliente(self._cliente_id)
        except ClienteNaoEncontradoError:
            QMessageBox.critical(self, "Erro", f"Cliente {self._cliente_id} não encontrado.")
            self.reject()
            return

        self.txt_nome.setText(c.nome)
        self.txt_telefone.setText(c.telefone or "")
        self.txt_documento.setText(c.documento or "")

    def _salvar(self) -> None:
        nome = self.txt_nome.text().strip()
        if not nome:
            QMessageBox.warning(self, "Nome obrigatório", "O nome do cliente não pode ser vazio.")
            return

        dados = {
            "nome": nome,
            "telefone": self.txt_telefone.text().strip() or None,
            "documento": self.txt_documento.text().strip() or None,
        }

        try:
            if self._modo_editar:
                service.atualizar_cliente(self._cliente_id, dados)
            else:
                service.criar_cliente(dados)
        except ValueError as e:
            QMessageBox.warning(self, "Dados inválidos", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro inesperado ao salvar: {e}")
            return

        self.accept()
