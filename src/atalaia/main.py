import sys
from PySide6.QtWidgets import QApplication
from atalaia.config_local import ConfigLocal
from atalaia.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)

    cfg = ConfigLocal.instancia()
    fonte = cfg.get("interface", "fonte_tamanho_geral", "11")
    altura = cfg.get("interface", "campo_altura_minima", "30")

    app.setStyleSheet(f"""
        QWidget {{ font-size: {fonte}px; }}
        QPushButton {{ font-size: {fonte}px; min-height: {altura}px; padding: 4px 12px; }}
        QLineEdit {{ font-size: {fonte}px; min-height: {altura}px; }}
        QComboBox {{ font-size: {fonte}px; min-height: {altura}px; }}
        QSpinBox {{ font-size: {fonte}px; min-height: {altura}px; }}
        QDoubleSpinBox {{ font-size: {fonte}px; min-height: {altura}px; }}
        QTableView {{ font-size: {int(fonte) - 1}px; }}
        QTabBar::tab {{ font-size: {fonte}px; min-height: {altura}px; padding: 4px 16px; }}
        QGroupBox {{ font-size: {fonte}px; }}
    """)

    window = MainWindow()
    window.showMaximized()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
