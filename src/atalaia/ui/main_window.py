from PySide6.QtWidgets import QMainWindow


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Atalaia - Cyber e Papelaria")
        self.resize(1024, 768)
