Carregue @CLAUDE.md antes de começar. O módulo Produtos já tem modelo, service e tela de listagem prontos e testados (39 passed, 5 skipped). Este prompt endurece service.py antes de construir o formulário de criar/editar, que vai expor dois casos ainda não tratados.

TAREFA

1. Adicione CodigoBarrasDuplicadoError em exceptions.py.

2. Em criar_produto e atualizar_produto, capture IntegrityError do SQLAlchemy ao fazer commit. Se a violação for da constraint única de codigo_barras (nome da constraint segue a naming_convention já definida em db/base.py, algo como uq_produtos_codigo_barras; inspecione a mensagem de erro ou o nome da constraint para identificar isso especificamente), re-levante como CodigoBarrasDuplicadoError com mensagem clara incluindo o valor de codigo_barras que causou o conflito. Qualquer outro IntegrityError não identificado continua propagando normalmente (não esconda erro não mapeado atrás de uma mensagem genérica errada).

3. Em atualizar_produto, se o dict de dados recebido contiver a chave estoque_atual, levante um erro explícito (ex: ValueError com mensagem clara) em vez de ignorar silenciosamente ou aplicar o valor. Documente no docstring da função: alteração de estoque_atual deve sempre passar por dar_baixa_estoque ou dar_entrada_estoque, nunca por atualização direta de campo, mesmo nesta camada de service; isso é reforço estrutural para o caso de a tela (ou qualquer chamador futuro) tentar enviar esse campo por engano.

4. Adicione testes em test_service_produto.py:
   - criar_produto com codigo_barras já usado por outro produto levanta CodigoBarrasDuplicadoError com mensagem mencionando o código
   - atualizar_produto mudando codigo_barras para um valor já usado por outro produto levanta o mesmo erro
   - atualizar_produto chamado com "estoque_atual" no dict de dados levanta ValueError e não altera o valor no banco (confirme lendo o produto depois da tentativa)

CRITÉRIOS DE ACEITE
- pytest passa em todos os testes novos e existentes
- Nenhuma mudança de comportamento nos outros casos já cobertos (CategoriaNaoEncontradaError, validações de desconto, normalização de tipo servico)

Mostre o plano antes de implementar.