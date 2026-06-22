from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from atalaia.db.models.categoria import Categoria
from atalaia.modules.produtos import service


class DialogoCategoria(QDialog):
    """
    Diálogo modal para criação rápida de categoria.

    Uso: abrir com exec(); se retornar QDialog.Accepted, recuperar a categoria
    criada via obter_categoria_criada(). Não acessa o banco diretamente — toda
    persistência passa por service.criar_categoria(), que valida nome vazio e
    nome duplicado (UNIQUE) levantando ValueError.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._categoria_criada: Categoria | None = None
        self.setWindowTitle("Nova Categoria")
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.txt_nome = QLineEdit()
        self.txt_nome.setPlaceholderText("Nome da categoria")
        form.addRow("Nome:", self.txt_nome)
        layout.addLayout(form)

        botoes = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        botoes.button(QDialogButtonBox.Save).setText("Salvar")
        botoes.button(QDialogButtonBox.Cancel).setText("Cancelar")
        botoes.accepted.connect(self._salvar)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)

    def _salvar(self) -> None:
        nome = self.txt_nome.text().strip()
        try:
            self._categoria_criada = service.criar_categoria(nome)
        except ValueError as e:
            QMessageBox.warning(self, "Categoria inválida", str(e))
            return
        self.accept()

    def obter_categoria_criada(self) -> Categoria | None:
        return self._categoria_criada
