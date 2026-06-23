Carregue @CLAUDE.md antes de começar. Este prompt cria o módulo Orçamentos completo (model + service + UI com visualização). Clientes já existem (tabela clientes, migration 876359399b80). Impressão via QPrinter será implementada em prompt futuro junto com Relatórios.

CONTEXTO DE NEGÓCIO
- Orçamento tem status: Aberto → Aprovado → Recusado
- Orçamento aprovado converte automaticamente em venda (tabela vendas, criada neste prompt como schema base para o PDV)
- Validade padrão vem da tabela configuracoes (chave 'validade_orcamento_dias', default '10'); editável por orçamento individual
- Número sequencial formatado: ORC-0001, ORC-0002 (campo numero INT autoincrement, formatado na exibição)
- Desconto: global sobre o total (um percentual só)
- Preço dos itens: usa obter_preco_vigente() do produtos/service.py (respeita promoção ativa por data)

PARTE 1 — Models e migration

1. Criar src/atalaia/db/models/orcamento.py com dois modelos:

   Orcamento (tabela orcamentos):
   - id: INT, PK, autoincrement
   - numero: INT, NOT NULL, UNIQUE, autoincrement (usado para gerar ORC-0001)
   - cliente_id: INT, NOT NULL, FK para clientes.id
   - status: ENUM('aberto', 'aprovado', 'recusado'), NOT NULL, default 'aberto'
   - validade_dias: INT, NOT NULL, default 10
   - data_criacao: DATE, NOT NULL, server_default=func.current_date() via Python (mesmo padrão de entrada_mercadoria, MySQL 5.7 não suporta DEFAULT CURRENT_DATE)
   - data_validade: DATE, NOT NULL (calculada: data_criacao + validade_dias, preenchida no service antes de inserir)
   - desconto_percentual: DECIMAL(5,2), NOT NULL, default 0
   - observacoes: VARCHAR(500), nullable
   - criado_em: DATETIME, NOT NULL, server_default=func.now()
   - atualizado_em: DATETIME, NOT NULL, server_default=func.now(), onupdate=func.now()
   - relationship: cliente (Cliente, back_populates='orcamentos')
   - relationship: itens (list[ItemOrcamento], back_populates='orcamento', cascade='all, delete-orphan')

   ItemOrcamento (tabela itens_orcamento):
   - id: INT, PK, autoincrement
   - orcamento_id: INT, NOT NULL, FK para orcamentos.id
   - produto_id: INT, NOT NULL, FK para produtos.id
   - quantidade: INT, NOT NULL (CHECK: quantidade > 0)
   - preco_unitario: DECIMAL(10,2), NOT NULL (preço vigente no momento da criação do item, congelado)
   - relationship: orcamento (Orcamento, back_populates='itens')
   - relationship: produto (Produto, lazy='joined')

   Adicionar relationship orcamentos em Cliente (back_populates='cliente' em Orcamento).

2. Criar src/atalaia/db/models/venda.py com schema base para PDV (será expandido no módulo PDV):

   Venda (tabela vendas):
   - id: INT, PK, autoincrement
   - orcamento_id: INT, nullable, FK para orcamentos.id (None quando venda direta pelo PDV)
   - cliente_id: INT, nullable, FK para clientes.id (nullable: PDV permite venda sem cliente identificado)
   - status: ENUM('aberta', 'finalizada', 'cancelada'), NOT NULL, default 'aberta'
   - desconto_percentual: DECIMAL(5,2), NOT NULL, default 0
   - total: DECIMAL(10,2), NOT NULL, default 0
   - criado_em: DATETIME, NOT NULL, server_default=func.now()
   - atualizado_em: DATETIME, NOT NULL, server_default=func.now(), onupdate=func.now()
   - relationship: orcamento (Orcamento, back_populates='venda')
   - relationship: cliente (Cliente, back_populates='vendas')
   - relationship: itens (list[ItemVenda], cascade='all, delete-orphan')

   ItemVenda (tabela itens_venda):
   - id: INT, PK, autoincrement
   - venda_id: INT, NOT NULL, FK para vendas.id
   - produto_id: INT, NOT NULL, FK para produtos.id
   - quantidade: INT, NOT NULL (CHECK: quantidade > 0)
   - preco_unitario: DECIMAL(10,2), NOT NULL
   - relationship: venda (Venda, back_populates='itens')
   - relationship: produto (Produto, lazy='joined')

   Adicionar relationship venda em Orcamento (back_populates='orcamento' em Venda, uselist=False).
   Adicionar relationship vendas em Cliente (back_populates='cliente' em Venda).

3. Gerar migration via alembic revision --autogenerate -m "cria tabelas orcamentos e vendas". Mostrar conteúdo completo antes de rodar alembic upgrade head. Confirmar down_revision = '876359399b80'.

4. Não rodar alembic upgrade head ainda.

PARTE 2 — Service

5. Criar src/atalaia/modules/orcamentos/__init__.py (vazio).

6. Criar src/atalaia/modules/orcamentos/exceptions.py:
   - OrcamentosError(Exception)
   - OrcamentoNaoEncontradoError
   - OrcamentoJaFinalizadoError (tentativa de alterar orçamento aprovado ou recusado)
   - ClienteNaoEncontradoError (re-exportar ou importar de clientes.exceptions)
   - ProdutoNaoEncontradoError (re-exportar ou importar de entrada_mercadorias.exceptions)

7. Criar src/atalaia/modules/orcamentos/service.py com:

   - _get_validade_padrao() -> int: lê configuracoes onde chave='validade_orcamento_dias', retorna int; se não existir, retorna 10 como fallback

   - criar_orcamento(cliente_id: int, validade_dias: int | None, desconto_percentual: Decimal, observacoes: str | None) -> Orcamento:
     * validade_dias: se None, usa _get_validade_padrao()
     * data_validade = date.today() + timedelta(days=validade_dias)
     * valida cliente existe e está ativo (ClienteNaoEncontradoError, ClienteInativoError)
     * status='aberto'

   - adicionar_item(orcamento_id: int, produto_id: int, quantidade: int) -> ItemOrcamento:
     * só em orçamento 'aberto' (OrcamentoJaFinalizadoError se aprovado/recusado)
     * valida produto existe e está ativo
     * preco_unitario = obter_preco_vigente(produto, date.today()) — congela o preço vigente no momento
     * valida desconto do produto via validar_desconto() se desconto_percentual > 0

   - remover_item(item_id: int) -> None: só em orçamento 'aberto'

   - atualizar_orcamento(orcamento_id: int, dados: dict) -> Orcamento: atualiza campos parciais (validade_dias, desconto_percentual, observacoes); recalcula data_validade se validade_dias mudar; só em 'aberto'

   - aprovar_orcamento(orcamento_id: int) -> Venda:
     * só em 'aberto' e dentro da validade (data.today() <= data_validade)
     * se vencido: levanta OrcamentoVencidoError (adicionar em exceptions.py)
     * seta status='aprovado'
     * cria Venda com os mesmos itens, mesmo cliente, mesmo desconto
     * para cada item: dar_baixa_estoque(produto_id, quantidade) via UPDATE atômico (mesmo padrão já estabelecido)
     * retorna a Venda criada

   - recusar_orcamento(orcamento_id: int) -> None: seta status='recusado'; não altera estoque

   - obter_orcamento(orcamento_id: int) -> Orcamento: com joinedload de cliente e itens (e produto de cada item)

   - listar_orcamentos(status: str | None = None, cliente_id: int | None = None) -> list[Orcamento]: com joinedload de cliente

   - numero_formatado(orcamento: Orcamento) -> str: retorna f"ORC-{orcamento.numero:04d}"

PARTE 3 — UI

8. Criar src/atalaia/modules/orcamentos/ui/__init__.py (vazio).

9. Criar src/atalaia/modules/orcamentos/ui/tela_orcamentos.py com TelaOrcamentos(QWidget):

   Filtros: combo Status (Todos/Aberto/Aprovado/Recusado), combo Cliente (Todos + lista), botões Buscar/Limpar

   Tabela (QTableView + QAbstractTableModel):
   - Colunas: Nº Orçamento, Cliente, Data, Validade, Total, Desconto, Status
   - Orçamentos vencidos (abertos com data_validade < hoje) em vermelho
   - Aprovados em verde, Recusados em cinza

   Botões:
   - "Novo Orçamento": abre FormularioOrcamento
   - "Abrir" (linha selecionada): abre FormularioOrcamento com dados; se aprovado/recusado, modo somente leitura
   - "Aprovar" (só abertos e dentro da validade): confirmação + aprovar_orcamento() + recarrega
   - "Recusar" (só abertos): confirmação + recusar_orcamento() + recarrega
   - "Visualizar" (linha selecionada): abre VisualizacaoOrcamento (preview de impressão)

10. Criar src/atalaia/modules/orcamentos/ui/formulario_orcamento.py com FormularioOrcamento(QDialog):

    Cabeçalho:
    - combo Cliente com botão "+" abrindo DialogoCliente (já criado em clientes/ui/)
    - campo Validade (dias, preenchido com padrão das configurações, editável)
    - campo Desconto % (0-100, default 0)
    - campo Observações

    Seção de itens (após salvar cabeçalho):
    - busca produto por nome ou código de barras (buscar_produtos_por_termo)
    - ao não encontrar: mesmo fluxo de Entrada de Mercadorias (oferecer cadastrar novo produto)
    - Quantidade (inteiro, mínimo 1)
    - Preço Unitário: preenchido automaticamente com obter_preco_vigente(), read-only (congelado no momento da adição)
    - Subtotal calculado: quantidade × preço_unitario
    - Botão "Adicionar Item"

    Tabela de itens: Produto, Qtd, Preço Unit., Subtotal; botão Remover

    Rodapé com totais:
    - Subtotal (soma dos itens)
    - Desconto (percentual aplicado sobre subtotal)
    - Total Final

    Modo somente leitura para aprovado/recusado.

11. Criar src/atalaia/modules/orcamentos/ui/visualizacao_orcamento.py com VisualizacaoOrcamento(QDialog):
    - Usa QTextBrowser ou QLabel para mostrar o orçamento formatado (dados da loja via configuracoes, dados do cliente, itens, totais, validade, número ORC-XXXX)
    - Botão "Imprimir" que usa QPrinter + QPrintDialog (diálogo nativo do Windows com todas as impressoras instaladas)
    - Botão "Fechar"

12. Atualizar main_window.py: substituir placeholder de Orçamentos por TelaOrcamentos().

PARTE 4 — Testes

13. Criar tests/test_orcamento_service.py:
    - criar_orcamento com cliente inativo levanta ClienteInativoError
    - adicionar_item congela preco_unitario com obter_preco_vigente() na data atual
    - aprovar_orcamento cria Venda, baixa estoque de cada item via UPDATE atômico, seta status='aprovado'
    - aprovar_orcamento vencido levanta OrcamentoVencidoError
    - aprovar_orcamento já aprovado levanta OrcamentoJaFinalizadoError
    - recusar_orcamento não altera estoque

14. Criar tests/test_ui_orcamentos.py (pytest-qt):
    - smoke: TelaOrcamentos instancia sem erro
    - smoke: FormularioOrcamento abre sem erro, validade preenchida com padrão

15. Atualizar CLAUDE.md: adicionar orcamentos, itens_orcamento, vendas, itens_venda no schema; documentar que aprovar_orcamento usa UPDATE atômico de estoque (mesmo padrão de PDV e Entrada de Mercadorias).

CRITÉRIOS DE ACEITE
- Migration com down_revision correto e todas as tabelas/constraints esperadas
- aprovar_orcamento é transação atômica: venda criada + estoque baixado + status atualizado, tudo ou nada
- número ORC-XXXX formatado corretamente
- pytest passa em todos os testes (99 passed, 5 skipped era o estado anterior)
- Nenhum get_session() direto nos arquivos de UI

Mostre o plano antes de criar os arquivos.