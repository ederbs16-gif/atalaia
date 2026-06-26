"""Testes de ConfigLocal (config.ini)."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from atalaia.config_local import ConfigLocal, _DEFAULTS


@pytest.fixture()
def tmp_cfg(tmp_path) -> ConfigLocal:
    cfg = ConfigLocal(path=tmp_path / "config.ini")
    return cfg


def test_cria_config_ini_com_defaults(tmp_path):
    path = tmp_path / "config.ini"
    assert not path.exists()
    ConfigLocal(path=path)
    assert path.exists()


def test_defaults_presentes(tmp_cfg):
    for section, keys in _DEFAULTS.items():
        for key, expected in keys.items():
            assert tmp_cfg.get(section, key) == expected


def test_get_retorna_fallback_para_chave_inexistente(tmp_cfg):
    assert tmp_cfg.get("interface", "chave_que_nao_existe", "FALLBACK") == "FALLBACK"


def test_set_e_get_roundtrip(tmp_cfg):
    tmp_cfg.set("interface", "fonte_tamanho_geral", "14")
    assert tmp_cfg.get("interface", "fonte_tamanho_geral") == "14"


def test_save_persiste_no_arquivo(tmp_path):
    path = tmp_path / "config.ini"
    cfg = ConfigLocal(path=path)
    cfg.set("interface", "fonte_tamanho_geral", "16")
    cfg.save()

    cfg2 = ConfigLocal(path=path)
    assert cfg2.get("interface", "fonte_tamanho_geral") == "16"


def test_instancia_singleton():
    ConfigLocal._instance = None
    a = ConfigLocal.instancia()
    b = ConfigLocal.instancia()
    assert a is b
    ConfigLocal._instance = None
