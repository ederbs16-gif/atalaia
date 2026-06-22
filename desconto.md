Carregue @CLAUDE.md antes de começar. O módulo Produtos tem modelo, service (com CodigoBarrasDuplicadoError e bloqueio de estoque_atual em atualizar_produto) e tela de listagem prontos e testados (42 passed, 5 skipped). Este prompt cria o formulário de criar/editar Produto e o diálogo rápido de categoria, substituindo os placeholders "Em desenvolvimento" da tela de listagem.

PARTE 1 — Reforço em service.py (antes da UI)

1. Adicione duas exceções em exceptions.py:
   - DescontoMaximoForaDoIntervaloError (desconto_maximo_percentual fora de [0, 100])
   - PromocaoInvalidaError (cobre os dois casos: promocao_fim anterior a promocao_inicio quando ambos preenchidos, ou preco_promocional maior que preco_venda quando preco_promocional preenchido)

2. Em criar_produto e atualizar_produto, antes de tocar na sessão/banco, valide em Python (mesma proatividade já usada para categoria_id e preco_venda):
   - Se desconto_maximo_percentual estiver nos dados e for menor que 0 ou maior que 100: levante DescontoMaximoForaDoIntervaloError
   - Se promocao_inicio e promocao_fim estiverem ambos presentes e promocao_fim < promocao_inicio: levante PromocaoInvalidaError com mensagem específica sobre datas
   - Se preco_promocional estiver presente e for maior que preco_venda (o novo valor sendo definido, ou o existente em caso de atualizar_produto parcial sem preco_venda no dict): levante PromocaoInvalidaError com mensagem específica sobre preço
   Os CHECK constraints do banco continuam existindo e não devem ser removidos; esta validação em Python é a camada que produz mensagem amigável antes de chegar lá.

3. Testes novos em test_service_produto.py para os três casos acima (criar e atualizar), confirmando mensagem específica e que nenhum dado é persistido quando a validação falha.

PARTE 2 — Diálogo de categoria rápida

4. Crie src/atalaia/modules/produtos/ui/dialogo_categoria.py com DialogoCategoria(QDialog): campo de texto "Nome", botões Salvar/Cancelar. Salvar chama service.criar_categoria(nome) (campo obrigatório, sem espaço em branco); em caso de nome duplicado, capture o erro de UNIQUE existente e mostre via QMessageBox.warning sem fechar o diálogo, permitindo corrigir e tentar de novo. Ao salvar com sucesso, feche o diálogo retornando a Categoria criada (via método tipo obter_categoria_criada() ou sinal Qt).

PARTE 3 — Formulário de Produto

5. Crie src/atalaia/modules/produtos/ui/formulario_produto.py com FormularioProduto(QDialog), aceitando um parâmetro opcional produto_id no construtor: None significa modo Criar, um id existente significa modo Editar (carrega os dados atuais via service antes de exibir).

   Campos do formulário, na ordem:
   - Nome (obrigatório)
   - Descrição (opcional, multilinha)
   - Tipo: combo Produto/Serviço. Ao mudar para Serviço, desabilite e desmarque automaticamente o campo Controla Estoque (espelhando a normalização que já existe em criar_produto, para o formulário nunca sugerir visualmente uma combinação que o backend vai silenciosamente corrigir)
   - Categoria: combo populado via listar_categorias(), com botão "+" ao lado abrindo DialogoCategoria; ao criar categoria nova com sucesso, recarregue o combo e selecione automaticamente a categoria recém-criada
   - Controla Estoque: checkbox (desabilitado quando Tipo=Serviço, conforme acima)
   - Estoque Inicial: campo numérico inteiro, visível e editável APENAS no modo Criar. No modo Editar, em vez deste campo, mostre um label somente leitura "Estoque atual: N (use as telas de Entrada de Mercadoria ou PDV para alterar)", já que atualizar_produto rejeita estoque_atual no dict
   - Estoque Mínimo: campo numérico inteiro, sempre editável
   - Preço de Custo: campo decimal, opcional
   - Preço de Venda: campo decimal, obrigatório
   - Permite Desconto: checkbox
   - Desconto Máximo (%): campo numérico decimal 0-100, habilitado apenas quando Permite Desconto estiver marcado
   - Produto em Promoção: checkbox
   - Preço Promocional, Data Início, Data Fim: habilitados apenas quando Produto em Promoção estiver marcado (datas via QDateEdit)
   - Código de Barras: campo de texto, opcional
   - Unidade de Medida: campo de texto, default "UN"

6. Validação no clique de Salvar: monte o dict de dados a partir dos campos (omita estoque_atual no modo Editar, inclua no modo Criar apenas se preenchido) e chame service.criar_produto(dados) ou service.atualizar_produto(produto_id, dados) conforme o modo. Capture cada exceção específica do service (CategoriaNaoEncontradaError, CodigoBarrasDuplicadoError, DescontoMaximoForaDoIntervaloError, PromocaoInvalidaError, e qualquer outra já existente) e mostre via QMessageBox.warning com a mensagem da exceção, sem fechar o formulário, permitindo corrigir o campo problemático. Erros não mapeados continuam indo para QMessageBox.critical como já é o padrão do projeto.

7. Em tela_produtos.py, troque os QMessageBox.information("Em desenvolvimento") dos botões "Novo Produto" e "Editar" por abrir FormularioProduto (sem produto_id para Novo, com o id da linha selecionada para Editar). Ao fechar o formulário com sucesso (produto salvo), recarregue a tabela.

8. Testes em tests/test_formulario_produto.py com pytest-qt (qtbot):
   - smoke test: formulário abre em modo Criar sem erro, combo de categoria populado
   - smoke test: formulário abre em modo Editar com produto existente, campos preenchidos corretamente, campo Estoque Inicial ausente/substituído pelo label read-only
   - alternar Tipo para Serviço desabilita e desmarca Controla Estoque na interface
   - salvar com categoria_id válido e dados corretos persiste o produto e fecha o diálogo
   - salvar com código de barras duplicado mantém o diálogo aberto e exibe a mensagem de erro específica
   - criar categoria via DialogoCategoria a partir do formulário atualiza o combo e seleciona a nova categoria

CRITÉRIOS DE ACEITE
- pytest passa em todos os testes novos e existentes
- Nenhum acesso direto a get_session() em formulario_produto.py ou dialogo_categoria.py, sempre via service.py
- Modo Editar nunca envia estoque_atual no dict para atualizar_produto
- Tipo=Serviço sempre reflete controla_estoque desabilitado e desmarcado na interface, consistente com a normalização do backend

Mostre o plano (estrutura dos dois arquivos novos, assinaturas dos métodos, e as duas exceções novas do service) antes de implementar.