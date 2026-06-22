class ProdutosError(Exception):
    """Base para todas as exceções do módulo de produtos."""


class EstoqueInsuficienteError(ProdutosError):
    """Estoque disponível menor que a quantidade solicitada."""


class ProdutoInativoError(ProdutosError):
    """Operação não permitida em produto inativo."""


class DescontoNaoPermitidoError(ProdutosError):
    """Produto não permite desconto (permite_desconto=False)."""


class DescontoExcedeLimiteError(ProdutosError):
    """Percentual de desconto solicitado supera desconto_maximo_percentual."""


class CategoriaNaoEncontradaError(ProdutosError):
    """Categoria referenciada não existe no banco."""


class CodigoBarrasDuplicadoError(ProdutosError):
    """Código de barras já está em uso por outro produto."""


class DescontoMaximoForaDoIntervaloError(ProdutosError):
    """desconto_maximo_percentual fora do intervalo [0, 100]."""


class PromocaoInvalidaError(ProdutosError):
    """Promoção inconsistente: datas invertidas ou preço promocional acima do preço de venda."""
