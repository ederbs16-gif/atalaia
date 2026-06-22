Carregue @CLAUDE.md antes de começar, para seguir as convenções já estabelecidas. O módulo Produtos já tem modelo de dados (Categoria, Produto) e camada de serviço (src/atalaia/modules/produtos/service.py) prontos e testados, incluindo: listar_produtos(tipo, categoria_id, apenas_ativos), buscar_por_codigo_barras(codigo), listar_categorias(), obter_preco_vigente(produto, data_referencia).

Este prompt cria a tela de listagem do módulo Produtos. Não cria formulário de criar/editar (isso é o próximo prompt); os botões "Novo Produto" e "Editar" desta tela devem existir na interface mas, por enquanto, abrir um QMessageBox informativo "Em desenvolvimento" ao serem clicados, para a tela já ficar com o layout final sem travar build por causa de uma dependência que ainda não existe.

TAREFA

1. Criar src/atalaia/modules/produtos/ui/__init__.py (pacote vazio) e src/atalaia/modules/produtos/ui/tela_produtos.py com uma classe TelaProdutos(QWidget) contendo:

   Painel de filtros no topo:
   - combo "Tipo": Todos / Produto / Serviço
   - combo "Categoria": populado via listar_categorias(), com opção "Todas" no início
   - combo "Status": Ativos / Inativos / Todos
   - campo de texto "Buscar" (nome ou código de barras)
   - botão "Buscar" (aplica os filtros) e botão "Limpar" (reseta todos os filtros e recarrega lista completa de ativos)

   Tabela de resultados (QTableView + QAbstractTableModel customizado, não QTableWidget, porque esse padrão vai se repetir nos próximos módulos):
   - Colunas: Nome, Tipo, Categoria, Preço de Venda, Preço Vigente, Estoque Atual, Status
   - "Preço Vigente" usa obter_preco_vigente(produto) para cada linha, refletindo promoção ativa quando aplicável; quando o preço vigente for diferente do preço de venda (produto em promoção ativa), destaque visualmente a célula (ex: cor de fundo ou texto diferenciado)
   - Linha de produto inativo visualmente diferenciada (ex: texto acinzentado), para não confundir com ativo na mesma lista quando o filtro Status = Todos

   Botões de ação abaixo ou ao lado da tabela:
   - "Novo Produto": por enquanto QMessageBox.information com "Em desenvolvimento"
   - "Editar" (habilitado só com uma linha selecionada na tabela): por enquanto QMessageBox.information com "Em desenvolvimento"
   - "Inativar" (habilitado só com uma linha selecionada e o produto selecionado estando ativo): chama service.inativar_produto(id) de verdade, pede confirmação via QMessageBox.question antes, e recarrega a tabela após sucesso

2. A busca por texto filtra tanto por nome (contém, case-insensitive) quanto por código de barras (igualdade exata), nessa ordem de tentativa: se o texto bater exatamente com algum código de barras, prioriza esse resultado; senão, filtra por nome. Implemente isso como uma função separada e testável (ex: em produtos/service.py ou produtos/ui/filtros.py, função buscar_produtos_por_termo(termo: str) -> list[Produto]), não direto inline no código do widget, para poder ser testada sem precisar instanciar interface gráfica.

3. A tela nunca abre sessão de banco diretamente nem importa get_session(); toda leitura passa pelas funções de produtos/service.py. Qualquer exceção do service é capturada e exibida via QMessageBox.critical com mensagem amigável, nunca como traceback cru na tela.

4. Adicionar pytest-qt ao requirements.txt como dependência de teste, e criar tests/test_tela_produtos.py com:
   - teste de buscar_produtos_por_termo: termo batendo código de barras exato retorna o produto certo mesmo se o nome não bate; termo parcial de nome retorna produtos correspondentes (case-insensitive); termo sem nenhuma correspondência retorna lista vazia
   - teste de smoke: TelaProdutos consegue ser instanciada sem erro com pytest-qt (fixture qtbot), e o combo de Categoria é populado corretamente a partir de categorias existentes no banco de teste

5. Atualizar CLAUDE.md acrescentando a convenção de UI estabelecida aqui: tela nunca acessa get_session() ou sessão de banco diretamente, sempre via funções de service.py; uso de QTableView + QAbstractTableModel customizado como padrão para listagens (em vez de QTableWidget), para reaproveitar em módulos futuros.

CRITÉRIOS DE ACEITE
- TelaProdutos instancia sem erro e exibe produtos existentes no banco de teste ao carregar.
- Filtros de tipo, categoria, status e busca por nome/código de barras funcionam combinados.
- Preço Vigente reflete corretamente promoção ativa via obter_preco_vigente, com destaque visual quando difere do preço de venda.
- Botão Inativar chama o service de verdade, pede confirmação, e atualiza a lista após sucesso; produto inativado não aparece mais com filtro Status=Ativos.
- Nenhum acesso direto a get_session() ou query SQL dentro de tela_produtos.py.
- pytest passa em todos os testes novos e existentes.

Mostre o plano de estrutura da tela (layout, métodos da classe, função de filtro testável) antes de implementar.