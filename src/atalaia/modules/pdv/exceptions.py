from __future__ import annotations


class PDVError(Exception):
    pass


class VendaNaoEncontradaError(PDVError):
    pass


class VendaJaFinalizadaError(PDVError):
    pass


class PagamentoInsuficienteError(PDVError):
    pass


class DescontoInvalidoError(PDVError):
    pass


class DevolucaoInvalidaError(PDVError):
    pass
