Carregue @CLAUDE.md antes de começar, para seguir as convenções já estabelecidas (naming_convention de constraints, padrão de get_session(), ENUM nativo para campos de valor fixo, server_default em campos de data).

Este é o primeiro prompt do módulo Cadastro de Produtos (src/atalaia/modules/produtos/). A infraestrutura de banco já existe: Base declarativa em src/atalaia/db/base.py, sessão em src/atalaia/db/session.py, Alembic configurado e funcionando, modelos Usuario e Configuracao já em produção via migration.

CONTEXTO DE NEGÓCIO
A Atalaia vende produtos físicos com controle de estoque (papelaria, acessórios eletrônicos) e presta serviços sem estoque (impressão, xerox, suporte de informática). Produto e serviço convivem na mesma venda/orçamento, então ficam na mesma tabela, diferenciados por um campo tipo. O sistema novo não permite estoque negativo (decisão deliberada, diferente do sistema legado que permitia); essa regra é reforçada tanto por CHECK constraint no banco quanto, futuramente, por validação na camada de negócio do PDV antes de fechar a venda.

TAREFA

1. Criar modelo Categoria em src/atalaia/db/models/categoria.py:
   - id: INT, PK, autoincrement
   - nome: VARCHAR(100), NOT NULL, UNIQUE
   - criado_em: DATETIME, NOT NULL, server_default=func.now()

2. Criar modelo Produto em src/atalaia/db/models/produto.py com os seguintes campos:

   Identificação e classificação:
   - id: INT, PK, autoincrement
   - nome: VARCHAR(200), NOT NULL
   - descricao: VARCHAR(500), nullable
   - tipo: ENUM('produto', 'servico'), NOT NULL
   - categoria_id: INT, NOT NULL, FK para categorias.id

   Estoque:
   - controla_estoque: BOOLEAN, NOT NULL, default True
   - estoque_atual: INT, NOT NULL, default 0
   - estoque_minimo: INT, NOT NULL, default 0 (usado futuramente por relatórios de estoque baixo; não implementar lógica de alerta agora, só o campo)

   Preço e desconto:
   - preco_custo: DECIMAL(10,2), nullable (nem sempre conhecido, especialmente em serviço)
   - preco_venda: DECIMAL(10,2), NOT NULL
   - permite_desconto: BOOLEAN, NOT NULL, default False
   - desconto_maximo_percentual: DECIMAL(5,2), NOT NULL, default 0 (percentual de 0 a 100; usado pelo PDV futuramente para limitar o desconto aplicável na venda quando permite_desconto=True; não implementar a lógica de aplicação agora, só o campo)

   Promoção:
   - produto_em_promocao: BOOLEAN, NOT NULL, default False
   - preco_promocional: DECIMAL(10,2), nullable
   - promocao_inicio: DATE, nullable
   - promocao_fim: DATE, nullable
   (regra de negócio futura, não implementar agora: quando produto_em_promocao=True e a data atual estiver entre promocao_inicio e promocao_fim, o PDV usa preco_promocional no lugar de preco_venda)

   Outros:
   - codigo_barras: VARCHAR(50), nullable, UNIQUE, com índice próprio (consultado por leitor de código de barras no PDV, precisa de busca rápida além da unicidade)
   - unidade_medida: VARCHAR(10), NOT NULL, default 'UN'
   - ativo: BOOLEAN, NOT NULL, default True (soft-delete: produtos referenciados em vendas passadas nunca podem ser excluídos fisicamente, só marcados como inativo)
   - criado_em: DATETIME, NOT NULL, server_default=func.now()
   - atualizado_em: DATETIME, NOT NULL, server_default=func.now(), onupdate=func.now()

3. Adicionar relationship entre Produto e Categoria (Produto.categoria e Categoria.produtos), usando back_populates.

4. Adicionar os seguintes CHECK constraints na tabela produtos, todos via CheckConstraint em __table_args__, seguindo a naming_convention já definida em base.py para o tipo "ck":
   - estoque_atual >= 0
   - preco_venda >= 0
   - desconto_maximo_percentual >= 0 AND desconto_maximo_percentual <= 100
   - promocao_inicio IS NULL OR promocao_fim IS NULL OR promocao_fim >= promocao_inicio
   - preco_promocional IS NULL OR preco_promocional <= preco_venda

5. Gerar a migration via alembic revision --autogenerate -m "cria tabelas categorias e produtos". Antes de aplicar, me mostre o conteúdo completo do arquivo gerado para eu revisar: nomes de constraint (via op.f(...) seguindo a convention), tipo ENUM com os dois valores corretos, os cinco CHECK constraints, e o índice em codigo_barras.

6. Não rode alembic upgrade head ainda; aguarde minha aprovação explícita do conteúdo da migration.

7. Criar tests/test_models_produto.py cobrindo:
   - criação de categoria e produto válidos, incluindo um produto do tipo servico com controla_estoque=False
   - violação de UNIQUE em categoria.nome
   - violação de UNIQUE em produto.codigo_barras
   - tentativa de inserir produto com tipo fora de ('produto', 'servico') deve falhar
   - relationship produto.categoria retorna o objeto correto
   - documentar no teste que os CHECK constraints (estoque_atual, preco_venda, desconto_maximo_percentual, datas de promoção, preco_promocional) só são garantidos no MySQL real, já que SQLite pode não aplicar CHECK dependendo da versão; os testes desses CHECKs ficam marcados como comportamento esperado em produção, não validados pelo SQLite do teste automatizado

8. Atualizar CLAUDE.md acrescentando: as tabelas produtos e categorias na seção de schema; a regra de soft-delete (produtos nunca são excluídos fisicamente, sempre via ativo=False); e a nota de que estoque negativo é proibido por decisão deliberada (diferente do sistema legado), reforçado por CHECK no banco e, futuramente, por validação na camada de negócio do PDV antes de confirmar a venda.

CRITÉRIOS DE ACEITE
- Migration gerada mostra os cinco CHECK constraints, o ENUM correto, UNIQUE em nome (categoria) e codigo_barras (produto), e índice em codigo_barras.
- pytest passa em todos os testes novos e nos já existentes.
- Nenhum dado é aplicado no MySQL real até eu aprovar o conteúdo da migration.
- CLAUDE.md atualizado com o novo schema, a regra de soft-delete e a regra de estoque nunca negativo.

Mostre o plano antes de criar os arquivos.