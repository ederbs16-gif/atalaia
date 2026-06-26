from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from atalaia.modules.dashboard import service

_QSS_CARD = """
    QFrame#Card {
        background: #252535;
        border-radius: 8px;
    }
"""
_COR_OK      = "color: #00b89a;"
_COR_ALERTA  = "color: #f39c12;"
_COR_CRITICO = "color: #e74c3c;"
_COR_NEUTRO  = "color: #ffffff;"
_COR_CINZA   = "color: #888899;"


def _card_simples(titulo: str) -> tuple[QFrame, QLabel]:
    """Card com título + label de valor grande. Retorna (frame, lbl_valor)."""
    frame = QFrame()
    frame.setObjectName("Card")
    frame.setStyleSheet(_QSS_CARD)
    frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    frame.setMinimumHeight(100)

    lay = QVBoxLayout(frame)
    lay.setContentsMargins(14, 12, 14, 12)
    lay.setSpacing(4)

    lbl_titulo = QLabel(titulo)
    lbl_titulo.setStyleSheet("color: #aaaacc; font-size: 11px;")
    lay.addWidget(lbl_titulo)

    lbl_valor = QLabel("—")
    lbl_valor.setStyleSheet("font-size: 20px; font-weight: bold;" + _COR_NEUTRO)
    lay.addWidget(lbl_valor)

    lay.addStretch()
    return frame, lbl_valor


def _card_contas(titulo: str) -> tuple[QFrame, QLabel, QVBoxLayout]:
    """Card financeiro expandido: título + resumo + scroll com linhas de contas.
    Retorna (frame, lbl_resumo, lay_lista) onde lay_lista é populado dinamicamente."""
    frame = QFrame()
    frame.setObjectName("Card")
    frame.setStyleSheet(_QSS_CARD)
    frame.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    frame.setMinimumWidth(320)

    outer = QVBoxLayout(frame)
    outer.setContentsMargins(14, 12, 14, 12)
    outer.setSpacing(6)

    lbl_titulo = QLabel(titulo)
    lbl_titulo.setStyleSheet("color: #aaaacc; font-size: 11px;")
    outer.addWidget(lbl_titulo)

    lbl_resumo = QLabel("—")
    lbl_resumo.setStyleSheet("font-size: 16px; font-weight: bold;" + _COR_NEUTRO)
    outer.addWidget(lbl_resumo)

    # scroll interno
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setMaximumHeight(200)
    scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

    inner_widget = QWidget()
    inner_widget.setStyleSheet("background: transparent;")
    lay_lista = QVBoxLayout(inner_widget)
    lay_lista.setContentsMargins(0, 4, 0, 4)
    lay_lista.setSpacing(2)

    scroll.setWidget(inner_widget)
    outer.addWidget(scroll)

    return frame, lbl_resumo, lay_lista


def _limpar_layout(lay: QVBoxLayout) -> None:
    while lay.count():
        item = lay.takeAt(0)
        if item.widget():
            item.widget().deleteLater()


def _linha_conta(descricao: str, valor: Decimal, cor: str, data: str = "") -> QWidget:
    w = QWidget()
    w.setStyleSheet("background: transparent;")
    h = QHBoxLayout(w)
    h.setContentsMargins(0, 1, 0, 1)
    h.setSpacing(6)

    lbl_desc = QLabel(descricao)
    lbl_desc.setStyleSheet("color: #ccccdd; font-size: 11px;")
    lbl_desc.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    h.addWidget(lbl_desc)

    if data:
        lbl_data = QLabel(data)
        lbl_data.setStyleSheet("color: #888899; font-size: 10px;")
        h.addWidget(lbl_data)

    lbl_val = QLabel(f"R$ {valor:,.2f}")
    lbl_val.setStyleSheet(f"font-size: 11px; font-weight: bold; {cor}")
    lbl_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    h.addWidget(lbl_val)

    return w


class EstoqueTableModel(QAbstractTableModel):
    _COLUNAS = ["Produto", "Atual", "Mínimo", "Diferença"]

    def __init__(self):
        super().__init__()
        self._itens: list[dict] = []

    def atualizar(self, itens: list[dict]) -> None:
        self.beginResetModel()
        self._itens = itens
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._itens)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 4

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._COLUNAS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        item = self._itens[index.row()]
        col = index.column()
        if role == Qt.DisplayRole:
            return [item["nome"], str(item["estoque_atual"]),
                    str(item["estoque_minimo"]), str(item["diferenca"])][col]
        if role == Qt.ForegroundRole:
            from PySide6.QtGui import QColor
            return QColor("#e74c3c")
        if role == Qt.TextAlignmentRole and col > 0:
            return Qt.AlignCenter | Qt.AlignVCenter
        return None


class TelaDashboard(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._dados: dict = {}
        self._modelo_estoque = EstoqueTableModel()
        self._setup_ui()
        self._atualizar()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._atualizar)
        self._timer.start(5 * 60 * 1000)

    # ── Construção da UI ──────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        titulo = QLabel("Dashboard")
        titulo.setStyleSheet("font-size: 18px; font-weight: bold; color: #ffffff;")
        root.addWidget(titulo)

        # ── Linha 1 — 4 cards resumo ──────────────────────────────────
        row1 = QHBoxLayout()
        row1.setSpacing(12)

        self._f_vendas, self._v_vendas = _card_simples("💰  Vendas Hoje")
        self._f_caixa,  self._v_caixa  = _card_simples("🏦  Caixa")
        self._f_orc,    self._v_orc    = _card_simples("📋  Orçamentos")
        self._f_est,    self._v_est    = _card_simples("📦  Estoque Baixo")

        for f in (self._f_vendas, self._f_caixa, self._f_orc, self._f_est):
            row1.addWidget(f)
        root.addLayout(row1)

        # ── Linha 2 — 2 cards financeiros expandidos ──────────────────
        row2 = QHBoxLayout()
        row2.setSpacing(12)

        self._f_pagar,   self._v_pagar,   self._lay_pagar   = _card_contas("📤  Contas a Pagar")
        self._f_receber, self._v_receber, self._lay_receber = _card_contas("📥  Contas a Receber")

        row2.addWidget(self._f_pagar)
        row2.addWidget(self._f_receber)
        root.addLayout(row2)

        # ── Linha 3 — tabela estoque crítico ──────────────────────────
        sec_est = QWidget()
        lay_est = QVBoxLayout(sec_est)
        lay_est.setContentsMargins(0, 0, 0, 0)
        lay_est.setSpacing(6)

        lbl_est = QLabel("Produtos com estoque crítico (top 5)")
        lbl_est.setStyleSheet("color: #aaaacc; font-size: 12px;")
        lay_est.addWidget(lbl_est)

        self._tabela_estoque = QTableView()
        self._tabela_estoque.setModel(self._modelo_estoque)
        self._tabela_estoque.setEditTriggers(QTableView.NoEditTriggers)
        self._tabela_estoque.setSelectionMode(QTableView.NoSelection)
        self._tabela_estoque.verticalHeader().setVisible(False)
        self._tabela_estoque.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._tabela_estoque.setMaximumHeight(160)
        self._tabela_estoque.setStyleSheet(
            "background: #252535; color: #ffffff; gridline-color: #333355;"
        )
        lay_est.addWidget(self._tabela_estoque)
        root.addWidget(sec_est)

        # ── Rodapé ────────────────────────────────────────────────────
        root.addStretch()
        rodape = QHBoxLayout()
        self._lbl_atualizacao = QLabel("Última atualização: —")
        self._lbl_atualizacao.setStyleSheet("color: #666688; font-size: 11px;")
        rodape.addWidget(self._lbl_atualizacao)
        rodape.addStretch()
        btn_refresh = QPushButton("🔄  Atualizar")
        btn_refresh.clicked.connect(self._atualizar)
        rodape.addWidget(btn_refresh)
        root.addLayout(rodape)

    # ── Atualização ───────────────────────────────────────────────────────

    def _atualizar(self) -> None:
        try:
            dados = service.obter_dados_dashboard()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao carregar dashboard: {e}")
            return
        self._dados = dados
        self._preencher(dados)
        agora = datetime.now().strftime("%H:%M:%S")
        self._lbl_atualizacao.setText(f"Última atualização: {agora}")

    def _preencher(self, d: dict) -> None:
        # Vendas hoje
        v = d["vendas_hoje"]
        self._v_vendas.setText(f"R$ {v['valor']:,.2f}\n{v['total']} venda(s)")
        self._v_vendas.setStyleSheet(
            "font-size: 18px; font-weight: bold; " + (_COR_OK if v["total"] > 0 else _COR_NEUTRO)
        )

        # Caixa
        cx = d["caixa_status"]
        if cx["aberto"]:
            self._v_caixa.setText(f"ABERTO\nSaldo: R$ {cx['saldo_inicial']:,.2f}")
            self._v_caixa.setStyleSheet("font-size: 16px; font-weight: bold; " + _COR_OK)
        else:
            self._v_caixa.setText("FECHADO")
            self._v_caixa.setStyleSheet("font-size: 20px; font-weight: bold; " + _COR_CRITICO)

        # Orçamentos
        orc = d["orcamentos_pendentes"]
        txt_orc = f"{orc['abertos']} aberto(s)"
        cor_orc = _COR_NEUTRO
        if orc["vencidos"] > 0:
            txt_orc += f"\n{orc['vencidos']} vencido(s)"
            cor_orc = _COR_CRITICO
        elif orc["vencendo_hoje"] > 0:
            txt_orc += f"\n{orc['vencendo_hoje']} vence hoje"
            cor_orc = _COR_ALERTA
        self._v_orc.setText(txt_orc)
        self._v_orc.setStyleSheet("font-size: 16px; font-weight: bold; " + cor_orc)

        # Estoque baixo
        est = d["estoque_baixo"]
        self._v_est.setText(f"{est['count']} produto(s)")
        self._v_est.setStyleSheet(
            "font-size: 20px; font-weight: bold; " + (_COR_CRITICO if est["count"] > 0 else _COR_OK)
        )
        self._modelo_estoque.atualizar(est["itens"])

        # Cards de contas
        self._preencher_card_contas(
            resumo_lbl=self._v_pagar,
            lay=self._lay_pagar,
            hoje=d["contas_pagar_hoje"],
            semana=d["contas_pagar_semana"],
            totais=d["contas_vencer_hoje"],
        )
        self._preencher_card_contas(
            resumo_lbl=self._v_receber,
            lay=self._lay_receber,
            hoje=d["contas_receber_hoje_lista"],
            semana=d["contas_receber_semana"],
            totais=d["contas_receber_hoje"],
        )

    def _preencher_card_contas(
        self,
        resumo_lbl: QLabel,
        lay: QVBoxLayout,
        hoje: list[dict],
        semana: list[dict],
        totais: dict,
    ) -> None:
        total_hoje = totais["count"]
        valor_hoje = totais["valor"]
        total_semana = len(semana)

        cor_resumo = _COR_CRITICO if total_hoje > 0 else (_COR_ALERTA if total_semana > 0 else _COR_NEUTRO)
        resumo_lbl.setText(f"Hoje: {total_hoje} (R$ {valor_hoje:,.2f})  |  Próx. 7d: {total_semana}")
        resumo_lbl.setStyleSheet(f"font-size: 12px; font-weight: bold; {cor_resumo}")

        _limpar_layout(lay)

        if not hoje and not semana:
            lbl = QLabel("Nenhuma conta pendente")
            lbl.setStyleSheet(_COR_CINZA + " font-size: 11px;")
            lay.addWidget(lbl)
            lay.addStretch()
            return

        if hoje:
            sec = QLabel("Vencimento HOJE")
            sec.setStyleSheet("color: #888899; font-size: 10px; font-weight: bold;")
            lay.addWidget(sec)
            for c in hoje:
                lay.addWidget(_linha_conta(c["descricao"], c["valor"], _COR_CRITICO))

        if semana:
            sec2 = QLabel("Próximos 7 dias")
            sec2.setStyleSheet("color: #888899; font-size: 10px; font-weight: bold; margin-top: 4px;")
            lay.addWidget(sec2)
            for c in semana:
                data_fmt = c["vencimento"].strftime("%d/%m") if hasattr(c["vencimento"], "strftime") else str(c["vencimento"])
                status_str = c.get("status", "")
                cor = _COR_ALERTA  # a vencer
                lay.addWidget(_linha_conta(c["descricao"], c["valor"], cor, data_fmt))

        lay.addStretch()
