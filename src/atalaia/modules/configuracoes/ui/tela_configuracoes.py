from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTime
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from atalaia.config_local import ConfigLocal
from atalaia.modules.configuracoes import service as cfg_service
from atalaia.modules.configuracoes.backup_service import (
    gerar_backup,
    restaurar_backup,
    verificar_senha_programador,
)
from atalaia.modules.configuracoes.network_scanner import NetworkScanner

_IDX_SISTEMA = 4


# ─── Utilitários PIX ──────────────────────────────────────────────────────────

def _tlv(field_id: str, value: str) -> str:
    return f"{field_id}{len(value):02d}{value}"


def _crc16_ccitt(data: str) -> str:
    crc = 0xFFFF
    for byte in data.encode("utf-8"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return f"{crc:04X}"


def _gerar_payload_pix(
    chave: str,
    nome: str,
    cidade: str,
    descricao: str = "",
) -> str:
    inner_26 = _tlv("00", "BR.GOV.BCB.PIX") + _tlv("01", chave)
    if descricao:
        inner_26 += _tlv("02", descricao[:72])

    payload = (
        _tlv("00", "01")
        + _tlv("26", inner_26)
        + _tlv("52", "0000")
        + _tlv("53", "986")
        + _tlv("59", nome[:25])
        + _tlv("60", cidade[:15])
        + _tlv("62", _tlv("05", "***"))
        + "6304"
    )
    return payload + _crc16_ccitt(payload)


# ─── TelaConfiguracoes ────────────────────────────────────────────────────────

class TelaConfiguracoes(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._cfg = ConfigLocal.instancia()
        self._aba_anterior = 0
        self._sistema_desbloqueada = False
        self._scanner: NetworkScanner | None = None
        self._build()
        self._carregar_todos()

    def _build(self) -> None:
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        self.tabs = QTabWidget()
        self.tabs.addTab(self._build_empresa(), "🏢 Empresa")
        self.tabs.addTab(self._build_pix(), "💳 PIX")
        self.tabs.addTab(self._build_interface(), "🖥️ Interface")
        self.tabs.addTab(self._build_impressora(), "🖨️ Impressora ESC/POS")
        # Aba Sistema: QStackedWidget com página 0 = placeholder, página 1 = conteúdo real
        self._stack_sistema = QStackedWidget()
        self._stack_sistema.addWidget(self._build_sistema_placeholder())
        self._stack_sistema.addWidget(self._build_sistema())
        self.tabs.addTab(self._stack_sistema, "🔧 Sistema")
        self.tabs.currentChanged.connect(self._on_aba_mudou)
        lay.addWidget(self.tabs)

    def _build_sistema_placeholder(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setAlignment(Qt.AlignCenter)
        lbl = QLabel("🔒  Área protegida por senha do programador")
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet("font-size: 16px; color: #666; margin-bottom: 16px;")
        btn = QPushButton("Autenticar")
        btn.setFixedWidth(160)
        btn.clicked.connect(self._autenticar_sistema)
        lay.addWidget(lbl)
        lay.addWidget(btn, alignment=Qt.AlignCenter)
        return w

    def _autenticar_sistema(self) -> None:
        senha, ok = QInputDialog.getText(
            self, "Acesso Restrito", "Senha do programador:",
            QLineEdit.Password,
        )
        if not ok:
            return
        if not verificar_senha_programador(senha):
            QMessageBox.warning(self, "Acesso negado", "Senha incorreta.")
            return
        self._sistema_desbloqueada = True
        self._stack_sistema.setCurrentIndex(1)

    def _on_aba_mudou(self, index: int) -> None:
        if index == _IDX_SISTEMA and not self._sistema_desbloqueada:
            # Garante que o placeholder está visível (nunca o conteúdo real)
            self._stack_sistema.setCurrentIndex(0)
        self._aba_anterior = index

    # ── Aba 1: Empresa ────────────────────────────────────────────────────────

    def _build_empresa(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self.emp_nome = QLineEdit()
        self.emp_cnpj = QLineEdit()
        self.emp_endereco = QLineEdit()
        self.emp_telefone = QLineEdit()
        self.emp_email = QLineEdit()
        self.emp_site = QLineEdit()

        form.addRow("Nome da empresa *:", self.emp_nome)
        form.addRow("CNPJ:", self.emp_cnpj)
        form.addRow("Endereço:", self.emp_endereco)
        form.addRow("Telefone:", self.emp_telefone)
        form.addRow("E-mail:", self.emp_email)
        form.addRow("Site:", self.emp_site)
        lay.addLayout(form)

        # Logo
        grp_logo = QGroupBox("Logo")
        lay_logo = QHBoxLayout(grp_logo)
        self.emp_logo_path = QLineEdit()
        self.emp_logo_path.setReadOnly(True)
        btn_logo = QPushButton("Selecionar...")
        btn_logo.clicked.connect(self._selecionar_logo)
        self.emp_logo_preview = QLabel()
        self.emp_logo_preview.setFixedSize(200, 100)
        self.emp_logo_preview.setAlignment(Qt.AlignCenter)
        self.emp_logo_preview.setStyleSheet("border: 1px solid #ccc;")
        lay_logo.addWidget(self.emp_logo_path, 1)
        lay_logo.addWidget(btn_logo)
        lay_logo.addWidget(self.emp_logo_preview)
        lay.addWidget(grp_logo)

        btn_salvar = QPushButton("Salvar Dados da Empresa")
        btn_salvar.clicked.connect(self._salvar_empresa)
        lay.addWidget(btn_salvar)
        lay.addStretch()
        return w

    def _selecionar_logo(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Logo", "", "Imagens (*.png *.jpg *.jpeg *.svg)"
        )
        if path:
            self.emp_logo_path.setText(path)
            self._atualizar_preview_logo(path)

    def _atualizar_preview_logo(self, path: str) -> None:
        if path and Path(path).exists():
            px = QPixmap(path).scaled(200, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.emp_logo_preview.setPixmap(px)
        else:
            self.emp_logo_preview.clear()

    def _salvar_empresa(self) -> None:
        nome = self.emp_nome.text().strip()
        if not nome:
            QMessageBox.warning(self, "Campo obrigatório", "Nome da empresa é obrigatório.")
            return
        campos = {
            "nome_empresa": nome,
            "cnpj": self.emp_cnpj.text().strip(),
            "endereco": self.emp_endereco.text().strip(),
            "telefone": self.emp_telefone.text().strip(),
            "email": self.emp_email.text().strip(),
            "site": self.emp_site.text().strip(),
            "logo_path": self.emp_logo_path.text().strip(),
        }
        try:
            for k, v in campos.items():
                cfg_service.set_config(k, v)
            QMessageBox.information(self, "Salvo", "Dados da empresa salvos.")
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))

    # ── Aba 2: PIX ────────────────────────────────────────────────────────────

    def _build_pix(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        form = QFormLayout()
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)

        self.pix_tipo = QComboBox()
        self.pix_tipo.addItems(["CPF", "CNPJ", "Email", "Telefone", "Chave Aleatória"])
        self.pix_chave = QLineEdit()
        self.pix_nome = QLineEdit()
        self.pix_cidade = QLineEdit()
        self.pix_descricao = QLineEdit()

        form.addRow("Tipo de chave:", self.pix_tipo)
        form.addRow("Chave PIX:", self.pix_chave)
        form.addRow("Nome do Recebedor *:", self.pix_nome)
        form.addRow("Cidade *:", self.pix_cidade)
        form.addRow("Descrição (opcional):", self.pix_descricao)
        lay.addLayout(form)

        grp_prev = QGroupBox("Preview do Payload PIX (BR Code)")
        lay_prev = QVBoxLayout(grp_prev)
        self.pix_preview = QLabel("—")
        self.pix_preview.setWordWrap(True)
        self.pix_preview.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.pix_preview.setStyleSheet("font-family: monospace; font-size: 10px;")
        lay_prev.addWidget(self.pix_preview)
        lay.addWidget(grp_prev)

        for field in (self.pix_chave, self.pix_nome, self.pix_cidade, self.pix_descricao):
            field.textChanged.connect(self._atualizar_preview_pix)

        btn_salvar = QPushButton("Salvar PIX")
        btn_salvar.clicked.connect(self._salvar_pix)
        lay.addWidget(btn_salvar)
        lay.addStretch()
        return w

    def _atualizar_preview_pix(self) -> None:
        chave = self.pix_chave.text().strip()
        nome = self.pix_nome.text().strip()
        cidade = self.pix_cidade.text().strip()
        if chave and nome and cidade:
            try:
                payload = _gerar_payload_pix(chave, nome, cidade, self.pix_descricao.text().strip())
                self.pix_preview.setText(payload)
            except Exception as e:
                self.pix_preview.setText(f"Erro: {e}")
        else:
            self.pix_preview.setText("—")

    def _salvar_pix(self) -> None:
        nome = self.pix_nome.text().strip()
        cidade = self.pix_cidade.text().strip()
        if not nome or not cidade:
            QMessageBox.warning(self, "Campos obrigatórios", "Nome do Recebedor e Cidade são obrigatórios.")
            return
        campos = {
            "pix_tipo_chave": self.pix_tipo.currentText(),
            "pix_chave": self.pix_chave.text().strip(),
            "pix_nome_recebedor": nome,
            "pix_cidade": cidade,
            "pix_descricao": self.pix_descricao.text().strip(),
        }
        try:
            for k, v in campos.items():
                cfg_service.set_config(k, v)
            QMessageBox.information(self, "Salvo", "Configurações PIX salvas.")
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))

    # ── Aba 3: Interface ──────────────────────────────────────────────────────

    def _build_interface(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        form = QFormLayout()

        self.iface_fonte_geral = QSpinBox()
        self.iface_fonte_geral.setRange(8, 20)
        self.iface_fonte_pdv = QSpinBox()
        self.iface_fonte_pdv.setRange(10, 24)
        self.iface_fonte_titulo = QSpinBox()
        self.iface_fonte_titulo.setRange(10, 24)
        self.iface_altura_campo = QSpinBox()
        self.iface_altura_campo.setRange(24, 50)

        form.addRow("Fonte geral (px):", self.iface_fonte_geral)
        form.addRow("Fonte PDV (px):", self.iface_fonte_pdv)
        form.addRow("Fonte títulos (px):", self.iface_fonte_titulo)
        form.addRow("Altura mínima de campos (px):", self.iface_altura_campo)
        lay.addLayout(form)

        grp_prev = QGroupBox("Preview ao vivo")
        lay_prev = QVBoxLayout(grp_prev)
        self.iface_prev_label = QLabel("Texto de exemplo — Label")
        self.iface_prev_input = QLineEdit("Texto de exemplo — QLineEdit")
        lay_prev.addWidget(self.iface_prev_label)
        lay_prev.addWidget(self.iface_prev_input)
        lay.addWidget(grp_prev)

        for spin in (self.iface_fonte_geral, self.iface_fonte_pdv,
                     self.iface_fonte_titulo, self.iface_altura_campo):
            spin.valueChanged.connect(self._atualizar_preview_interface)

        btn_salvar = QPushButton("Salvar Interface")
        btn_salvar.clicked.connect(self._salvar_interface)
        lay.addWidget(btn_salvar)
        lay.addStretch()
        return w

    def _atualizar_preview_interface(self) -> None:
        f = self.iface_fonte_geral.value()
        h = self.iface_altura_campo.value()
        self.iface_prev_label.setStyleSheet(f"font-size: {f}px;")
        self.iface_prev_input.setStyleSheet(f"font-size: {f}px; min-height: {h}px;")

    def _salvar_interface(self) -> None:
        self._cfg.set("interface", "fonte_tamanho_geral", str(self.iface_fonte_geral.value()))
        self._cfg.set("interface", "fonte_tamanho_pdv", str(self.iface_fonte_pdv.value()))
        self._cfg.set("interface", "fonte_tamanho_titulo", str(self.iface_fonte_titulo.value()))
        self._cfg.set("interface", "campo_altura_minima", str(self.iface_altura_campo.value()))
        self._cfg.save()
        QMessageBox.information(self, "Salvo", "Configurações de interface salvas.\nReinicie o sistema para aplicar.")

    # ── Aba 4: Impressora ─────────────────────────────────────────────────────

    def _build_impressora(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        form = QFormLayout()

        self.imp_ativada = QCheckBox("Impressora ESC/POS ativada")
        self.imp_porta = QLineEdit()
        self.imp_porta.setPlaceholderText("ex: COM3")
        self.imp_modelo = QComboBox()
        self.imp_modelo.addItems(["EPSON_TM20", "BEMATECH_MP4200", "CUSTOM"])

        self.imp_ativada.toggled.connect(lambda ativo: self.imp_porta.setEnabled(ativo))
        self.imp_ativada.toggled.connect(lambda ativo: self.imp_modelo.setEnabled(ativo))

        form.addRow("", self.imp_ativada)
        form.addRow("Porta:", self.imp_porta)
        form.addRow("Modelo:", self.imp_modelo)
        lay.addLayout(form)

        row = QHBoxLayout()
        btn_testar = QPushButton("Testar")
        btn_testar.clicked.connect(lambda: QMessageBox.information(self, "Impressora", "Teste ESC/POS em desenvolvimento."))
        btn_salvar = QPushButton("Salvar Impressora")
        btn_salvar.clicked.connect(self._salvar_impressora)
        row.addWidget(btn_testar)
        row.addWidget(btn_salvar)
        lay.addLayout(row)
        lay.addStretch()
        return w

    def _salvar_impressora(self) -> None:
        self._cfg.set("impressora", "escpos_ativada", "true" if self.imp_ativada.isChecked() else "false")
        self._cfg.set("impressora", "escpos_porta", self.imp_porta.text().strip())
        self._cfg.set("impressora", "escpos_modelo", self.imp_modelo.currentText())
        self._cfg.save()
        QMessageBox.information(self, "Salvo", "Configurações de impressora salvas.")

    # ── Aba 5: Sistema (protegida) ────────────────────────────────────────────

    def _build_sistema(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)

        # Seção: Conexão com Banco
        grp_banco = QGroupBox("Conexão com Banco")
        form_banco = QFormLayout(grp_banco)
        self.sis_host = QLineEdit()
        self.sis_porta = QSpinBox()
        self.sis_porta.setRange(1, 65535)
        self.sis_porta.setValue(3306)
        self.sis_usuario = QLineEdit()
        self.sis_senha_banco = QLineEdit()
        self.sis_senha_banco.setEchoMode(QLineEdit.Password)

        form_banco.addRow("Host:", self.sis_host)
        form_banco.addRow("Porta:", self.sis_porta)
        form_banco.addRow("Usuário:", self.sis_usuario)
        form_banco.addRow("Senha:", self.sis_senha_banco)

        self._sis_lista_ips = QListWidget()
        self._sis_lista_ips.setMaximumHeight(100)
        self._sis_lista_ips.itemDoubleClicked.connect(
            lambda item: self.sis_host.setText(item.text())
        )

        row_banco = QHBoxLayout()
        btn_scan = QPushButton("Buscar Servidores na Rede")
        btn_scan.clicked.connect(self._buscar_servidores)
        btn_testar_conn = QPushButton("Testar Conexão")
        btn_testar_conn.clicked.connect(self._testar_conexao_banco)
        btn_salvar_conn = QPushButton("Salvar Conexão")
        btn_salvar_conn.clicked.connect(self._salvar_conexao)
        row_banco.addWidget(btn_scan)
        row_banco.addWidget(btn_testar_conn)
        row_banco.addWidget(btn_salvar_conn)

        lay_grp = QVBoxLayout()
        lay_grp.addLayout(form_banco)
        lay_grp.addWidget(QLabel("Servidores encontrados (duplo clique para preencher Host):"))
        lay_grp.addWidget(self._sis_lista_ips)
        lay_grp.addLayout(row_banco)
        grp_banco.setLayout(lay_grp)
        lay.addWidget(grp_banco)

        # Seção: Backup
        grp_backup = QGroupBox("Backup")
        lay_backup = QVBoxLayout(grp_backup)
        form_backup = QFormLayout()
        self.sis_pasta_backup = QLineEdit()
        self.sis_pasta_backup.setReadOnly(True)
        btn_pasta = QPushButton("Selecionar...")
        btn_pasta.clicked.connect(self._selecionar_pasta_backup)
        row_pasta = QHBoxLayout()
        row_pasta.addWidget(self.sis_pasta_backup, 1)
        row_pasta.addWidget(btn_pasta)

        self.sis_backup_auto = QCheckBox("Backup automático")
        self.sis_horario_backup = QTimeEdit(QTime(18, 0))
        self.sis_horario_backup.setDisplayFormat("HH:mm")

        form_backup.addRow("Pasta destino:", row_pasta)
        form_backup.addRow("", self.sis_backup_auto)
        form_backup.addRow("Horário:", self.sis_horario_backup)
        lay_backup.addLayout(form_backup)

        self.sis_lista_backups = QListWidget()
        self.sis_lista_backups.setMaximumHeight(100)
        lay_backup.addWidget(QLabel("Últimos backups:"))
        lay_backup.addWidget(self.sis_lista_backups)

        row_bk = QHBoxLayout()
        btn_backup_agora = QPushButton("Fazer Backup Agora")
        btn_backup_agora.clicked.connect(self._fazer_backup)
        btn_restaurar = QPushButton("Restaurar Backup")
        btn_restaurar.setStyleSheet("background-color: #c0392b; color: white;")
        btn_restaurar.clicked.connect(self._restaurar_backup)
        btn_salvar_backup = QPushButton("Salvar Config. Backup")
        btn_salvar_backup.clicked.connect(self._salvar_backup_config)
        row_bk.addWidget(btn_backup_agora)
        row_bk.addWidget(btn_restaurar)
        row_bk.addWidget(btn_salvar_backup)
        lay_backup.addLayout(row_bk)
        lay.addWidget(grp_backup)

        # Seção: Parâmetros
        grp_params = QGroupBox("Parâmetros do Sistema")
        form_params = QFormLayout(grp_params)
        self.sis_validade_orc = QSpinBox()
        self.sis_validade_orc.setRange(1, 365)
        self.sis_validade_orc.setValue(10)
        self.sis_desconto_max = QSpinBox()
        self.sis_desconto_max.setRange(0, 100)
        self.sis_desconto_max.setValue(100)
        self.sis_caixa_individual = QCheckBox("Caixa individual por PC")
        form_params.addRow("Validade padrão orçamento (dias):", self.sis_validade_orc)
        form_params.addRow("Desconto máximo global (%):", self.sis_desconto_max)
        form_params.addRow("", self.sis_caixa_individual)

        btn_salvar_params = QPushButton("Salvar Parâmetros")
        btn_salvar_params.clicked.connect(self._salvar_params)
        lay_params_v = QVBoxLayout()
        lay_params_v.addLayout(form_params)
        lay_params_v.addWidget(btn_salvar_params)
        grp_params.setLayout(lay_params_v)
        lay.addWidget(grp_params)

        lay.addStretch()
        return w

    def _buscar_servidores(self) -> None:
        dlg = QProgressDialog("Varrendo rede...", "Cancelar", 0, 0, self)
        dlg.setWindowModality(Qt.WindowModal)
        dlg.show()

        self._scanner = NetworkScanner(timeout=0.5, parent=self)

        def _on_resultado(ips: list[str]) -> None:
            dlg.close()
            self._sis_lista_ips.clear()
            if ips:
                self._sis_lista_ips.addItems(ips)
            else:
                self._sis_lista_ips.addItem("Nenhum servidor MySQL encontrado.")

        self._scanner.resultado.connect(_on_resultado)
        dlg.canceled.connect(self._scanner.quit)
        self._scanner.start()

    def _testar_conexao_banco(self) -> None:
        host = self.sis_host.text().strip()
        porta = self.sis_porta.value()
        usuario = self.sis_usuario.text().strip()
        senha = self.sis_senha_banco.text()
        db_name = ""
        try:
            from atalaia import config as db_config
            db_name = db_config.DB_NAME or ""
        except Exception:
            pass
        try:
            import mysql.connector
            conn = mysql.connector.connect(
                host=host, port=porta, user=usuario, password=senha, database=db_name
            )
            conn.close()
            QMessageBox.information(self, "Conexão OK", f"Conectado com sucesso a {host}:{porta}.")
        except Exception as e:
            QMessageBox.critical(self, "Falha na conexão", str(e))

    def _salvar_conexao(self) -> None:
        self._cfg.set("banco", "host", self.sis_host.text().strip())
        self._cfg.set("banco", "porta", str(self.sis_porta.value()))
        self._cfg.set("banco", "usuario", self.sis_usuario.text().strip())
        self._cfg.set("banco", "senha", self.sis_senha_banco.text())
        self._cfg.save()
        QMessageBox.information(self, "Salvo", "Configurações de conexão salvas.\nReinicie o sistema para aplicar.")

    def _selecionar_pasta_backup(self) -> None:
        pasta = QFileDialog.getExistingDirectory(self, "Selecionar Pasta de Backup")
        if pasta:
            self.sis_pasta_backup.setText(pasta)

    def _fazer_backup(self) -> None:
        self._cfg.set("backup", "pasta_destino", self.sis_pasta_backup.text().strip())
        self._cfg.save()
        try:
            caminho = gerar_backup()
            self._atualizar_lista_backups()
            QMessageBox.information(self, "Backup concluído", f"Arquivo gerado:\n{caminho}")
        except Exception as e:
            QMessageBox.critical(self, "Erro no backup", str(e))

    def _restaurar_backup(self) -> None:
        senha, ok = QInputDialog.getText(
            self, "Confirmação", "Senha do programador:", QLineEdit.Password
        )
        if not ok or not verificar_senha_programador(senha):
            if ok:
                QMessageBox.warning(self, "Acesso negado", "Senha incorreta.")
            return

        caminho, _ = QFileDialog.getOpenFileName(
            self, "Selecionar Backup", "", "Backup ZIP (*.zip)"
        )
        if not caminho:
            return

        resp = QMessageBox.warning(
            self, "ATENÇÃO",
            "Esta operação sobrescreve o banco de dados atual com o backup selecionado.\n"
            "Todos os dados atuais serão perdidos.\n\nDeseja continuar?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if resp != QMessageBox.Yes:
            return

        try:
            restaurar_backup(caminho, senha)
            QMessageBox.information(self, "Restaurado", "Backup restaurado com sucesso.")
        except Exception as e:
            QMessageBox.critical(self, "Erro na restauração", str(e))

    def _salvar_backup_config(self) -> None:
        self._cfg.set("backup", "pasta_destino", self.sis_pasta_backup.text().strip())
        self._cfg.set("backup", "backup_automatico", "true" if self.sis_backup_auto.isChecked() else "false")
        t = self.sis_horario_backup.time()
        self._cfg.set("backup", "horario_automatico", f"{t.hour():02d}:{t.minute():02d}")
        self._cfg.save()
        QMessageBox.information(self, "Salvo", "Configurações de backup salvas.")

    def _atualizar_lista_backups(self) -> None:
        self.sis_lista_backups.clear()
        pasta = self.sis_pasta_backup.text().strip()
        if not pasta or not Path(pasta).exists():
            return
        backups = sorted(Path(pasta).glob("atalaia_backup_*.sql.zip"), reverse=True)[:5]
        for b in backups:
            size_kb = b.stat().st_size // 1024
            self.sis_lista_backups.addItem(f"{b.name}  ({size_kb} KB)")

    def _salvar_params(self) -> None:
        try:
            cfg_service.set_config("validade_orcamento_dias", str(self.sis_validade_orc.value()))
            cfg_service.set_config("desconto_maximo_global", str(self.sis_desconto_max.value()))
            cfg_service.set_config("caixa_individual", "true" if self.sis_caixa_individual.isChecked() else "false")
            QMessageBox.information(self, "Salvo", "Parâmetros do sistema salvos.")
        except Exception as e:
            QMessageBox.critical(self, "Erro", str(e))

    # ── Carregamento inicial ──────────────────────────────────────────────────

    def _carregar_todos(self) -> None:
        self._carregar_empresa()
        self._carregar_pix()
        self._carregar_interface()
        self._carregar_impressora()
        self._carregar_sistema()

    def _carregar_empresa(self) -> None:
        try:
            dados = cfg_service.get_configs_empresa()
            self.emp_nome.setText(dados.get("nome_empresa", ""))
            self.emp_cnpj.setText(dados.get("cnpj", ""))
            self.emp_endereco.setText(dados.get("endereco", ""))
            self.emp_telefone.setText(dados.get("telefone", ""))
            self.emp_email.setText(dados.get("email", ""))
            self.emp_site.setText(dados.get("site", ""))
            logo = dados.get("logo_path", "")
            self.emp_logo_path.setText(logo)
            self._atualizar_preview_logo(logo)
        except Exception:
            pass

    def _carregar_pix(self) -> None:
        try:
            dados = cfg_service.get_configs_pix()
            tipo = dados.get("pix_tipo_chave", "")
            idx = self.pix_tipo.findText(tipo)
            if idx >= 0:
                self.pix_tipo.setCurrentIndex(idx)
            self.pix_chave.setText(dados.get("pix_chave", ""))
            self.pix_nome.setText(dados.get("pix_nome_recebedor", ""))
            self.pix_cidade.setText(dados.get("pix_cidade", ""))
            self.pix_descricao.setText(dados.get("pix_descricao", ""))
        except Exception:
            pass

    def _carregar_interface(self) -> None:
        cfg = self._cfg
        self.iface_fonte_geral.setValue(int(cfg.get("interface", "fonte_tamanho_geral", "11")))
        self.iface_fonte_pdv.setValue(int(cfg.get("interface", "fonte_tamanho_pdv", "14")))
        self.iface_fonte_titulo.setValue(int(cfg.get("interface", "fonte_tamanho_titulo", "16")))
        self.iface_altura_campo.setValue(int(cfg.get("interface", "campo_altura_minima", "30")))

    def _carregar_impressora(self) -> None:
        cfg = self._cfg
        ativa = cfg.get("impressora", "escpos_ativada", "false").lower() == "true"
        self.imp_ativada.setChecked(ativa)
        self.imp_porta.setEnabled(ativa)
        self.imp_modelo.setEnabled(ativa)
        self.imp_porta.setText(cfg.get("impressora", "escpos_porta", ""))
        modelo = cfg.get("impressora", "escpos_modelo", "EPSON_TM20")
        idx = self.imp_modelo.findText(modelo)
        if idx >= 0:
            self.imp_modelo.setCurrentIndex(idx)

    def _carregar_sistema(self) -> None:
        cfg = self._cfg
        self.sis_host.setText(cfg.get("banco", "host", "localhost"))
        self.sis_porta.setValue(int(cfg.get("banco", "porta", "3306")))
        self.sis_usuario.setText(cfg.get("banco", "usuario", ""))
        self.sis_senha_banco.setText(cfg.get("banco", "senha", ""))

        pasta = cfg.get("backup", "pasta_destino", "")
        self.sis_pasta_backup.setText(pasta)
        self.sis_backup_auto.setChecked(cfg.get("backup", "backup_automatico", "true").lower() == "true")
        horario = cfg.get("backup", "horario_automatico", "18:00")
        try:
            h, m = (int(x) for x in horario.split(":"))
            self.sis_horario_backup.setTime(QTime(h, m))
        except Exception:
            self.sis_horario_backup.setTime(QTime(18, 0))

        self._atualizar_lista_backups()

        try:
            dados = cfg_service.get_configs_sistema()
            self.sis_validade_orc.setValue(int(dados.get("validade_orcamento_dias", "10")))
            self.sis_desconto_max.setValue(int(dados.get("desconto_maximo_global", "100")))
            self.sis_caixa_individual.setChecked(dados.get("caixa_individual", "false").lower() == "true")
        except Exception:
            pass
