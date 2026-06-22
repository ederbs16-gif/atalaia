Carregue @CLAUDE.md antes de começar, para seguir as convenções já estabelecidas. Os modelos Categoria e Produto já existem em produção (migration 150ecb145dad aplicada), com os 5 CHECK constraints, ENUM de tipo, e os campos de estoque, desconto e promoção já no banco.

Este prompt cria a camada de regras de negócio do módulo Produtos (src/atalaia/modules/produtos/service.py), entre o modelo de dados e a futura tela PySide6. Nenhuma UI é criada aqui.

TAREFA

1. Criar exceções customizadas em src/atalaia/modules/produtos/exceptions.py:
   - EstoqueInsuficienteError
   - ProdutoInativoError
   - DescontoNaoPermitidoError (produto com permite_desconto=False)
   - DescontoExcedeLimiteError (percentual solicitado maior que desconto_maximo_percentual)
   - CategoriaNaoEncontradaError

2. Em src/atalaia/modules/produtos/service.py, criar as seguintes funções, todas recebendo a sessão via get_session() (já existente em db/session.py):

   - criar_categoria(nome: str) -> Categoria: valida nome não vazio, propaga erro de UNIQUE de forma clara se a categoria já existir.

   - listar_categorias() -> list[Categoria]

   - criar_produto(dados: dict) -> Produto: valida categoria_id existente (levanta CategoriaNaoEncontradaError se não existir), valida preco_venda >= 0, valida que se tipo='servico' então controla_estoque deve vir False (servico nunca controla estoque; se vier True com tipo servico, force False e não levante erro, é uma normalização razoável, mas documente essa decisão no docstring da função).

   - atualizar_produto(produto_id: int, dados: dict) -> Produto: atualiza campos parciais, mesmas validações de criar_produto para os campos presentes.

   - inativar_produto(produto_id: int) -> None: soft delete, seta ativo=False. Nunca remove a linha fisicamente.

   - listar_produtos(tipo: str | None = None, categoria_id: int | None = None, apenas_ativos: bool = True) -> list[Produto]: filtros opcionais combináveis.

   - buscar_por_codigo_barras(codigo: str) -> Produto | None

   - dar_baixa_estoque(produto_id: int, quantidade: int) -> None: CRÍTICO, deve usar UPDATE atômico no banco, não leitura seguida de escrita em Python. Use a forma:
   UPDATE produtos SET estoque_atual = estoque_atual - :qtd
 WHERE id = :id AND controla_estoque = TRUE AND estoque_atual >= :qtd
 Verifique o rowcount do resultado. Se for 0, levante EstoqueInsuficienteError (a mensagem deve deixar claro se a causa foi estoque insuficiente ou produto não controla estoque, consultando o produto separadamente só para compor a mensagem de erro, não para decidir o fluxo). Se o produto tiver controla_estoque=False (caso de serviço), a função deve simplesmente não fazer nada e retornar, sem erro: isso evita que PDV e Orçamento precisem checar o tipo do produto antes de chamar essa função, a checagem fica centralizada aqui.

   - dar_entrada_estoque(produto_id: int, quantidade: int) -> None: mesma lógica de UPDATE atômico, mas somando. Se controla_estoque=False, não faz nada (mesma razão).

   - obter_preco_vigente(produto: Produto, data_referencia: date | None = None) -> Decimal: se data_referencia for None, usa date.today(). Retorna preco_promocional se produto_em_promocao=True e data_referencia estiver entre promocao_inicio e promocao_fim (inclusive nas duas pontas); caso contrário, retorna preco_venda.

   - validar_desconto(produto: Produto, percentual_solicitado: Decimal) -> None: levanta DescontoNaoPermitidoError se permite_desconto=False e percentual_solicitado > 0; levanta DescontoExcedeLimiteError se percentual_solicitado > desconto_maximo_percentual. Não retorna valor, só valida (levanta exceção ou não faz nada).

3. Criar tests/test_service_produto.py cobrindo, no mínimo:
   - criar_produto válido, tipo produto e tipo servico
   - criar_produto com categoria_id inexistente levanta CategoriaNaoEncontradaError
   - criar_produto tipo servico com controla_estoque=True na entrada é normalizado para False
   - dar_baixa_estoque com estoque suficiente reduz corretamente
   - dar_baixa_estoque com estoque insuficiente levanta EstoqueInsuficienteError e não altera o valor no banco
   - dar_baixa_estoque em produto com controla_estoque=False não altera nada e não levanta erro
   - simulação de concorrência: dentro do teste, com estoque_atual=2, execute duas chamadas sequenciais de dar_baixa_estoque(produto_id, 2) sem recarregar o objeto Produto em memória entre as chamadas (simulando duas "sessões" lendo o mesmo estado inicial); a segunda chamada deve levantar EstoqueInsuficienteError, comprovando que o UPDATE atômico impede a venda dupla mesmo sem re-leitura do objeto em Python
   - obter_preco_vigente: produto em promoção dentro do período retorna preco_promocional; fora do período (antes do início ou depois do fim) retorna preco_venda; produto_em_promocao=False sempre retorna preco_venda mesmo com datas preenchidas
   - validar_desconto: percentual dentro do limite passa sem erro; percentual acima do limite levanta DescontoExcedeLimiteError; produto com permite_desconto=False e percentual > 0 levanta DescontoNaoPermitidoError; percentual=0 nunca levanta erro mesmo com permite_desconto=False
   - inativar_produto seta ativo=False e listar_produtos(apenas_ativos=True) não retorna mais o produto

4. Atualizar CLAUDE.md acrescentando uma seção curta sobre o padrão de atualização atômica de estoque (UPDATE com WHERE condicional + checagem de rowcount, nunca leitura seguida de escrita), porque esse padrão vai se repetir em Entrada de Mercadorias e PDV.

CRITÉRIOS DE ACEITE
- dar_baixa_estoque e dar_entrada_estoque usam UPDATE atômico via SQL, comprovável lendo o código (não fazem SELECT seguido de UPDATE calculado em Python).
- pytest passa em todos os testes novos e nos já existentes, incluindo o teste de simulação de concorrência.
- Nenhuma função desta camada faz exclusão física de Produto ou Categoria.
- CLAUDE.md atualizado com o padrão de atualização atômica de estoque.

Mostre o plano de funções e assinaturas antes de implementar.