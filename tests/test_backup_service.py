"""Testes do backup_service."""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from atalaia.modules.configuracoes import backup_service


# ─── Senha do programador ─────────────────────────────────────────────────────

def test_verificar_senha_incorreta_retorna_false():
    assert backup_service.verificar_senha_programador("senha_errada") is False


def test_verificar_senha_vazia_retorna_false():
    assert backup_service.verificar_senha_programador("") is False


def test_verificar_senha_correta_retorna_true():
    # A senha real lida de variável de ambiente — nunca em texto puro no código.
    senha = os.getenv("PROGRAMADOR_SENHA")
    if senha is None:
        pytest.skip("PROGRAMADOR_SENHA não definida; pule este teste em CI sem segredo configurado.")
    assert backup_service.verificar_senha_programador(senha) is True


# ─── gerar_backup ─────────────────────────────────────────────────────────────

def test_gerar_backup_sem_pasta_configurada_levanta_value_error(tmp_path):
    from atalaia.config_local import ConfigLocal
    cfg_mock = MagicMock()
    cfg_mock.get.side_effect = lambda secao, chave, fallback="": {
        ("backup", "pasta_destino"): "",
        ("sistema", "mysqldump_path"): "tools/mysqldump.exe",
    }.get((secao, chave), fallback)

    with patch.object(ConfigLocal, "instancia", return_value=cfg_mock):
        with pytest.raises(ValueError, match="Pasta de destino"):
            backup_service.gerar_backup()


def test_gerar_backup_mysqldump_inexistente_levanta_file_not_found(tmp_path):
    from atalaia.config_local import ConfigLocal
    caminho_inexistente = str(tmp_path / "nao_existe" / "mysqldump.exe")
    cfg_mock = MagicMock()
    cfg_mock.get.side_effect = lambda secao, chave, fallback="": {
        ("backup", "pasta_destino"): str(tmp_path),
        ("sistema", "mysqldump_path"): caminho_inexistente,
    }.get((secao, chave), fallback)

    with patch.object(ConfigLocal, "instancia", return_value=cfg_mock):
        with pytest.raises(FileNotFoundError, match="mysqldump"):
            backup_service.gerar_backup()
