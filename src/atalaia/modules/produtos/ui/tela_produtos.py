from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
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

from atalaia.db.models.produto import TipoEnum
from atalaia.modules.produtos import service
from atalaia.modules.produtos.ui.formulario_produto import FormularioProduto

_COLUNAS = [
    "Nome",
    "Tipo",
    "Categoria",
    "Preço de Venda",
    "Preço Vigente",
    "Estoque",
    "Status",
]

_COR_PROMOCAO = QColor("#FFF3CD")   # amarelo suave — preço vigente em promoção
_COR_INATIVO = QColor("#AAAAAA")    # cinza — produto inativo


class ProdutoTableModel(QAbstractTableModel):
    """Model customizado para QTableView — padrão a reutilizar em todos os módulos."""

    def __init__(self, produtos: list = None):
        super().__init__()
        self._produtos: list = produtos or []

    def atualizar(self, produtos: list) -> None:
        self.beginResetModel()
        self._produtos = produtos
        self.endResetModel()

    def produto_em_linha(self, row: int):
        if 0 <= row < len(self._produtos):
            return self._produtos[row]
        return None

    # --- QAbstractTableModel interface ---

    def rowCount(self, parent=QModelIndex()) -> int:
        return len(self._produtos)

    def columnCount(self, parent=QModelIndex()) -> int:
        return len(_COLUNAS)

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            return _COLUNAS[section]
        return None

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        if not index.isValid():
            return None

        p = self._produtos[index.row()]
        col = index.column()
        preco_vigente: Decimal = service.obter_preco_vigente(p)
        em_promocao: bool = preco_vigente != p.preco_venda

        if role == Qt.DisplayRole:
            if col == 0:
                return p.nome
            if col == 1:
                return "Produto" if p.tipo == TipoEnum.produto else "Serviço"
            if col == 2:
                return p.categoria.nome if p.categoria else "—"
            if col == 3:
                return f"R$ {p.preco_venda:,.2f}"
            if col == 4:
                sufixo = " ★" if em_promocao else ""
                return f"R$ {preco_vigente:,.2f}{sufixo}"
            if col == 5:
                return str(p.estoque_atual) if p.controla_estoque else "—"
            if col == 6:
                return "Ativo" if p.ativo else "Inativo"

        if role == Qt.BackgroundRole:
            if col == 4 and em_promocao:
                return _COR_PROMOCAO

        if role == Qt.ForegroundRole:
            if not p.ativo:
                return _COR_INATIVO

        if role == Qt.TextAlignmentRole:
            if col in (3, 4, 5):
                return Qt.AlignRight | Qt.AlignVCenter

        return None


class TelaProdutos(QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self._categorias: list = []
        self._modelo = ProdutoTableModel()
        self._setup_ui()
        self._popular_combo_categorias()
        self._aplicar_filtros()

    # ------------------------------------------------------------------
    # Construção da UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.addLayout(self._criar_painel_filtros())
        layout.addWidget(self._criar_tabela())
        layout.addLayout(self._criar_painel_acoes())

    def _criar_painel_filtros(self) -> QHBoxLayout:
        row = QHBoxLayout()

        row.addWidget(QLabel("Tipo:"))
        self.combo_tipo = QComboBox()
        self.combo_tipo.addItems(["Todos", "Produto", "Serviço"])
        row.addWidget(self.combo_tipo)

        row.addWidget(QLabel("Categoria:"))
        self.combo_categoria = QComboBox()
        self.combo_categoria.addItem("Todas")
        row.addWidget(self.combo_categoria)

        row.addWidget(QLabel("Status:"))
        self.combo_status = QComboBox()
        self.combo_status.addItems(["Ativos", "Inativos", "Todos"])
        row.addWidget(self.combo_status)

        row.addWidget(QLabel("Buscar:"))
        self.txt_buscar = QLineEdit()
        self.txt_buscar.setPlaceholderText("Nome ou código de barras")
        self.txt_buscar.returnPressed.connect(self._aplicar_filtros)
        row.addWidget(self.txt_buscar)

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
        self.tabela.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.tabela.verticalHeader().setVisible(False)
        self.tabela.selectionModel().selectionChanged.connect(self._on_selecao_mudou)
        return self.tabela

    def _criar_painel_acoes(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch()

        self.btn_novo = QPushButton("Novo Produto")
        self.btn_novo.clicked.connect(self._novo_produto)
        row.addWidget(self.btn_novo)

        self.btn_editar = QPushButton("Editar")
        self.btn_editar.setEnabled(False)
        self.btn_editar.clicked.connect(self._editar_produto)
        row.addWidget(self.btn_editar)

        self.btn_inativar = QPushButton("Inativar")
        self.btn_inativar.setEnabled(False)
        self.btn_inativar.clicked.connect(self._inativar_produto)
        row.addWidget(self.btn_inativar)

        return row

    # ------------------------------------------------------------------
    # Carregamento de dados
    # ------------------------------------------------------------------

    def _popular_combo_categorias(self) -> None:
        try:
            self._categorias = service.listar_categorias()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao carregar categorias: {e}")
            self._categorias = []

        self.combo_categoria.clear()
        self.combo_categoria.addItem("Todas")
        for cat in self._categorias:
            self.combo_categoria.addItem(cat.nome)

    def _aplicar_filtros(self) -> None:
        termo = self.txt_buscar.text().strip()
        tipo_idx = self.combo_tipo.currentIndex()
        cat_idx = self.combo_categoria.currentIndex()
        status_idx = self.combo_status.currentIndex()

        tipo = {1: "produto", 2: "servico"}.get(tipo_idx)
        cat_id = self._categorias[cat_idx - 1].id if cat_idx > 0 else None
        # 0=Ativos → apenas_ativos=True (SQL filtra só ativos)
        # 1=Inativos → apenas_ativos=False (SQL traz ambos; filtramos inativos abaixo)
        # 2=Todos   → apenas_ativos=False (SQL traz ambos)
        apenas_ativos = (status_idx == 0)

        try:
            if termo:
                produtos = service.buscar_produtos_por_termo(
                    termo, tipo=tipo, categoria_id=cat_id, apenas_ativos=apenas_ativos
                )
            else:
                produtos = service.listar_produtos(
                    tipo=tipo, categoria_id=cat_id, apenas_ativos=apenas_ativos
                )
            # "Inativos": apenas_ativos=False traz ativos+inativos via SQL; manter só inativos.
            # Pós-filtro necessário porque listar_produtos não tem parâmetro apenas_inativos.
            if status_idx == 1:
                produtos = [p for p in produtos if not p.ativo]
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao buscar produtos: {e}")
            return

        self._modelo.atualizar(produtos)
        self._on_selecao_mudou()

    def _limpar_filtros(self) -> None:
        self.combo_tipo.setCurrentIndex(0)
        self.combo_categoria.setCurrentIndex(0)
        self.combo_status.setCurrentIndex(0)
        self.txt_buscar.clear()
        self._aplicar_filtros()

    # ------------------------------------------------------------------
    # Seleção e botões de ação
    # ------------------------------------------------------------------

    def _on_selecao_mudou(self, *_) -> None:
        p = self._produto_selecionado()
        self.btn_editar.setEnabled(p is not None)
        self.btn_inativar.setEnabled(p is not None and p.ativo)

    def _produto_selecionado(self):
        indexes = self.tabela.selectionModel().selectedRows()
        if not indexes:
            return None
        return self._modelo.produto_em_linha(indexes[0].row())

    def _novo_produto(self) -> None:
        formulario = FormularioProduto(parent=self)
        if formulario.exec() == QDialog.Accepted:
            self._aplicar_filtros()

    def _editar_produto(self) -> None:
        p = self._produto_selecionado()
        if p is None:
            return
        formulario = FormularioProduto(produto_id=p.id, parent=self)
        if formulario.exec() == QDialog.Accepted:
            self._aplicar_filtros()

    def _inativar_produto(self) -> None:
        p = self._produto_selecionado()
        if p is None:
            return

        resposta = QMessageBox.question(
            self,
            "Confirmar inativação",
            f"Inativar o produto '{p.nome}'?\n\nEle não aparecerá mais nas listagens ativas.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if resposta != QMessageBox.Yes:
            return

        try:
            service.inativar_produto(p.id)
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao inativar produto: {e}")
            return

        self._aplicar_filtros()
