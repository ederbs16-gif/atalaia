from __future__ import annotations

from atalaia.db.session import get_session
from atalaia.db.models.fornecedor import Fornecedor
from atalaia.modules.entrada_mercadorias.exceptions import FornecedorNaoEncontradoError


def buscar_fornecedores_por_termo(
    termo: str, apenas_ativos: bool = True
) -> list[Fornecedor]:
    """Filtra fornecedores por nome OU documento (contém, case-insensitive) via LIKE no banco."""
    with get_session() as session:
        q = session.query(Fornecedor)
        if apenas_ativos:
            q = q.filter(Fornecedor.ativo.is_(True))
        if termo.strip():
            padrao = f"%{termo.strip()}%"
            q = q.filter(
                Fornecedor.nome.ilike(padrao) | Fornecedor.documento.ilike(padrao)
            )
        fornecedores = q.order_by(Fornecedor.nome).all()
        for f in fornecedores:
            session.expunge(f)
        return fornecedores


def criar_fornecedor(dados: dict) -> Fornecedor:
    nome = dados.get("nome", "")
    if not nome or not str(nome).strip():
        raise ValueError("Nome do fornecedor não pode ser vazio.")
    with get_session() as session:
        f = Fornecedor(**dados)
        session.add(f)
        session.flush()
        session.expunge(f)
        return f


def atualizar_fornecedor(fornecedor_id: int, dados: dict) -> Fornecedor:
    with get_session() as session:
        f = session.get(Fornecedor, fornecedor_id)
        if f is None:
            raise FornecedorNaoEncontradoError(
                f"Fornecedor {fornecedor_id} não encontrado."
            )
        for campo, valor in dados.items():
            setattr(f, campo, valor)
        session.flush()
        session.expunge(f)
        return f


def inativar_fornecedor(fornecedor_id: int) -> None:
    with get_session() as session:
        f = session.get(Fornecedor, fornecedor_id)
        if f is None:
            raise FornecedorNaoEncontradoError(
                f"Fornecedor {fornecedor_id} não encontrado."
            )
        f.ativo = False


def listar_fornecedores(apenas_ativos: bool = True) -> list[Fornecedor]:
    with get_session() as session:
        q = session.query(Fornecedor)
        if apenas_ativos:
            q = q.filter(Fornecedor.ativo.is_(True))
        fornecedores = q.order_by(Fornecedor.nome).all()
        for f in fornecedores:
            session.expunge(f)
        return fornecedores


def obter_fornecedor(fornecedor_id: int) -> Fornecedor:
    with get_session() as session:
        f = session.get(Fornecedor, fornecedor_id)
        if f is None:
            raise FornecedorNaoEncontradoError(
                f"Fornecedor {fornecedor_id} não encontrado."
            )
        session.expunge(f)
        return f
