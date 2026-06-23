import sys
from PySide6.QtWidgets import QApplication
from atalaia.modules.entrada_mercadorias.ui.tela_entradas import TelaEntradas

app = QApplication(sys.argv)
janela = TelaEntradas()
janela.setWindowTitle("Preview — Tela Entrada de Mercadorias")
janela.resize(1024, 600)
janela.show()
sys.exit(app.exec())
