from __future__ import annotations

from sqlalchemy import select

from atalaia.db.models.configuracao import Configuracao
from atalaia.db.session import get_session

_PADRAO_EMPRESA = {
    "nome_empresa": "",
    "cnpj": "",
    "endereco": "",
    "telefone": "",
    "email": "",
    "site": "",
    "logo_path": "",
}

_PADRAO_PIX = {
    "pix_tipo_chave": "",
    "pix_chave": "",
    "pix_nome_recebedor": "",
    "pix_cidade": "",
    "pix_descricao": "",
}

_PADRAO_SISTEMA = {
    "validade_orcamento_dias": "10",
    "caixa_individual": "false",
    "desconto_maximo_global": "100",
}


def _get_obj(session, chave: str) -> Configuracao | None:
    return session.execute(
        select(Configuracao).where(Configuracao.chave == chave)
    ).scalar_one_or_none()


def get_config(chave: str, default: str = "") -> str:
    with get_session() as session:
        obj = _get_obj(session, chave)
        return obj.valor if obj else default


def set_config(chave: str, valor: str) -> None:
    with get_session() as session:
        obj = _get_obj(session, chave)
        if obj is None:
            session.add(Configuracao(chave=chave, valor=valor))
        else:
            obj.valor = valor


def get_configs_empresa() -> dict:
    return {k: get_config(k) for k in _PADRAO_EMPRESA}


def get_configs_pix() -> dict:
    return {k: get_config(k) for k in _PADRAO_PIX}


def get_configs_sistema() -> dict:
    return {k: get_config(k) for k in _PADRAO_SISTEMA}


def inicializar_configs_padrao() -> None:
    todos = {**_PADRAO_EMPRESA, **_PADRAO_PIX, **_PADRAO_SISTEMA}
    with get_session() as session:
        for chave, valor in todos.items():
            if _get_obj(session, chave) is None:
                session.add(Configuracao(chave=chave, valor=valor))
