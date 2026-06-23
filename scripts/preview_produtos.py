import sys
from PySide6.QtWidgets import QApplication
from atalaia.modules.produtos.ui.tela_produtos import TelaProdutos

app = QApplication(sys.argv)
janela = TelaProdutos()
janela.setWindowTitle("Preview — Tela Produtos")
janela.resize(1024, 600)
janela.show()
sys.exit(app.exec())
