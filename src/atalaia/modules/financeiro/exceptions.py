class FinanceiroError(Exception):
    pass

class CaixaJaAbertoError(FinanceiroError):
    pass

class CaixaNaoAbertoError(FinanceiroError):
    pass

class CaixaJaFechadoError(FinanceiroError):
    pass

class ContaNaoEncontradaError(FinanceiroError):
    pass

class ContaJaPagaError(FinanceiroError):
    pass

class PagamentoExcedeValorError(FinanceiroError):
    pass
