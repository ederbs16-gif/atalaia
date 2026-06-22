Carregue @CLAUDE.md antes de começar. A tabela fornecedores já existe em produção (migration 5fd03d193769). Este prompt cria as tabelas de entrada de mercadorias e a lógica de negócio, sem UI ainda.

CONTEXTO DE NEGÓCIO
Uma entrada de mercadoria registra o recebimento de produtos de um fornecedor. Cada entrada tem um cabeçalho (fornecedor, nota fiscal, data) e múltiplos itens (produto, quantidade, custo unitário). Ao confirmar uma entrada:
- O estoque de cada produto é incrementado via dar_entrada_estoque() já existente em produtos/service.py (UPDATE atômico, não leitura+escrita)
- O custo do produto é atualizado seguindo a regra: preco_custo_anterior recebe o valor atual de preco_custo; preco_custo recebe o custo unitário da entrada; custo_medio recebe (preco_custo_anterior + preco_custo) / 2 (média simples dos dois últimos custos, decisão deliberada documentada no CLAUDE.md)
- Uma entrada confirmada não pode ser editada nem excluída (imutabilidade de registro fiscal)

TAREFA

1. Adicionar três campos ao modelo Produto em src/atalaia/db/models/produto.py:
   - preco_custo_anterior: DECIMAL(10,2), nullable (None quando nunca houve custo registrado antes)
   - custo_medio: DECIMAL(10,2), nullable
   Os dois campos são nullable porque produtos novos não têm histórico de custo ainda. O campo preco_custo já existe.

2. Criar src/atalaia/db/models/entrada_mercadoria.py com dois modelos no mesmo arquivo:

   EntradaMercadoria (tabela entradas_mercadorias):
   - id: INT, PK, autoincrement
   - fornecedor_id: INT, NOT NULL, FK para fornecedores.id
   - numero_nota: VARCHAR(50), nullable
   - data_entrada: DATE, NOT NULL, server_default=func.current_date()
   - observacoes: VARCHAR(500), nullable
   - status: ENUM('rascunho', 'confirmada'), NOT NULL, default 'rascunho'
   - criado_em: DATETIME, NOT NULL, server_default=func.now()
   - atualizado_em: DATETIME, NOT NULL, server_default=func.now(), onupdate=func.now()
   - relationship: fornecedor (Fornecedor, back_populates='entradas')
   - relationship: itens (list[ItemEntrada], back_populates='entrada', cascade='all, delete-orphan')

   ItemEntrada (tabela itens_entrada):
   - id: INT, PK, autoincrement
   - entrada_id: INT, NOT NULL, FK para entradas_mercadorias.id
   - produto_id: INT, NOT NULL, FK para produtos.id
   - quantidade: INT, NOT NULL (CHECK: quantidade > 0)
   - custo_unitario: DECIMAL(10,2), NOT NULL (CHECK: custo_unitario >= 0)
   - relationship: entrada (EntradaMercadoria, back_populates='itens')
   - relationship: produto (Produto, joinedload via lazy='joined', para nunca acessar fora da sessão)

   Adicionar relationship entradas em Fornecedor (back_populates='fornecedor' em EntradaMercadoria).
   Adicionar relationship itens_entrada em Produto (back_populates='produto' em ItemEntrada).

3. Criar src/atalaia/modules/entrada_mercadorias/entrada_service.py com:

   - criar_entrada(fornecedor_id: int, numero_nota: str | None, data_entrada: date | None, observacoes: str | None) -> EntradaMercadoria: cria em status 'rascunho'. Verifica se fornecedor existe e está ativo (FornecedorNaoEncontradoError, FornecedorInativoError).

   - adicionar_item(entrada_id: int, produto_id: int, quantidade: int, custo_unitario: Decimal) -> ItemEntrada: só permitido se entrada estiver em 'rascunho' (EntradaJaConfirmadaError se status='confirmada'). Valida quantidade > 0 e custo_unitario >= 0 em Python antes de tocar no banco. Verifica se produto existe e está ativo (ProdutoNaoEncontradoError, ProdutoInativoError — adicionar essas duas exceções em exceptions.py do módulo).

   - remover_item(item_id: int) -> None: só permitido se entrada estiver em 'rascunho'.

   - confirmar_entrada(entrada_id: int) -> None: operação atômica — tudo acontece numa única sessão/transação. Para cada item:
     a) Chamar produtos/service.dar_entrada_estoque(produto_id, quantidade) — UPDATE atômico já existente
     b) Atualizar custo do produto em SQL direto atômico:
        UPDATE produtos SET
          preco_custo_anterior = preco_custo,
          preco_custo = :novo_custo,
          custo_medio = CASE
            WHEN preco_custo IS NULL THEN :novo_custo
            WHEN preco_custo IS NULL THEN :novo_custo  
            ELSE (preco_custo + :novo_custo) / 2
          END
        WHERE id = :produto_id
        (use CASE para o cenário de primeiro custo: se preco_custo era NULL, custo_medio = novo_custo, não (NULL + novo_custo) / 2)
     Setar status='confirmada' na entrada. Se qualquer etapa falhar, toda a transação faz rollback.

   - obter_entrada(entrada_id: int) -> EntradaMercadoria: com joinedload de fornecedor e itens (e produto de cada item).

   - listar_entradas(status: str | None = None, fornecedor_id: int | None = None) -> list[EntradaMercadoria]: com joinedload de fornecedor.

4. Adicionar EntradaJaConfirmadaError, ProdutoNaoEncontradoError, ProdutoInativoError em exceptions.py do módulo.

5. Gerar migration via alembic revision --autogenerate -m "cria tabelas entrada mercadorias e adiciona campos custo a produtos". Mostrar conteúdo completo antes de rodar alembic upgrade head. Confirmar:
   - down_revision aponta para 5fd03d193769
   - ALTER TABLE produtos adiciona preco_custo_anterior e custo_medio
   - CREATE TABLE entradas_mercadorias e itens_entrada com FKs corretas
   - CHECK constraints em itens_entrada (quantidade > 0, custo_unitario >= 0) via op.f(...)

6. Não rodar alembic upgrade head ainda.

7. Criar tests/test_entrada_service.py cobrindo:
   - criar_entrada com fornecedor inativo levanta FornecedorInativoError
   - adicionar_item com quantidade <= 0 levanta ValueError antes de tocar no banco
   - adicionar_item em entrada confirmada levanta EntradaJaConfirmadaError
   - confirmar_entrada: estoque do produto aumenta corretamente; preco_custo_anterior, preco_custo e custo_medio atualizados conforme a regra de média simples; status muda para 'confirmada'
   - confirmar_entrada com primeiro custo (preco_custo era NULL): custo_medio = novo_custo, não NULL
   - confirmar_entrada duas vezes levanta EntradaJaConfirmadaError na segunda tentativa

8. Atualizar CLAUDE.md: adicionar entradas_mercadorias e itens_entrada no schema; documentar a regra de custo médio (média simples dos dois últimos custos, decisão deliberada); documentar que entradas confirmadas são imutáveis.

CRITÉRIOS DE ACEITE
- Migration gerada com down_revision correto e todos os campos/constraints esperados
- confirmar_entrada usa UPDATE atômico para estoque E para custo, nunca leitura+escrita em Python
- pytest passa em todos os testes novos e existentes
- Nenhuma migration aplicada até aprovação explícita

Mostre o plano antes de criar os arquivos.