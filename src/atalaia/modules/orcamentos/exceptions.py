class OrcamentosError(Exception):
    pass


class OrcamentoNaoEncontradoError(OrcamentosError):
    pass


class OrcamentoJaFinalizadoError(OrcamentosError):
    pass


class OrcamentoVencidoError(OrcamentosError):
    pass


class EstoqueInsuficienteError(OrcamentosError):
    pass


# Re-exportados para uso no service sem expor dependências cruzadas ao caller
from atalaia.modules.clientes.exceptions import ClienteNaoEncontradoError, ClienteInativoError  # noqa: E402, F401
from atalaia.modules.entrada_mercadorias.exceptions import ProdutoNaoEncontradoError, ProdutoInativoError  # noqa: E402, F401
