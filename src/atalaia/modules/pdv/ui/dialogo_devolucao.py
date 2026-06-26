from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from atalaia.modules.pdv import venda_service
from atalaia.modules.pdv.exceptions import VendaNaoEncontradaError, VendaJaFinalizadaError, DevolucaoInvalidaError
from atalaia.modules.produtos.service import buscar_produtos_por_termo


class DialogoDevolucao(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Registrar Devolução")
        self.setMinimumSize(600, 500)
        self._venda = None
        self._item_widgets: list[dict] = []
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        row_busca = QHBoxLayout()
        row_busca.addWidget(QLabel("ID da Venda:"))
        self.spin_venda_id = QSpinBox()
        self.spin_venda_id.setMinimum(1)
        self.spin_venda_id.setMaximum(999999)
        row_busca.addWidget(self.spin_venda_id)
        btn_buscar = QPushButton("Buscar")
        btn_buscar.clicked.connect(self._buscar_venda)
        row_busca.addWidget(btn_buscar)
        row_busca.addStretch()
        layout.addLayout(row_busca)

        self.lbl_venda = QLabel("Nenhuma venda carregada.")
        layout.addWidget(self.lbl_venda)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.area_itens = QWidget()
        self.layout_itens = QVBoxLayout(self.area_itens)
        scroll.setWidget(self.area_itens)
        layout.addWidget(scroll)

        form = QFormLayout()
        self.combo_tipo = QComboBox()
        self.combo_tipo.addItems(["Reembolso", "Troca"])
        self.combo_tipo.currentTextChanged.connect(self._on_tipo_mudou)
        form.addRow("Tipo:", self.combo_tipo)

        self.txt_motivo = QPlainTextEdit()
        self.txt_motivo.setMaximumHeight(80)
        self.txt_motivo.setPlaceholderText("Motivo da devolução (obrigatório)")
        form.addRow("Motivo:", self.txt_motivo)

        self.lbl_forma = QLabel("Forma de reembolso:")
        self.combo_forma = QComboBox()
        self.combo_forma.addItems(["dinheiro", "pix", "debito", "credito"])
        form.addRow(self.lbl_forma, self.combo_forma)

        layout.addLayout(form)

        buttons = QDialogButtonBox()
        self.btn_registrar = buttons.addButton("Registrar Devolução", QDialogButtonBox.AcceptRole)
        buttons.addButton(QDialogButtonBox.Cancel)
        self.btn_registrar.setEnabled(False)
        self.btn_registrar.clicked.connect(self._registrar)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _buscar_venda(self) -> None:
        venda_id = self.spin_venda_id.value()
        try:
            self._venda = venda_service.obter_venda(venda_id)
        except VendaNaoEncontradaError as e:
            QMessageBox.warning(self, "Não encontrada", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return

        if self._venda.status.value != "finalizada":
            QMessageBox.warning(self, "Atenção", "Devoluções só são permitidas em vendas finalizadas.")
            self._venda = None
            return

        self.lbl_venda.setText(
            f"Venda #{self._venda.id} | "
            f"Cliente: {self._venda.cliente.nome if self._venda.cliente else 'Anônimo'} | "
            f"Total: R$ {self._venda.total:.2f}"
        )
        self._popular_itens()
        self.btn_registrar.setEnabled(True)

    def _popular_itens(self) -> None:
        while self.layout_itens.count():
            child = self.layout_itens.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._item_widgets = []

        for item in self._venda.itens:
            grp = QGroupBox(f"{item.produto.nome} — Qtd comprada: {item.quantidade}")
            form = QFormLayout(grp)

            chk = QCheckBox("Devolver")
            spin_qtd = QSpinBox()
            spin_qtd.setMinimum(1)
            spin_qtd.setMaximum(item.quantidade)
            spin_qtd.setValue(1)
            spin_qtd.setEnabled(False)
            chk.toggled.connect(spin_qtd.setEnabled)

            lbl_sub = QLabel("Produto substituto (troca):")
            txt_sub = QPushButton("Buscar produto substituto...")
            txt_sub.setEnabled(False)
            txt_sub.setProperty("produto_sub_id", None)
            txt_sub.clicked.connect(lambda checked, b=txt_sub: self._buscar_substituto(b))
            lbl_sub.setVisible(False)
            txt_sub.setVisible(False)

            form.addRow(chk, spin_qtd)
            form.addRow(lbl_sub, txt_sub)

            self.layout_itens.addWidget(grp)
            self._item_widgets.append({
                "produto_id": item.produto_id,
                "chk": chk,
                "spin_qtd": spin_qtd,
                "lbl_sub": lbl_sub,
                "btn_sub": txt_sub,
            })

        self.layout_itens.addStretch()
        self._on_tipo_mudou(self.combo_tipo.currentText())

    def _on_tipo_mudou(self, tipo: str) -> None:
        eh_troca = tipo == "Troca"
        self.lbl_forma.setVisible(not eh_troca)
        self.combo_forma.setVisible(not eh_troca)
        for w in self._item_widgets:
            w["lbl_sub"].setVisible(eh_troca)
            w["btn_sub"].setVisible(eh_troca)
            w["btn_sub"].setEnabled(eh_troca and w["chk"].isChecked())
            w["chk"].toggled.connect(
                lambda checked, b=w["btn_sub"]: b.setEnabled(checked and eh_troca)
            )

    def _buscar_substituto(self, btn: QPushButton) -> None:
        from PySide6.QtWidgets import QInputDialog
        termo, ok = QInputDialog.getText(self, "Buscar produto", "Nome ou código de barras:")
        if not ok or not termo.strip():
            return
        try:
            produtos = buscar_produtos_por_termo(termo.strip(), apenas_ativos=True)
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return
        if not produtos:
            QMessageBox.information(self, "Não encontrado", "Nenhum produto encontrado.")
            return
        if len(produtos) == 1:
            prod = produtos[0]
        else:
            from PySide6.QtWidgets import QInputDialog
            nomes = [f"{p.nome} ({p.codigo_barras or '—'})" for p in produtos]
            escolha, ok2 = QInputDialog.getItem(self, "Selecionar produto", "Produto:", nomes, 0, False)
            if not ok2:
                return
            idx = nomes.index(escolha)
            prod = produtos[idx]
        btn.setText(f"{prod.nome}")
        btn.setProperty("produto_sub_id", prod.id)

    def _registrar(self) -> None:
        if self._venda is None:
            return
        motivo = self.txt_motivo.toPlainText().strip()
        if not motivo:
            QMessageBox.warning(self, "Atenção", "Informe o motivo da devolução.")
            return

        itens_dev = []
        tipo = "troca" if self.combo_tipo.currentText() == "Troca" else "reembolso"

        for w in self._item_widgets:
            if not w["chk"].isChecked():
                continue
            item = {"produto_id": w["produto_id"], "quantidade": w["spin_qtd"].value()}
            if tipo == "troca":
                sub_id = w["btn_sub"].property("produto_sub_id")
                if sub_id is None:
                    QMessageBox.warning(self, "Atenção", "Selecione o produto substituto para todos os itens de troca.")
                    return
                item["produto_substituto_id"] = sub_id
            itens_dev.append(item)

        if not itens_dev:
            QMessageBox.warning(self, "Atenção", "Selecione ao menos um item para devolver.")
            return

        forma_reembolso = self.combo_forma.currentText() if tipo == "reembolso" else None

        try:
            venda_service.registrar_devolucao(
                self._venda.id, itens_dev, tipo, motivo, forma_reembolso
            )
        except (DevolucaoInvalidaError, VendaJaFinalizadaError) as e:
            QMessageBox.warning(self, "Erro na devolução", str(e))
            return
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))
            return

        QMessageBox.information(self, "Sucesso", "Devolução registrada com sucesso.")
        self.accept()
