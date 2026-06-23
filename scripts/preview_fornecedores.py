import sys
from PySide6.QtWidgets import QApplication
from atalaia.modules.entrada_mercadorias.ui.tela_fornecedores import TelaFornecedores

app = QApplication(sys.argv)
janela = TelaFornecedores()
janela.setWindowTitle("Preview — Tela Fornecedores")
janela.resize(1024, 600)
janela.show()
sys.exit(app.exec())
