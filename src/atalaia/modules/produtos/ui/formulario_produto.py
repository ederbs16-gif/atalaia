from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from atalaia.db.models.produto import TipoEnum
from atalaia.modules.produtos import service
from atalaia.modules.produtos.exceptions import (
    CategoriaNaoEncontradaError,
    CodigoBarrasDuplicadoError,
    DescontoMaximoForaDoIntervaloError,
    PromocaoInvalidaError,
    ProdutosError,
)
from atalaia.modules.produtos.ui.dialogo_categoria import DialogoCategoria

_MAX_ESTOQUE = 1_000_000


class FormularioProduto(QDialog):
    """
    Formulário de criar/editar produto.

    produto_id=None  -> modo Criar (Estoque Inicial editável; chama criar_produto)
    produto_id=int   -> modo Editar (Estoque Inicial vira label read-only;
                        estoque_atual nunca entra no dict; chama atualizar_produto)

    Nunca acessa get_session() diretamente — toda persistência passa por service.
    """

    def __init__(self, produto_id: int | None = None, parent=None):
        super().__init__(parent)
        self._produto_id = produto_id
        self._modo_editar = produto_id is not None
        self._categorias: list = []
        self._produto_salvo = False

        self.setWindowTitle("Editar Produto" if self._modo_editar else "Novo Produto")
        self._setup_ui()
        self._popular_categorias()
        if self._modo_editar:
            self._carregar_produto()
        self._on_tipo_mudou()
        self._on_permite_desconto_mudou()
        self._on_em_promocao_mudou()

    # ------------------------------------------------------------------
    # Construção da UI
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_nome = QLineEdit()
        form.addRow("Nome *:", self.txt_nome)

        self.txt_descricao = QPlainTextEdit()
        self.txt_descricao.setMaximumHeight(60)
        form.addRow("Descrição:", self.txt_descricao)

        self.combo_tipo = QComboBox()
        self.combo_tipo.addItem("Produto", TipoEnum.produto)
        self.combo_tipo.addItem("Serviço", TipoEnum.servico)
        self.combo_tipo.currentIndexChanged.connect(self._on_tipo_mudou)
        form.addRow("Tipo:", self.combo_tipo)

        cat_row = QHBoxLayout()
        self.combo_categoria = QComboBox()
        cat_row.addWidget(self.combo_categoria, 1)
        self.btn_nova_categoria = QPushButton("+")
        self.btn_nova_categoria.setMaximumWidth(32)
        self.btn_nova_categoria.setToolTip("Nova categoria")
        self.btn_nova_categoria.clicked.connect(self._abrir_dialogo_categoria)
        cat_row.addWidget(self.btn_nova_categoria)
        cat_widget = QWidget()
        cat_widget.setLayout(cat_row)
        form.addRow("Categoria:", cat_widget)

        self.chk_controla_estoque = QCheckBox("Controla estoque")
        self.chk_controla_estoque.setChecked(True)
        form.addRow("", self.chk_controla_estoque)

        # Estoque Inicial (Criar) ou label read-only (Editar)
        self.spin_estoque_inicial = QSpinBox()
        self.spin_estoque_inicial.setMaximum(_MAX_ESTOQUE)
        self.lbl_estoque_atual = QLabel()
        if self._modo_editar:
            form.addRow("Estoque:", self.lbl_estoque_atual)
        else:
            form.addRow("Estoque inicial:", self.spin_estoque_inicial)

        self.spin_estoque_minimo = QSpinBox()
        self.spin_estoque_minimo.setMaximum(_MAX_ESTOQUE)
        form.addRow("Estoque mínimo:", self.spin_estoque_minimo)

        self.txt_preco_custo = QLineEdit()
        self.txt_preco_custo.setPlaceholderText("opcional")
        form.addRow("Preço de custo:", self.txt_preco_custo)

        self.txt_preco_venda = QLineEdit()
        form.addRow("Preço de venda *:", self.txt_preco_venda)

        self.chk_permite_desconto = QCheckBox("Permite desconto")
        self.chk_permite_desconto.toggled.connect(self._on_permite_desconto_mudou)
        form.addRow("", self.chk_permite_desconto)

        self.txt_desconto_maximo = QLineEdit()
        self.txt_desconto_maximo.setPlaceholderText("0 a 100")
        form.addRow("Desconto máximo (%):", self.txt_desconto_maximo)

        self.chk_em_promocao = QCheckBox("Produto em promoção")
        self.chk_em_promocao.toggled.connect(self._on_em_promocao_mudou)
        form.addRow("", self.chk_em_promocao)

        self.txt_preco_promocional = QLineEdit()
        form.addRow("Preço promocional:", self.txt_preco_promocional)

        self.date_promo_inicio = QDateEdit()
        self.date_promo_inicio.setCalendarPopup(True)
        self.date_promo_inicio.setDate(QDate.currentDate())
        form.addRow("Promoção início:", self.date_promo_inicio)

        self.date_promo_fim = QDateEdit()
        self.date_promo_fim.setCalendarPopup(True)
        self.date_promo_fim.setDate(QDate.currentDate())
        form.addRow("Promoção fim:", self.date_promo_fim)

        self.txt_codigo_barras = QLineEdit()
        self.txt_codigo_barras.setPlaceholderText("opcional")
        form.addRow("Código de barras:", self.txt_codigo_barras)

        self.txt_unidade = QLineEdit("UN")
        form.addRow("Unidade de medida:", self.txt_unidade)

        layout.addLayout(form)

        botoes = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        botoes.button(QDialogButtonBox.Save).setText("Salvar")
        botoes.button(QDialogButtonBox.Cancel).setText("Cancelar")
        botoes.accepted.connect(self._salvar)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)

    # ------------------------------------------------------------------
    # Carregamento de dados
    # ------------------------------------------------------------------

    def _popular_categorias(self, selecionar_id: int | None = None) -> None:
        try:
            self._categorias = service.listar_categorias()
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro ao carregar categorias: {e}")
            self._categorias = []

        self.combo_categoria.clear()
        for cat in self._categorias:
            self.combo_categoria.addItem(cat.nome, cat.id)

        if selecionar_id is not None:
            idx = self.combo_categoria.findData(selecionar_id)
            if idx >= 0:
                self.combo_categoria.setCurrentIndex(idx)

    def _carregar_produto(self) -> None:
        p = service.obter_produto(self._produto_id)
        if p is None:
            QMessageBox.critical(self, "Erro", f"Produto {self._produto_id} não encontrado.")
            self.reject()
            return

        self.txt_nome.setText(p.nome)
        self.txt_descricao.setPlainText(p.descricao or "")

        idx_tipo = self.combo_tipo.findData(p.tipo)
        if idx_tipo >= 0:
            self.combo_tipo.setCurrentIndex(idx_tipo)

        idx_cat = self.combo_categoria.findData(p.categoria_id)
        if idx_cat >= 0:
            self.combo_categoria.setCurrentIndex(idx_cat)

        self.chk_controla_estoque.setChecked(p.controla_estoque)
        self.lbl_estoque_atual.setText(
            f"{p.estoque_atual} (use as telas de Entrada de Mercadoria ou PDV para alterar)"
        )
        self.spin_estoque_minimo.setValue(p.estoque_minimo)

        self.txt_preco_custo.setText("" if p.preco_custo is None else str(p.preco_custo))
        self.txt_preco_venda.setText(str(p.preco_venda))

        self.chk_permite_desconto.setChecked(p.permite_desconto)
        self.txt_desconto_maximo.setText(str(p.desconto_maximo_percentual))

        self.chk_em_promocao.setChecked(p.produto_em_promocao)
        if p.preco_promocional is not None:
            self.txt_preco_promocional.setText(str(p.preco_promocional))
        if p.promocao_inicio is not None:
            self.date_promo_inicio.setDate(QDate(p.promocao_inicio))
        if p.promocao_fim is not None:
            self.date_promo_fim.setDate(QDate(p.promocao_fim))

        self.txt_codigo_barras.setText(p.codigo_barras or "")
        self.txt_unidade.setText(p.unidade_medida)

    # ------------------------------------------------------------------
    # Dinâmica de campos
    # ------------------------------------------------------------------

    def _on_tipo_mudou(self, *_) -> None:
        eh_servico = self.combo_tipo.currentData() == TipoEnum.servico
        if eh_servico:
            self.chk_controla_estoque.setChecked(False)
        self.chk_controla_estoque.setEnabled(not eh_servico)

    def _on_permite_desconto_mudou(self, *_) -> None:
        self.txt_desconto_maximo.setEnabled(self.chk_permite_desconto.isChecked())

    def _on_em_promocao_mudou(self, *_) -> None:
        ativo = self.chk_em_promocao.isChecked()
        self.txt_preco_promocional.setEnabled(ativo)
        self.date_promo_inicio.setEnabled(ativo)
        self.date_promo_fim.setEnabled(ativo)

    def _abrir_dialogo_categoria(self) -> None:
        dialogo = DialogoCategoria(self)
        if dialogo.exec() == QDialog.Accepted:
            nova = dialogo.obter_categoria_criada()
            if nova is not None:
                self._popular_categorias(selecionar_id=nova.id)

    # ------------------------------------------------------------------
    # Salvar
    # ------------------------------------------------------------------

    def _parse_decimal(self, texto: str, campo: str) -> Decimal | None:
        texto = texto.strip()
        if not texto:
            return None
        try:
            return Decimal(texto.replace(",", "."))
        except (InvalidOperation, ValueError):
            raise ValueError(f"Valor inválido em '{campo}': {texto!r}")

    def _montar_dados(self) -> dict:
        nome = self.txt_nome.text().strip()
        if not nome:
            raise ValueError("Nome é obrigatório.")

        preco_venda = self._parse_decimal(self.txt_preco_venda.text(), "Preço de venda")
        if preco_venda is None:
            raise ValueError("Preço de venda é obrigatório.")

        if self.combo_categoria.currentData() is None:
            raise ValueError("Selecione uma categoria.")

        descricao = self.txt_descricao.toPlainText().strip()
        em_promocao = self.chk_em_promocao.isChecked()

        dados: dict = {
            "nome": nome,
            "descricao": descricao or None,
            "tipo": self.combo_tipo.currentData(),
            "categoria_id": self.combo_categoria.currentData(),
            "controla_estoque": self.chk_controla_estoque.isChecked(),
            "estoque_minimo": self.spin_estoque_minimo.value(),
            "preco_custo": self._parse_decimal(self.txt_preco_custo.text(), "Preço de custo"),
            "preco_venda": preco_venda,
            "permite_desconto": self.chk_permite_desconto.isChecked(),
            "desconto_maximo_percentual": (
                self._parse_decimal(self.txt_desconto_maximo.text(), "Desconto máximo")
                or Decimal("0")
            ),
            "produto_em_promocao": em_promocao,
            "preco_promocional": (
                self._parse_decimal(self.txt_preco_promocional.text(), "Preço promocional")
                if em_promocao
                else None
            ),
            "promocao_inicio": self.date_promo_inicio.date().toPython() if em_promocao else None,
            "promocao_fim": self.date_promo_fim.date().toPython() if em_promocao else None,
            "codigo_barras": self.txt_codigo_barras.text().strip() or None,
            "unidade_medida": self.txt_unidade.text().strip() or "UN",
        }

        # estoque_atual: apenas no modo Criar e somente se preenchido (>0).
        # No modo Editar nunca enviamos — atualizar_produto rejeita o campo.
        if not self._modo_editar:
            inicial = self.spin_estoque_inicial.value()
            if inicial > 0:
                dados["estoque_atual"] = inicial

        return dados

    def _salvar(self) -> None:
        try:
            dados = self._montar_dados()
        except ValueError as e:
            QMessageBox.warning(self, "Dados inválidos", str(e))
            return

        try:
            if self._modo_editar:
                service.atualizar_produto(self._produto_id, dados)
            else:
                service.criar_produto(dados)
        except (
            CategoriaNaoEncontradaError,
            CodigoBarrasDuplicadoError,
            DescontoMaximoForaDoIntervaloError,
            PromocaoInvalidaError,
            ProdutosError,
            ValueError,
        ) as e:
            QMessageBox.warning(self, "Não foi possível salvar", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "Erro", f"Erro inesperado ao salvar: {e}")
            return

        self._produto_salvo = True
        self.accept()

    def produto_salvo(self) -> bool:
        return self._produto_salvo
