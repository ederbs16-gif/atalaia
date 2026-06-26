from __future__ import annotations

from datetime import date

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from atalaia.modules.orcamentos import service
from atalaia.modules.orcamentos.exceptions import (
    OrcamentoJaFinalizadoError,
    OrcamentoVencidoError,
)
from atalaia.modules.orcamentos.ui.formulario_orcamento import FormularioOrcamento
from atalaia.modules.orcamentos import whatsapp
from atalaia.modules.configuracoes.service import get_config

_COLUNAS = ["Nº", "Cliente", "Criação", "Validade", "Status", "Total"]
_COR_VENCIDO = QColor("#c0392b")


class OrcamentoTableModel(QAbstractTableModel):
    def __init__(self):
        super().__init__()
        self._orcamentos: list = []

    def atualizar(self, orcamentos: list) -> None:
        self.beginResetModel()
        self._orcamentos = orcamentos
        self.endResetModel()

    def orcamento_em_linha(self, row: int):
        if 0 <= row < len(self._orcamentos):
            return self._orcamentos[row]
        return None

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._orcamentos)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(_COLUNAS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return _COLUNAS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None
        orc = self._orcamentos[index.row()]
        col = index.column()
        eh_aberto = orc.status.value == "aberto"
        eh_vencido = eh_aberto and orc.data_validade and date.today() > orc.data_validade

        if role == Qt.DisplayRole:
            if col == 0:
                return service.numero_formatado(orc)
            if col == 1:
                return orc.cliente.nome if orc.cliente else "—"
            if col == 2:
                return str(orc.data_criacao) if orc.data_criacao else "—"
            if col == 3:
                return str(orc.data_validade) if orc.data_validade else "—"
            if col == 4:
                return orc.status.value.capitalize()
            if col == 5:
                itens = orc.itens if orc.itens else []
                subtotal = sum(i.quantidade * i.preco_unitario for i in itens)
                if orc.desconto_percentual:
                    from decimal import Decimal
                    subtotal = subtotal * (1 - orc.desconto_percentual / Decimal("100"))
                return f"R$ {subtotal:,.2f}"

        if role == Qt.ForegroundRole and eh_vencido:
            return _COR_VENCIDO

        if role == Qt.TextAlignmentRole:
            if col == 0:
                return Qt.AlignCenter | Qt.AlignVCenter
            if col == 5:
                return Qt.AlignRight | Qt.AlignVCenter

        return None


class TelaOrcamentos(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._modelo = OrcamentoTableModel()
        self._setup_ui()
        self._aplicar_filtros()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addLayout(self._criar_painel_filtros())
        layout.addWidget(self._criar_tabela())
        layout.addLayout(self._criar_painel_acoes())

    def _criar_painel_filtros(self) -> QHBoxLayout:
        row = QHBoxLayout()

        row.addWidget(QLabel("Status:"))
        self.combo_status = QComboBox()
        self.combo_status.addItems(["Todos", "Aberto", "Aprovado", "Recusado"])
        row.addWidget(self.combo_status)

        row.addWidget(QLabel("Cliente:"))
        self.txt_cliente = QLineEdit()
        self.txt_cliente.setPlaceholderText("Nome do cliente")
        self.txt_cliente.setMaximumWidth(200)
        self.txt_cliente.returnPressed.connect(self._aplicar_filtros)
        row.addWidget(self.txt_cliente)

        btn_buscar = QPushButton("Buscar")
        btn_buscar.clicked.connect(self._aplicar_filtros)
        row.addWidget(btn_buscar)

        btn_limpar = QPushButton("Limpar")
        btn_limpar.clicked.connect(self._limpar_filtros)
        row.addWidget(btn_limpar)

        row.addStretch()
        return row

    def _criar_tabela(self) -> QTableView:
        self.tabela = QTableView()
        self.tabela.setModel(self._modelo)
        self.tabela.setSelectionBehavior(QTableView.SelectRows)
        self.tabela.setSelectionMode(QTableView.SingleSelection)
        self.tabela.setEditTriggers(QTableView.NoEditTriggers)
        self.tabela.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.selectionModel().selectionChanged.connect(self._on_selecao_mudou)
        return self.tabela

    def _criar_painel_acoes(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch()

        self.btn_novo = QPushButton("Novo Orçamento")
        self.btn_novo.clicked.connect(self._novo_orcamento)
        row.addWidget(self.btn_novo)

        self.btn_abrir = QPushButton("Abrir / Editar")
        self.btn_abrir.setEnabled(False)
        self.btn_abrir.clicked.connect(self._abrir_orcamento)
        row.addWidget(self.btn_abrir)

        self.btn_aprovar = QPushButton("Aprovar")
        self.btn_aprovar.setEnabled(False)
        self.btn_aprovar.clicked.connect(self._aprovar_orcamento)
        row.addWidget(self.btn_aprovar)

        self.btn_recusar = QPushButton("Recusar")
        self.btn_recusar.setEnabled(False)
        self.btn_recusar.clicked.connect(self._recusar_orcamento)
        row.addWidget(self.btn_recusar)

        self.btn_whatsapp = QPushButton("📱 WhatsApp")
        self.btn_whatsapp.setEnabled(False)
        self.btn_whatsapp.clicked.connect(self._enviar_whatsapp)
        row.addWidget(self.btn_whatsapp)

        return row

    def _aplicar_filtros(self) -> None:
        status_idx = self.combo_status.currentIndex()
        status = {1: "aberto", 2: "aprovado", 3: "recusado"}.get(status_idx)

        try:
            orcamentos = service.listar_orcamentos(status=status)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao buscar orçamentos: {e}")
            return

        termo = self.txt_cliente.text().strip().lower()
        if termo:
            orcamentos = [
                o for o in orcamentos
                if o.cliente and termo in o.cliente.nome.lower()
            ]

        self._modelo.atualizar(orcamentos)
        self._on_selecao_mudou()

    def _limpar_filtros(self) -> None:
        self.combo_status.setCurrentIndex(0)
        self.txt_cliente.clear()
        self._aplicar_filtros()

    def _on_selecao_mudou(self, *_) -> None:
        orc = self._orcamento_selecionado()
        eh_aberto = orc is not None and orc.status.value == "aberto"
        tem_telefone = (
            orc is not None
            and orc.cliente is not None
            and bool(orc.cliente.telefone and orc.cliente.telefone.strip())
        )
        self.btn_abrir.setEnabled(orc is not None)
        self.btn_aprovar.setEnabled(eh_aberto)
        self.btn_recusar.setEnabled(eh_aberto)
        self.btn_whatsapp.setEnabled(tem_telefone)

    def _orcamento_selecionado(self):
        indexes = self.tabela.selectionModel().selectedRows()
        if not indexes:
            return None
        return self._modelo.orcamento_em_linha(indexes[0].row())

    def _novo_orcamento(self) -> None:
        dlg = FormularioOrcamento(parent=self)
        dlg.exec()
        self._aplicar_filtros()

    def _abrir_orcamento(self) -> None:
        orc = self._orcamento_selecionado()
        if orc is None:
            return
        dlg = FormularioOrcamento(orcamento_id=orc.id, parent=self)
        dlg.exec()
        self._aplicar_filtros()

    def _aprovar_orcamento(self) -> None:
        orc = self._orcamento_selecionado()
        if orc is None:
            return
        resposta = QMessageBox.question(
            self,
            "Aprovar orçamento",
            f"Aprovar {service.numero_formatado(orc)}? O orçamento ficará aguardando importação pelo PDV.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resposta != QMessageBox.Yes:
            return
        try:
            service.aprovar_orcamento(orc.id)
        except OrcamentoVencidoError as ex:
            QMessageBox.warning(self, "Orçamento vencido", str(ex))
            return
        except OrcamentoJaFinalizadoError as ex:
            QMessageBox.warning(self, "Orçamento já finalizado", str(ex))
            return
        except Exception as ex:
            QMessageBox.critical(self, "Erro", f"Erro ao aprovar orçamento: {ex}")
            return
        self._aplicar_filtros()

    def _enviar_whatsapp(self) -> None:
        orc = self._orcamento_selecionado()
        if orc is None:
            return
        if not (orc.cliente and orc.cliente.telefone and orc.cliente.telefone.strip()):
            QMessageBox.warning(
                self, "Sem telefone",
                "Cliente não possui telefone cadastrado. "
                "Cadastre o telefone do cliente para usar esta função.",
            )
            return
        nome_empresa = get_config("nome_empresa", "Atalaia")
        whatsapp.abrir_whatsapp(orc, nome_empresa)
        QMessageBox.information(
            self, "WhatsApp",
            "WhatsApp aberto! Confirme o envio no WhatsApp.",
        )

    def _recusar_orcamento(self) -> None:
        orc = self._orcamento_selecionado()
        if orc is None:
            return
        resposta = QMessageBox.question(
            self,
            "Recusar orçamento",
            f"Recusar {service.numero_formatado(orc)}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resposta != QMessageBox.Yes:
            return
        try:
            service.recusar_orcamento(orc.id)
        except OrcamentoJaFinalizadoError as ex:
            QMessageBox.warning(self, "Não foi possível recusar", str(ex))
            return
        except Exception as ex:
            QMessageBox.critical(self, "Erro", f"Erro ao recusar orçamento: {ex}")
            return
        self._aplicar_filtros()
