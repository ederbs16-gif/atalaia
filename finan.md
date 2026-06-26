Carregue @CLAUDE.md antes de começar. Este prompt cria o módulo Financeiro completo com três submódulos: Caixa, Contas a Pagar e Contas a Receber. As tabelas vendas e clientes já existem em produção.

CONTEXTO DE NEGÓCIO
- Caixa: abertura com saldo inicial, fechamento com totais por forma de pagamento. Configuração global caixa_individual (chave em configuracoes, default 'false'): False = um caixa por vez no sistema; True = um caixa por PC (identificado pelo hostname).
- Contas a Pagar: lançamento manual ou vinculado a fornecedor. Parcelamento automático gera N lançamentos. Pagamento parcial com controle de valor pago.
- Contas a Receber: lançamento manual ou vinculado a cliente/orçamento. Mesmas regras de parcelamento e pagamento parcial.
- Status de contas: Pendente → Pago Parcialmente → Pago
- Formas de pagamento: dinheiro, pix, debito, credito

PARTE 1 — Models e migration

1. Criar src/atalaia/db/models/caixa.py com modelo Caixa (tabela caixas):
   - id: INT, PK, autoincrement
   - hostname: VARCHAR(100), NOT NULL (identifica o PC; usado quando caixa_individual=True)
   - saldo_inicial: DECIMAL(10,2), NOT NULL, default 0
   - total_dinheiro: DECIMAL(10,2), NOT NULL, default 0
   - total_pix: DECIMAL(10,2), NOT NULL, default 0
   - total_debito: DECIMAL(10,2), NOT NULL, default 0
   - total_credito: DECIMAL(10,2), NOT NULL, default 0
   - status: ENUM('aberto', 'fechado'), NOT NULL, default 'aberto'
   - aberto_em: DATETIME, NOT NULL, server_default=func.now()
   - fechado_em: DATETIME, nullable
   - observacoes: VARCHAR(500), nullable

2. Criar src/atalaia/db/models/conta_pagar.py com modelo ContaPagar (tabela contas_pagar):
   - id: INT, PK, autoincrement
   - descricao: VARCHAR(200), NOT NULL
   - valor_total: DECIMAL(10,2), NOT NULL (CHECK: valor_total > 0)
   - valor_pago: DECIMAL(10,2), NOT NULL, default 0
   - status: ENUM('pendente', 'pago_parcialmente', 'pago'), NOT NULL, default 'pendente'
   - vencimento: DATE, NOT NULL
   - fornecedor_id: INT, nullable, FK para fornecedores.id
   - parcela_numero: INT, nullable (ex: 1 de 3)
   - parcela_total: INT, nullable (ex: 3 de 3)
   - grupo_parcelas: VARCHAR(36), nullable (UUID gerado pelo service para agrupar parcelas da mesma compra)
   - observacoes: VARCHAR(500), nullable
   - criado_em: DATETIME, NOT NULL, server_default=func.now()
   - atualizado_em: DATETIME, NOT NULL, server_default=func.now(), onupdate=func.now()

3. Criar src/atalaia/db/models/pagamento_conta_pagar.py com PagamentoContaPagar (tabela pagamentos_conta_pagar):
   - id: INT, PK, autoincrement
   - conta_pagar_id: INT, NOT NULL, FK para contas_pagar.id
   - valor: DECIMAL(10,2), NOT NULL (CHECK: valor > 0)
   - forma_pagamento: ENUM('dinheiro','pix','debito','credito'), NOT NULL
   - data_pagamento: DATE, NOT NULL
   - observacoes: VARCHAR(200), nullable
   - criado_em: DATETIME, NOT NULL, server_default=func.now()

4. Criar src/atalaia/db/models/conta_receber.py com ContaReceber (tabela contas_receber):
   - id: INT, PK, autoincrement
   - descricao: VARCHAR(200), NOT NULL
   - valor_total: DECIMAL(10,2), NOT NULL (CHECK: valor_total > 0)
   - valor_pago: DECIMAL(10,2), NOT NULL, default 0
   - status: ENUM('pendente', 'pago_parcialmente', 'pago'), NOT NULL, default 'pendente'
   - vencimento: DATE, NOT NULL
   - cliente_id: INT, nullable, FK para clientes.id
   - orcamento_id: INT, nullable, FK para orcamentos.id
   - parcela_numero: INT, nullable
   - parcela_total: INT, nullable
   - grupo_parcelas: VARCHAR(36), nullable
   - observacoes: VARCHAR(500), nullable
   - criado_em: DATETIME, NOT NULL, server_default=func.now()
   - atualizado_em: DATETIME, NOT NULL, server_default=func.now(), onupdate=func.now()

5. Criar src/atalaia/db/models/pagamento_conta_receber.py com PagamentoContaReceber (tabela pagamentos_conta_receber):
   - id: INT, PK, autoincrement
   - conta_receber_id: INT, NOT NULL, FK para contas_receber.id
   - valor: DECIMAL(10,2), NOT NULL (CHECK: valor > 0)
   - forma_pagamento: ENUM('dinheiro','pix','debito','credito'), NOT NULL
   - data_pagamento: DATE, NOT NULL
   - observacoes: VARCHAR(200), nullable
   - criado_em: DATETIME, NOT NULL, server_default=func.now()

6. Adicionar relationships:
   - ContaPagar.fornecedor (nullable), ContaPagar.pagamentos (cascade all delete-orphan)
   - ContaReceber.cliente (nullable), ContaReceber.orcamento (nullable), ContaReceber.pagamentos (cascade all delete-orphan)
   - Caixa sem relationships por enquanto (PDV vai registrar totais via service)

7. Atualizar db/models/__init__.py com todos os novos modelos.

8. Gerar migration via alembic revision --autogenerate -m "cria modulo financeiro". Mostrar conteúdo completo antes de rodar alembic upgrade head. Confirmar down_revision = '0c5735d2929f'.

9. Não rodar alembic upgrade head ainda.

PARTE 2 — Service

10. Criar src/atalaia/modules/financeiro/__init__.py (vazio).

11. Criar src/atalaia/modules/financeiro/exceptions.py:
    - FinanceiroError(Exception)
    - CaixaJaAbertoError
    - CaixaNaoAbertoError (tentativa de venda sem caixa aberto)
    - CaixaJaFechadoError
    - ContaNaoEncontradaError
    - ContaJaPagaError (tentativa de pagar conta já quitada)
    - PagamentoExcedeValorError (soma dos pagamentos excederia valor_total)

12. Criar src/atalaia/modules/financeiro/caixa_service.py:
    - abrir_caixa(saldo_inicial: Decimal, observacoes: str | None) -> Caixa:
      * Lê configuracoes 'caixa_individual' (default 'false')
      * Se False: verifica se existe algum caixa 'aberto' no sistema (qualquer hostname); se sim, levanta CaixaJaAbertoError
      * Se True: verifica se existe caixa 'aberto' para o hostname atual (socket.gethostname()); se sim, levanta CaixaJaAbertoError
      * Cria caixa com status='aberto'
    - fechar_caixa(caixa_id: int, observacoes: str | None) -> Caixa:
      * Seta status='fechado', fechado_em=datetime.now()
      * Não altera totais (são acumulados pelo PDV via registrar_pagamento_caixa)
    - obter_caixa_aberto() -> Caixa | None: retorna caixa aberto atual (respeitando lógica de caixa_individual)
    - registrar_pagamento_caixa(caixa_id: int, forma: str, valor: Decimal) -> None:
      * UPDATE atômico: total_dinheiro/pix/debito/credito += valor conforme forma
      * Usado pelo PDV ao finalizar venda
    - listar_caixas(limit: int = 30) -> list[Caixa]: ordenado por aberto_em desc

13. Criar src/atalaia/modules/financeiro/contas_service.py com funções para ambos os tipos:
    - criar_conta_pagar(dados: dict) -> ContaPagar: valida descricao não vazia, valor_total > 0
    - criar_conta_pagar_parcelada(dados: dict, num_parcelas: int) -> list[ContaPagar]:
      * Gera UUID para grupo_parcelas
      * Cria num_parcelas contas com vencimentos mensais (vencimento + 30*i dias)
      * parcela_numero de 1 a num_parcelas, parcela_total = num_parcelas
    - registrar_pagamento_pagar(conta_id: int, valor: Decimal, forma: str, data: date, obs: str | None) -> PagamentoContaPagar:
      * Verifica conta não está 'pago' (ContaJaPagaError)
      * Verifica valor não excede (valor_pago + valor) > valor_total (PagamentoExcedeValorError)
      * Registra pagamento, atualiza valor_pago
      * Atualiza status: se valor_pago == valor_total → 'pago'; se 0 < valor_pago < valor_total → 'pago_parcialmente'
      * UPDATE atômico para valor_pago (mesmo padrão de estoque)
    - listar_contas_pagar(status: str | None, vencimento_ate: date | None) -> list[ContaPagar]
    - obter_conta_pagar(conta_id: int) -> ContaPagar
    - (mesmas funções espelhadas para ContaReceber: criar_conta_receber, criar_conta_receber_parcelada, registrar_pagamento_receber, listar_contas_receber, obter_conta_receber)

PARTE 3 — UI

14. Criar src/atalaia/modules/financeiro/ui/__init__.py (vazio).

15. Criar src/atalaia/modules/financeiro/ui/tela_financeiro.py com TelaFinanceiro(QWidget):
    Layout com QTabWidget com 3 abas: "💰 Caixa", "📤 Contas a Pagar", "📥 Contas a Receber"

    Aba Caixa:
    - Card de status do caixa atual (Aberto/Fechado, saldo inicial, totais por forma, hostname)
    - Botão "Abrir Caixa": abre DialogoAbrirCaixa (saldo inicial + observações)
    - Botão "Fechar Caixa" (só com caixa aberto): confirmação + fechar_caixa()
    - Tabela de histórico de caixas (QTableView): Data, Hostname, Saldo Inicial, Total, Status

    Aba Contas a Pagar:
    - Filtros: combo Status, date range vencimento, busca por descrição
    - Tabela: Descrição, Fornecedor, Vencimento, Valor Total, Valor Pago, Status, Parcela
    - Contas vencidas em vermelho, vencendo hoje em amarelo
    - Botões: Nova Conta, Nova Conta Parcelada, Registrar Pagamento, Ver Pagamentos

    Aba Contas a Receber:
    - Mesma estrutura de Contas a Pagar, com Cliente e Orçamento no lugar de Fornecedor

16. Criar src/atalaia/modules/financeiro/ui/dialogo_abrir_caixa.py: campo saldo_inicial (Decimal, default 0), observações, botões Abrir/Cancelar.

17. Criar src/atalaia/modules/financeiro/ui/formulario_conta.py com FormularioConta(QDialog):
    - Modo: 'pagar' ou 'receber' (parâmetro no construtor)
    - Campos: Descrição *, Valor Total *, Vencimento *, Parcelar (checkbox), Nº Parcelas (habilitado se Parcelar marcado)
    - Se modo='pagar': combo Fornecedor (opcional) com botão "+"
    - Se modo='receber': combo Cliente (opcional) com botão "+", combo Orçamento (opcional, filtra por cliente selecionado)
    - Salvar: chama criar_conta_pagar ou criar_conta_pagar_parcelada conforme Parcelar

18. Criar src/atalaia/modules/financeiro/ui/dialogo_pagamento.py com DialogoPagamento(QDialog):
    - Mostra: conta selecionada, valor total, valor já pago, saldo restante
    - Campos: Valor (Decimal, max = saldo restante), Forma de Pagamento (combo), Data (QDateEdit, default hoje), Observações
    - Salvar: chama registrar_pagamento_pagar ou registrar_pagamento_receber conforme o tipo da conta

19. Atualizar main_window.py: adicionar financeiro.svg no sidebar entre Entradas e Orçamentos, instanciar TelaFinanceiro().

PARTE 4 — Testes

20. Criar tests/test_financeiro_service.py:
    - abrir_caixa com caixa já aberto levanta CaixaJaAbertoError (modo caixa_individual=False)
    - fechar_caixa seta status='fechado' e fechado_em preenchido
    - registrar_pagamento_pagar atualiza valor_pago e status corretamente
    - registrar_pagamento_pagar excedendo valor_total levanta PagamentoExcedeValorError
    - criar_conta_pagar_parcelada cria N contas com grupo_parcelas igual e vencimentos corretos
    - conta já paga levanta ContaJaPagaError ao tentar novo pagamento

21. Criar tests/test_ui_financeiro.py (pytest-qt):
    - smoke: TelaFinanceiro instancia sem erro, 3 abas presentes
    - smoke: DialogoAbrirCaixa abre sem erro
    - smoke: FormularioConta abre em modo pagar e modo receber sem erro

22. Atualizar CLAUDE.md: adicionar as 5 novas tabelas no schema, documentar lógica de caixa_individual.

CRITÉRIOS DE ACEITE
- Migration com down_revision correto e todos os CHECKs e FKs via op.f(...)
- registrar_pagamento_pagar e registrar_pagamento_receber usam UPDATE atômico para valor_pago
- abrir_caixa respeita configuração caixa_individual
- PDV poderá verificar caixa aberto via obter_caixa_aberto() antes de permitir venda
- pytest passa em todos os testes novos e existentes
- Nenhum get_session() direto nos arquivos de UI

Mostre o plano antes de criar os arquivos.