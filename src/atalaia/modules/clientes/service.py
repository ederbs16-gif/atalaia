from __future__ import annotations

from atalaia.db.session import get_session
from atalaia.db.models.cliente import Cliente
from atalaia.modules.clientes.exceptions import ClienteNaoEncontradoError


def criar_cliente(dados: dict) -> Cliente:
    nome = dados.get("nome", "")
    if not nome or not str(nome).strip():
        raise ValueError("Nome do cliente não pode ser vazio.")
    with get_session() as session:
        c = Cliente(**dados)
        session.add(c)
        session.flush()
        session.expunge(c)
        return c


def atualizar_cliente(cliente_id: int, dados: dict) -> Cliente:
    with get_session() as session:
        c = session.get(Cliente, cliente_id)
        if c is None:
            raise ClienteNaoEncontradoError(f"Cliente {cliente_id} não encontrado.")
        for campo, valor in dados.items():
            setattr(c, campo, valor)
        session.flush()
        session.expunge(c)
        return c


def inativar_cliente(cliente_id: int) -> None:
    with get_session() as session:
        c = session.get(Cliente, cliente_id)
        if c is None:
            raise ClienteNaoEncontradoError(f"Cliente {cliente_id} não encontrado.")
        c.ativo = False


def listar_clientes(apenas_ativos: bool = True) -> list[Cliente]:
    with get_session() as session:
        q = session.query(Cliente)
        if apenas_ativos:
            q = q.filter(Cliente.ativo.is_(True))
        clientes = q.order_by(Cliente.nome).all()
        for c in clientes:
            session.expunge(c)
        return clientes


def obter_cliente(cliente_id: int) -> Cliente:
    with get_session() as session:
        c = session.get(Cliente, cliente_id)
        if c is None:
            raise ClienteNaoEncontradoError(f"Cliente {cliente_id} não encontrado.")
        session.expunge(c)
        return c


def buscar_clientes_por_termo(termo: str, apenas_ativos: bool = True) -> list[Cliente]:
    """Filtra clientes por nome OU documento (contém, case-insensitive) via LIKE no banco."""
    with get_session() as session:
        q = session.query(Cliente)
        if apenas_ativos:
            q = q.filter(Cliente.ativo.is_(True))
        if termo.strip():
            padrao = f"%{termo.strip()}%"
            q = q.filter(
                Cliente.nome.ilike(padrao) | Cliente.documento.ilike(padrao)
            )
        clientes = q.order_by(Cliente.nome).all()
        for c in clientes:
            session.expunge(c)
        return clientes
