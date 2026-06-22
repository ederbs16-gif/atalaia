class EntradaMercadoriasError(Exception):
    """Base para todas as exceções do módulo de Entrada de Mercadorias."""


class FornecedorNaoEncontradoError(EntradaMercadoriasError):
    """Fornecedor com o id solicitado não existe no banco."""


class FornecedorInativoError(EntradaMercadoriasError):
    """Tentativa de usar um fornecedor inativo numa entrada nova."""


class EntradaJaConfirmadaError(EntradaMercadoriasError):
    """Operação de escrita tentada em uma entrada já confirmada."""


class ProdutoNaoEncontradoError(EntradaMercadoriasError):
    """Produto com o id solicitado não existe no banco."""


class ProdutoInativoError(EntradaMercadoriasError):
    """Tentativa de adicionar um produto inativo a uma entrada."""
