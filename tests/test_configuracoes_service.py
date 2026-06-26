"""Testes do service de configurações da empresa (banco MySQL)."""
from __future__ import annotations

from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from atalaia.db.base import Base
import atalaia.db.models  # noqa: F401 — registra todos os models

from atalaia.modules.configuracoes import service as cfg_service


@pytest.fixture(scope="module")
def engine():
    e = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(e)
    yield e
    Base.metadata.drop_all(e)
    e.dispose()


@pytest.fixture(autouse=True)
def patch_session(engine, monkeypatch):
    SM = sessionmaker(bind=engine, autocommit=False, autoflush=False)

    @contextmanager
    def _session():
        s = SM()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    monkeypatch.setattr(cfg_service, "get_session", _session)
    yield

    from sqlalchemy import text
    with SM() as s:
        s.execute(text("DELETE FROM configuracoes"))
        s.commit()


def test_set_config_e_get_config():
    cfg_service.set_config("chave_teste", "valor_x")
    assert cfg_service.get_config("chave_teste") == "valor_x"


def test_get_config_retorna_default_para_chave_ausente():
    assert cfg_service.get_config("chave_inexistente", "PADRAO") == "PADRAO"


def test_set_config_upsert():
    cfg_service.set_config("chave_upsert", "v1")
    cfg_service.set_config("chave_upsert", "v2")
    assert cfg_service.get_config("chave_upsert") == "v2"


def test_inicializar_configs_padrao_cria_chaves():
    cfg_service.inicializar_configs_padrao()
    assert cfg_service.get_config("nome_empresa") == ""
    assert cfg_service.get_config("validade_orcamento_dias") == "10"
    assert cfg_service.get_config("caixa_individual") == "false"
    assert cfg_service.get_config("desconto_maximo_global") == "100"


def test_inicializar_configs_padrao_idempotente():
    cfg_service.set_config("nome_empresa", "Minha Loja")
    cfg_service.inicializar_configs_padrao()
    assert cfg_service.get_config("nome_empresa") == "Minha Loja"


def test_get_configs_pix_retorna_todas_as_chaves():
    cfg_service.inicializar_configs_padrao()
    dados = cfg_service.get_configs_pix()
    assert set(dados.keys()) == {
        "pix_tipo_chave", "pix_chave", "pix_nome_recebedor",
        "pix_cidade", "pix_descricao",
    }


def test_get_configs_empresa_retorna_todas_as_chaves():
    cfg_service.inicializar_configs_padrao()
    dados = cfg_service.get_configs_empresa()
    assert "nome_empresa" in dados
    assert "cnpj" in dados
    assert "logo_path" in dados
