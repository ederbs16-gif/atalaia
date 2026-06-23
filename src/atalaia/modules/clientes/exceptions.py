class ClientesError(Exception):
    pass


class ClienteNaoEncontradoError(ClientesError):
    pass


class ClienteInativoError(ClientesError):
    pass
