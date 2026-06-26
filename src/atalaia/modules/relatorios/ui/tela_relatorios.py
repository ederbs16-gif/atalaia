from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from PySide6.QtCore import QAbstractTableModel, QDate, QModelIndex, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDateEdit,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTabWidget,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from atalaia.modules.relatorios import queries
from atalaia.modules.relatorios.periodo import calcular_periodo
from atalaia.modules.relatorios.ui.exportador import (
    exportar_pdf,
    exportar_sugestao_compra,
    imprimir_relatorio,
)

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    from matplotlib.figure import Figure
    _MPL = True
except ImportError:
    _MPL = False


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _qdate(d: date) -> QDate:
    return QDate(d.year, d.month, d.day)


def _card(label: str, valor: str = "—") -> QWidget:
    w = QWidget()
    lay = QVBoxLayout(w)
    lay.setContentsMargins(12, 8, 12, 8)
    lbl_v = QLabel(valor)
    font = QFont()
    font.setBold(True)
    font.setPointSize(14)
    lbl_v.setFont(font)
    lbl_v.setAlignment(Qt.AlignCenter)
    lbl_l = QLabel(label)
    lbl_l.setAlignment(Qt.AlignCenter)
    lbl_l.setStyleSheet("color: #666;")
    lay.addWidget(lbl_v)
    lay.addWidget(lbl_l)
    w.setStyleSheet("QWidget { border: 1px solid #ddd; border-radius: 6px; background: #fafafa; }")
    w._lbl_v = lbl_v
    return w


def _canvas_vazio() -> "FigureCanvasQTAgg | QLabel":
    if not _MPL:
        lbl = QLabel("matplotlib não instalado")
        lbl.setAlignment(Qt.AlignCenter)
        return lbl
    fig = Figure(figsize=(6, 3), tight_layout=True)
    canvas = FigureCanvasQTAgg(fig)
    canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
    canvas.setMinimumHeight(220)
    canvas.setMaximumHeight(280)
    return canvas


# ─── Painel de filtro de período ──────────────────────────────────────────────

class _PainelPeriodo(QWidget):
    def __init__(self, com_periodo: bool = True, parent=None):
        super().__init__(parent)
        self._com_periodo = com_periodo
        self._build()

    def _build(self) -> None:
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        if not self._com_periodo:
            btn = QPushButton("🔄 Atualizar")
            btn.clicked.connect(self._emit_gerar)
            lay.addWidget(btn)
            lay.addStretch()
            self._gerar_cb = None
            return

        for label, tipo in [("Hoje", "diario"), ("Semana", "semanal"), ("Mês", "mensal")]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, t=tipo: self._aplicar_rapido(t))
            lay.addWidget(btn)

        lay.addWidget(QLabel("De:"))
        self.date_ini = QDateEdit(_qdate(date.today().replace(day=1)))
        self.date_ini.setCalendarPopup(True)
        self.date_ini.setDisplayFormat("dd/MM/yyyy")
        lay.addWidget(self.date_ini)

        lay.addWidget(QLabel("Até:"))
        self.date_fim = QDateEdit(_qdate(date.today()))
        self.date_fim.setCalendarPopup(True)
        self.date_fim.setDisplayFormat("dd/MM/yyyy")
        lay.addWidget(self.date_fim)

        btn_gerar = QPushButton("Gerar")
        btn_gerar.clicked.connect(self._emit_gerar)
        lay.addWidget(btn_gerar)
        lay.addStretch()
        self._gerar_cb = None

    def on_gerar(self, callback) -> None:
        self._gerar_cb = callback

    def _aplicar_rapido(self, tipo: str) -> None:
        ini, fim = calcular_periodo(tipo)
        if ini and fim:
            self.date_ini.setDate(_qdate(ini))
            self.date_fim.setDate(_qdate(fim))
        self._emit_gerar()

    def _emit_gerar(self) -> None:
        if self._gerar_cb:
            self._gerar_cb()

    def periodo(self) -> tuple[date, date]:
        if not self._com_periodo:
            return date.today(), date.today()
        qi = self.date_ini.date()
        qf = self.date_fim.date()
        return date(qi.year(), qi.month(), qi.day()), date(qf.year(), qf.month(), qf.day())


# ─── Table Models genéricos ───────────────────────────────────────────────────

class _DictTableModel(QAbstractTableModel):
    def __init__(self, headers: list[str]):
        super().__init__()
        self._headers = headers
        self._dados: list[list] = []

    def atualizar(self, dados: list[list]) -> None:
        self.beginResetModel()
        self._dados = dados
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._dados)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(self._headers)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return self._headers[section]
        return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        if role == Qt.DisplayRole:
            return str(self._dados[index.row()][index.column()])
        if role == Qt.TextAlignmentRole and index.column() >= 1:
            return Qt.AlignRight | Qt.AlignVCenter
        return None

    def linha(self, row: int) -> list | None:
        return self._dados[row] if 0 <= row < len(self._dados) else None


class _EstoqueTableModel(_DictTableModel):
    _COR_VENCIDO = QColor("#c0392b")
    _COR_ZERO = QColor("#cc8800")

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        base = super().data(index, role)
        if role == Qt.ForegroundRole:
            row = self._dados[index.row()]
            diff = int(row[4]) if len(row) > 4 else 0
            if diff < 0:
                return self._COR_VENCIDO
            if diff == 0:
                return self._COR_ZERO
        return base


class _ContaTableModel(_DictTableModel):
    _COR_VENCIDO = QColor("#c0392b")
    _COR_PAGO = QColor("#888888")

    def __init__(self, headers: list[str]):
        super().__init__(headers)
        self._vencidos: set[int] = set()
        self._pagos: set[int] = set()

    def atualizar_contas(self, itens: list[dict]) -> None:
        self._vencidos = set()
        self._pagos = set()
        rows = []
        for i, item in enumerate(itens):
            if item.get("status") == "pago":
                self._pagos.add(i)
            elif item.get("vencido"):
                self._vencidos.add(i)
            rows.append([
                item.get("descricao", ""),
                item.get("vencimento", ""),
                f"R$ {item.get('valor_total', 0):,.2f}",
                f"R$ {item.get('valor_pago', 0):,.2f}",
                item.get("status", "").replace("_", " "),
            ])
        self.atualizar(rows)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        base = super().data(index, role)
        if role == Qt.ForegroundRole:
            row = index.row()
            if row in self._pagos:
                return self._COR_PAGO
            if row in self._vencidos:
                return self._COR_VENCIDO
        return base


def _tabela(model: QAbstractTableModel) -> QTableView:
    t = QTableView()
    t.setModel(model)
    t.setSelectionBehavior(QAbstractItemView.SelectRows)
    t.setEditTriggers(QAbstractItemView.NoEditTriggers)
    t.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
    t.verticalHeader().setVisible(False)
    return t


# ─── Aba Vendas ───────────────────────────────────────────────────────────────

class _AbaVendas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._dados: dict = {}
        self._build()

    def _build(self) -> None:
        lay = QVBoxLayout(self)

        self._filtro = _PainelPeriodo()
        self._filtro.on_gerar(self.gerar)
        lay.addWidget(self._filtro)

        # Cards
        row_cards = QHBoxLayout()
        self._card_total = _card("Total Vendas", "0")
        self._card_liquido = _card("Valor Líquido", "R$ 0,00")
        self._card_ticket = _card("Ticket Médio", "R$ 0,00")
        for c in (self._card_total, self._card_liquido, self._card_ticket):
            row_cards.addWidget(c)
        lay.addLayout(row_cards)

        # Gráfico
        self._canvas = _canvas_vazio()
        lay.addWidget(self._canvas)

        # Tabela
        self._model = _DictTableModel(["Data", "Qtd Vendas", "Valor Bruto", "Desconto", "Valor Líquido"])
        lay.addWidget(_tabela(self._model))

        # Rodapé
        row_footer = QHBoxLayout()
        btn_print = QPushButton("🖨️ Imprimir")
        btn_print.clicked.connect(lambda: imprimir_relatorio(self, "Vendas por Período"))
        btn_pdf = QPushButton("📄 Exportar PDF")
        btn_pdf.clicked.connect(lambda: exportar_pdf(self, "Vendas por Período"))
        row_footer.addStretch()
        row_footer.addWidget(btn_print)
        row_footer.addWidget(btn_pdf)
        lay.addLayout(row_footer)

    def gerar(self) -> None:
        ini, fim = self._filtro.periodo()
        try:
            dados = queries.vendas_por_periodo(ini, fim)
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return
        self._dados = dados
        self._card_total._lbl_v.setText(str(dados["total_vendas"]))
        self._card_liquido._lbl_v.setText(f"R$ {dados['valor_liquido']:,.2f}")
        self._card_ticket._lbl_v.setText(f"R$ {dados['ticket_medio']:,.2f}")

        agrupado = dados.get("agrupado_por_dia", [])
        if _MPL:
            fig = self._canvas.figure
            fig.clear()
            ax = fig.add_subplot(111)
            if agrupado:
                datas = [r["data"] for r in agrupado]
                valores = [float(r["valor"]) for r in agrupado]
                ax.plot(datas, valores, marker="o", color="#00B89A")
                ax.set_ylabel("R$")
                if len(datas) > 10:
                    ax.set_xticks(datas[::max(1, len(datas)//8)])
                ax.tick_params(axis="x", rotation=30)
            else:
                ax.text(0.5, 0.5, "Sem dados no período", ha="center", va="center",
                        transform=ax.transAxes, color="#888")
            ax.set_title("Valor líquido por dia")
            fig.tight_layout()
            self._canvas.draw()

        rows = [
            [r["data"], "—", "—", "—", f"R$ {r['valor']:,.2f}"]
            for r in agrupado
        ]
        self._model.atualizar(rows)


# ─── Aba Mais Vendidos ────────────────────────────────────────────────────────

class _AbaMaisVendidos(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        lay = QVBoxLayout(self)

        self._filtro = _PainelPeriodo()
        self._filtro.on_gerar(self.gerar)
        lay.addWidget(self._filtro)

        self._canvas = _canvas_vazio()
        lay.addWidget(self._canvas)

        self._model = _DictTableModel(["Produto", "Categoria", "Qtd Vendida", "Valor Total"])
        lay.addWidget(_tabela(self._model))

        row_footer = QHBoxLayout()
        btn_print = QPushButton("🖨️ Imprimir")
        btn_print.clicked.connect(lambda: imprimir_relatorio(self, "Produtos Mais Vendidos"))
        btn_pdf = QPushButton("📄 Exportar PDF")
        btn_pdf.clicked.connect(lambda: exportar_pdf(self, "Produtos Mais Vendidos"))
        row_footer.addStretch()
        row_footer.addWidget(btn_print)
        row_footer.addWidget(btn_pdf)
        lay.addLayout(row_footer)

    def gerar(self) -> None:
        ini, fim = self._filtro.periodo()
        try:
            dados = queries.produtos_mais_vendidos(ini, fim)
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return

        if _MPL:
            fig = self._canvas.figure
            fig.clear()
            ax = fig.add_subplot(111)
            if dados:
                nomes = [d["nome"][:25] for d in dados]
                qtds = [d["quantidade_total"] for d in dados]
                ax.barh(nomes[::-1], qtds[::-1], color="#00B89A")
                ax.set_xlabel("Quantidade")
            else:
                ax.text(0.5, 0.5, "Sem dados no período", ha="center", va="center",
                        transform=ax.transAxes, color="#888")
            ax.set_title("Top 10 produtos por quantidade")
            fig.tight_layout()
            self._canvas.draw()

        rows = [
            [d["nome"], d["categoria"], d["quantidade_total"], f"R$ {d['valor_total']:,.2f}"]
            for d in dados
        ]
        self._model.atualizar(rows)


# ─── Aba Estoque Baixo ────────────────────────────────────────────────────────

class _AbaEstoqueBaixo(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._itens: list[dict] = []
        self._build()

    def _build(self) -> None:
        lay = QVBoxLayout(self)

        self._filtro = _PainelPeriodo(com_periodo=False)
        self._filtro.on_gerar(self.gerar)
        lay.addWidget(self._filtro)

        self._model = _EstoqueTableModel(["Produto", "Categoria", "Estoque Atual", "Estoque Mínimo", "Diferença"])
        lay.addWidget(_tabela(self._model))

        row_footer = QHBoxLayout()
        btn_sugestao = QPushButton("📋 Gerar Sugestão de Compra")
        btn_sugestao.clicked.connect(self._exportar_sugestao)
        btn_print = QPushButton("🖨️ Imprimir")
        btn_print.clicked.connect(lambda: imprimir_relatorio(self, "Estoque Baixo"))
        btn_pdf = QPushButton("📄 Exportar PDF")
        btn_pdf.clicked.connect(lambda: exportar_pdf(self, "Estoque Baixo"))
        row_footer.addWidget(btn_sugestao)
        row_footer.addStretch()
        row_footer.addWidget(btn_print)
        row_footer.addWidget(btn_pdf)
        lay.addLayout(row_footer)

        self.gerar()

    def gerar(self) -> None:
        try:
            self._itens = queries.estoque_baixo()
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return
        rows = [
            [d["nome"], d["categoria"], d["estoque_atual"], d["estoque_minimo"], d["diferenca"]]
            for d in self._itens
        ]
        self._model.atualizar(rows)

    def _exportar_sugestao(self) -> None:
        if not self._itens:
            QMessageBox.information(self, "Sem dados", "Nenhum produto com estoque baixo.")
            return
        exportar_sugestao_compra(self._itens, parent=self)


# ─── Aba Fluxo de Caixa ──────────────────────────────────────────────────────

class _AbaFluxoCaixa(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        lay = QVBoxLayout(self)

        self._filtro = _PainelPeriodo()
        self._filtro.on_gerar(self.gerar)
        lay.addWidget(self._filtro)

        row_cards = QHBoxLayout()
        self._card_ent = _card("Total Entradas", "R$ 0,00")
        self._card_sai = _card("Total Saídas", "R$ 0,00")
        self._card_saldo = _card("Saldo do Período", "R$ 0,00")
        for c in (self._card_ent, self._card_sai, self._card_saldo):
            row_cards.addWidget(c)
        lay.addLayout(row_cards)

        self._canvas = _canvas_vazio()
        lay.addWidget(self._canvas)

        self._model = _DictTableModel(["Forma", "Entradas"])
        lay.addWidget(_tabela(self._model))

        row_footer = QHBoxLayout()
        btn_print = QPushButton("🖨️ Imprimir")
        btn_print.clicked.connect(lambda: imprimir_relatorio(self, "Fluxo de Caixa"))
        btn_pdf = QPushButton("📄 Exportar PDF")
        btn_pdf.clicked.connect(lambda: exportar_pdf(self, "Fluxo de Caixa"))
        row_footer.addStretch()
        row_footer.addWidget(btn_print)
        row_footer.addWidget(btn_pdf)
        lay.addLayout(row_footer)

    def gerar(self) -> None:
        ini, fim = self._filtro.periodo()
        try:
            dados = queries.fluxo_de_caixa(ini, fim)
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return

        self._card_ent._lbl_v.setText(f"R$ {dados['entradas_total']:,.2f}")
        self._card_sai._lbl_v.setText(f"R$ {dados['saidas_total']:,.2f}")
        saldo = dados["saldo"]
        self._card_saldo._lbl_v.setText(f"R$ {saldo:,.2f}")
        self._card_saldo._lbl_v.setStyleSheet(
            "color: #27ae60;" if saldo >= 0 else "color: #c0392b;"
        )

        por_dia = dados.get("por_dia", [])
        if _MPL:
            fig = self._canvas.figure
            fig.clear()
            ax = fig.add_subplot(111)
            if por_dia:
                datas = [r["data"] for r in por_dia]
                entradas = [float(r["entrada"]) for r in por_dia]
                saidas = [float(r["saida"]) for r in por_dia]
                x = range(len(datas))
                ax.bar(x, entradas, label="Entradas", color="#27ae60", alpha=0.8)
                ax.bar(x, [-s for s in saidas], label="Saídas", color="#c0392b", alpha=0.8)
                ax.set_xticks(list(x))
                ax.set_xticklabels(datas, rotation=30, ha="right")
                ax.legend()
            else:
                ax.text(0.5, 0.5, "Sem dados no período", ha="center", va="center",
                        transform=ax.transAxes, color="#888")
            ax.set_title("Entradas vs Saídas por dia")
            fig.tight_layout()
            self._canvas.draw()

        por_forma = dados.get("por_forma", {})
        rows = [
            [forma.capitalize(), f"R$ {valor:,.2f}"]
            for forma, valor in por_forma.items()
        ]
        self._model.atualizar(rows)


# ─── Aba Contas ───────────────────────────────────────────────────────────────

class _AbaContas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._build()

    def _build(self) -> None:
        lay = QVBoxLayout(self)

        self._filtro = _PainelPeriodo()
        self._filtro.on_gerar(self.gerar)
        lay.addWidget(self._filtro)

        splitter = QSplitter(Qt.Horizontal)

        # Painel Pagar
        w_pagar = QWidget()
        lay_pagar = QVBoxLayout(w_pagar)
        lay_pagar.addWidget(QLabel("<b>Contas a Pagar</b>"))
        row_pagar = QHBoxLayout()
        self._cp_pendente = _card("Pendente", "R$ 0,00")
        self._cp_vencido = _card("Vencido", "R$ 0,00")
        self._cp_pago = _card("Pago", "R$ 0,00")
        self._cp_vencido._lbl_v.setStyleSheet("color: #c0392b;")
        for c in (self._cp_pendente, self._cp_vencido, self._cp_pago):
            row_pagar.addWidget(c)
        lay_pagar.addLayout(row_pagar)
        self._model_pagar = _ContaTableModel(["Descrição", "Vencimento", "Total", "Pago", "Status"])
        lay_pagar.addWidget(_tabela(self._model_pagar))
        splitter.addWidget(w_pagar)

        # Painel Receber
        w_receber = QWidget()
        lay_receber = QVBoxLayout(w_receber)
        lay_receber.addWidget(QLabel("<b>Contas a Receber</b>"))
        row_receber = QHBoxLayout()
        self._cr_pendente = _card("Pendente", "R$ 0,00")
        self._cr_vencido = _card("Vencido", "R$ 0,00")
        self._cr_pago = _card("Pago", "R$ 0,00")
        self._cr_vencido._lbl_v.setStyleSheet("color: #c0392b;")
        for c in (self._cr_pendente, self._cr_vencido, self._cr_pago):
            row_receber.addWidget(c)
        lay_receber.addLayout(row_receber)
        self._model_receber = _ContaTableModel(["Descrição", "Vencimento", "Total", "Pago", "Status"])
        lay_receber.addWidget(_tabela(self._model_receber))
        splitter.addWidget(w_receber)

        lay.addWidget(splitter)

        row_footer = QHBoxLayout()
        btn_print = QPushButton("🖨️ Imprimir")
        btn_print.clicked.connect(lambda: imprimir_relatorio(self, "Contas a Pagar/Receber"))
        btn_pdf = QPushButton("📄 Exportar PDF")
        btn_pdf.clicked.connect(lambda: exportar_pdf(self, "Contas a Pagar/Receber"))
        row_footer.addStretch()
        row_footer.addWidget(btn_print)
        row_footer.addWidget(btn_pdf)
        lay.addLayout(row_footer)

    def gerar(self) -> None:
        ini, fim = self._filtro.periodo()
        try:
            dados = queries.contas_a_pagar_receber(ini, fim)
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return

        pagar = dados["pagar"]
        self._cp_pendente._lbl_v.setText(f"R$ {pagar['total_pendente']:,.2f}")
        self._cp_vencido._lbl_v.setText(f"R$ {pagar['total_vencido']:,.2f}")
        self._cp_pago._lbl_v.setText(f"R$ {pagar['total_pago']:,.2f}")
        self._model_pagar.atualizar_contas(pagar["itens"])

        receber = dados["receber"]
        self._cr_pendente._lbl_v.setText(f"R$ {receber['total_pendente']:,.2f}")
        self._cr_vencido._lbl_v.setText(f"R$ {receber['total_vencido']:,.2f}")
        self._cr_pago._lbl_v.setText(f"R$ {receber['total_pago']:,.2f}")
        self._model_receber.atualizar_contas(receber["itens"])


# ─── TelaRelatorios ───────────────────────────────────────────────────────────

class TelaRelatorios(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)

        self.tabWidget = QTabWidget()
        self._aba_vendas = _AbaVendas()
        self._aba_mais_vendidos = _AbaMaisVendidos()
        self._aba_estoque = _AbaEstoqueBaixo()
        self._aba_fluxo = _AbaFluxoCaixa()
        self._aba_contas = _AbaContas()

        self.tabWidget.addTab(self._aba_vendas, "📈 Vendas")
        self.tabWidget.addTab(self._aba_mais_vendidos, "🏆 Mais Vendidos")
        self.tabWidget.addTab(self._aba_estoque, "📦 Estoque Baixo")
        self.tabWidget.addTab(self._aba_fluxo, "💰 Fluxo de Caixa")
        self.tabWidget.addTab(self._aba_contas, "📋 Contas")

        lay.addWidget(self.tabWidget)
