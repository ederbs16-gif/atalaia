"""Smoke tests da UI de Configurações."""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from atalaia.modules.configuracoes import service as cfg_service


@pytest.fixture(autouse=True)
def patch_services(monkeypatch):
    """Isola testes de UI do banco e do config.ini."""
    monkeypatch.setattr(cfg_service, "get_config", lambda chave, default="": default)
    monkeypatch.setattr(cfg_service, "set_config", lambda chave, valor: None)
    monkeypatch.setattr(cfg_service, "get_configs_empresa", lambda: {
        "nome_empresa": "", "cnpj": "", "endereco": "",
        "telefone": "", "email": "", "site": "", "logo_path": "",
    })
    monkeypatch.setattr(cfg_service, "get_configs_pix", lambda: {
        "pix_tipo_chave": "", "pix_chave": "", "pix_nome_recebedor": "",
        "pix_cidade": "", "pix_descricao": "",
    })
    monkeypatch.setattr(cfg_service, "get_configs_sistema", lambda: {
        "validade_orcamento_dias": "10",
        "caixa_individual": "false",
        "desconto_maximo_global": "100",
    })

    from atalaia.config_local import ConfigLocal
    cfg_mock = MagicMock()
    cfg_mock.get.side_effect = lambda secao, chave, fallback="": {
        ("interface", "fonte_tamanho_geral"): "11",
        ("interface", "fonte_tamanho_pdv"): "14",
        ("interface", "fonte_tamanho_titulo"): "16",
        ("interface", "campo_altura_minima"): "30",
        ("impressora", "escpos_ativada"): "false",
        ("impressora", "escpos_porta"): "",
        ("impressora", "escpos_modelo"): "EPSON_TM20",
        ("banco", "host"): "localhost",
        ("banco", "porta"): "3306",
        ("banco", "usuario"): "",
        ("banco", "senha"): "",
        ("backup", "pasta_destino"): "",
        ("backup", "backup_automatico"): "true",
        ("backup", "horario_automatico"): "18:00",
    }.get((secao, chave), fallback)

    monkeypatch.setattr(ConfigLocal, "instancia", lambda: cfg_mock)


def test_smoke_tela_configuracoes_instancia(qtbot):
    from atalaia.modules.configuracoes.ui.tela_configuracoes import TelaConfiguracoes
    w = TelaConfiguracoes()
    qtbot.addWidget(w)
    assert w is not None


def test_smoke_cinco_abas(qtbot):
    from atalaia.modules.configuracoes.ui.tela_configuracoes import TelaConfiguracoes
    w = TelaConfiguracoes()
    qtbot.addWidget(w)
    assert w.tabs.count() == 5


def test_smoke_aba_empresa_campos_carregados(qtbot):
    from atalaia.modules.configuracoes.ui.tela_configuracoes import TelaConfiguracoes
    w = TelaConfiguracoes()
    qtbot.addWidget(w)
    w.tabs.setCurrentIndex(0)
    # campos devem existir e ser QLineEdit
    from PySide6.QtWidgets import QLineEdit
    assert isinstance(w.emp_nome, QLineEdit)
    assert isinstance(w.emp_cnpj, QLineEdit)


def test_aba_sistema_mostra_placeholder_sem_senha(qtbot):
    from atalaia.modules.configuracoes.ui.tela_configuracoes import TelaConfiguracoes
    w = TelaConfiguracoes()
    qtbot.addWidget(w)

    # Sem autenticação: placeholder (índice 0) deve estar visível
    w.tabs.setCurrentIndex(4)
    assert w._stack_sistema.currentIndex() == 0
    assert not w._sistema_desbloqueada


def test_aba_sistema_exibe_conteudo_apos_autenticacao(qtbot, monkeypatch):
    import atalaia.modules.configuracoes.ui.tela_configuracoes as mod
    from atalaia.modules.configuracoes.ui.tela_configuracoes import TelaConfiguracoes

    monkeypatch.setattr(mod, "verificar_senha_programador", lambda s: True)
    monkeypatch.setattr(mod.QInputDialog, "getText", staticmethod(lambda *a, **kw: ("qualquer", True)))

    w = TelaConfiguracoes()
    qtbot.addWidget(w)
    w.tabs.setCurrentIndex(4)
    w._autenticar_sistema()

    assert w._sistema_desbloqueada
    assert w._stack_sistema.currentIndex() == 1
