from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from atalaia.ui.icon_loader import load_icon
from atalaia.modules.dashboard.ui.tela_dashboard import TelaDashboard
from atalaia.modules.pdv.ui.tela_pdv import TelaPDV
from atalaia.modules.produtos.ui.tela_produtos import TelaProdutos
from atalaia.modules.clientes.ui.tela_clientes import TelaClientes
from atalaia.modules.entrada_mercadorias.ui.tela_fornecedores import TelaFornecedores
from atalaia.modules.entrada_mercadorias.ui.tela_entradas import TelaEntradas
from atalaia.modules.financeiro.ui.tela_financeiro import TelaFinanceiro
from atalaia.modules.orcamentos.ui.tela_orcamentos import TelaOrcamentos
from atalaia.modules.relatorios.ui.tela_relatorios import TelaRelatorios
from atalaia.modules.configuracoes.ui.tela_configuracoes import TelaConfiguracoes
from atalaia.modules.configuracoes.service import inicializar_configs_padrao
from atalaia.modules.configuracoes.backup_service import agendar_backup_automatico

_ICONS = Path(__file__).parent.parent / "assets" / "icons"

_SIDEBAR_QSS = """
    QWidget#Sidebar {
        background-color: #1e1e2e;
    }
    QWidget#Sidebar QPushButton {
        background: transparent;
        color: #ffffff;
        padding: 12px;
        text-align: left;
        border: none;
        border-left: 3px solid transparent;
        font-size: 13px;
    }
    QWidget#Sidebar QPushButton:hover {
        background: #2a2a3e;
    }
    QWidget#Sidebar QPushButton:checked {
        background: #313244;
        border-left: 3px solid #00B89A;
        font-weight: bold;
    }
"""

_MENU = [
    ("Dashboard",    "dashboard.svg"),
    ("PDV",          "pdv.svg"),
    ("Produtos",     "produtos.svg"),
    ("Clientes",     "clientes.svg"),
    ("Fornecedores", "fornecedor.svg"),
    ("Entradas",     "entrada.svg"),
    ("Financeiro",   "financeiro.svg"),
    ("Orçamentos",   "orcamento.svg"),
    ("Relatórios",   "relatorios.svg"),
]

_NOMES_PAGINA = ["Dashboard", "PDV", "Produtos", "Clientes", "Fornecedores",
                 "Entradas", "Financeiro", "Orçamentos", "Relatórios", "Configurações"]


def _placeholder(texto: str) -> QLabel:
    lbl = QLabel(texto)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet("font-size: 22px; color: #888888;")
    return lbl


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Atalaia — Cyber e Papelaria")
        self.setMinimumSize(1024, 600)
        self.setStyleSheet(_SIDEBAR_QSS)
        self._nav_buttons: list[QPushButton] = []

        self._setup_ui()
        self._navegar(0, self.btn_dashboard)

        try:
            inicializar_configs_padrao()
        except Exception:
            pass
        self._backup_timer = agendar_backup_automatico(QApplication.instance())

    # ------------------------------------------------------------------
    # Construção da UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._criar_sidebar())

        self._stack = QStackedWidget()
        self._criar_paginas()
        root.addWidget(self._stack)

    def _criar_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(200)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(0, 8, 0, 8)
        layout.setSpacing(0)

        for label, icon_file in _MENU:
            btn = self._criar_nav_btn(label, _ICONS / icon_file)
            layout.addWidget(btn)
            self._nav_buttons.append(btn)

        (
            self.btn_dashboard,
            self.btn_pdv,
            self.btn_produtos,
            self.btn_clientes,
            self.btn_fornecedores,
            self.btn_entradas,
            self.btn_financeiro,
            self.btn_orcamentos,
            self.btn_relatorios,
        ) = self._nav_buttons

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #44445a; margin: 4px 0;")
        layout.addWidget(sep)

        self.btn_configuracoes = self._criar_nav_btn("Configurações", _ICONS / "config.svg")
        self._nav_buttons.append(self.btn_configuracoes)
        layout.addWidget(self.btn_configuracoes)

        layout.addStretch()

        self.btn_sair = QPushButton("  Sair")
        self.btn_sair.setIcon(load_icon(_ICONS / "desligar.svg"))
        self.btn_sair.setIconSize(QSize(24, 24))
        self.btn_sair.clicked.connect(self._confirmar_saida)
        layout.addWidget(self.btn_sair)

        return sidebar

    def _criar_nav_btn(self, label: str, icon_path: Path) -> QPushButton:
        idx = len(self._nav_buttons)
        btn = QPushButton(f"  {label}")
        btn.setIcon(load_icon(icon_path))
        btn.setIconSize(QSize(24, 24))
        btn.setCheckable(True)
        btn.setFlat(True)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        btn.clicked.connect(lambda _checked, i=idx, b=btn: self._navegar(i, b))
        return btn

    def _criar_paginas(self) -> None:
        self._stack.addWidget(TelaDashboard())                                          # 0
        self._stack.addWidget(_placeholder("🖥️ PDV"))                                  # 1 placeholder (PDV abre fullscreen)
        self._stack.addWidget(TelaProdutos())                                           # 2
        self._stack.addWidget(TelaClientes())                                           # 3
        self._stack.addWidget(TelaFornecedores())                                       # 4
        self._stack.addWidget(TelaEntradas())                                           # 5
        self._stack.addWidget(TelaFinanceiro())                                         # 6
        self._stack.addWidget(TelaOrcamentos())                                         # 7
        self._stack.addWidget(TelaRelatorios())                                         # 8
        self._stack.addWidget(TelaConfiguracoes())                                      # 9

    # ------------------------------------------------------------------
    # Navegação
    # ------------------------------------------------------------------

    def _navegar(self, index: int, btn: QPushButton) -> None:
        if index == 1:
            self._abrir_pdv()
            return
        for b in self._nav_buttons:
            b.setChecked(False)
        btn.setChecked(True)
        self._stack.setCurrentIndex(index)
        nome = _NOMES_PAGINA[index] if index < len(_NOMES_PAGINA) else ""
        self.statusBar().showMessage(nome)

    def _abrir_pdv(self) -> None:
        self._pdv_window = TelaPDV()
        self._pdv_window.closed.connect(lambda: self.btn_pdv.setChecked(False))
        self._pdv_window.showFullScreen()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_F11:
            self._abrir_pdv()
        else:
            super().keyPressEvent(event)

    # ------------------------------------------------------------------
    # Saída
    # ------------------------------------------------------------------

    def _confirmar_saida(self) -> None:
        resp = QMessageBox.question(
            self,
            "Sair",
            "Deseja fechar o Atalaia?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resp == QMessageBox.Yes:
            QApplication.quit()
