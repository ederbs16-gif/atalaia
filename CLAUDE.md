# Atalaia — Guia para Claude

## Stack técnica
- **Python** 3.11+
- **Interface**: PySide6 (Qt6 para Python)
- **Banco**: MySQL acessado via SQLAlchemy 2.x (ORM declarativo + `DeclarativeBase`)
- **Migrations**: Alembic (migrations versionadas — ver regras abaixo)
- **Driver MySQL**: mysql-connector-python
- **Configuração**: python-dotenv (variáveis de ambiente via `.env`) + `config.ini` local por PC (ver abaixo)
- **Testes**: pytest
- **Cupom fiscal (futuro)**: python-escpos (módulo `pdv/` reservado)
- **Empacotamento (futuro)**: PyInstaller
- **hash ultimo Commit valido f93d9e0 (HEAD -> main, origin/main) UI criadas
- **hash commit inicial ce50457 



## Convenções de nomenclatura
- Arquivos e módulos Python: `snake_case`
- Classes Python: `PascalCase`
- Tabelas e colunas do banco: em **português**, `snake_case`
- Nomes de tabela no **plural**: `produtos`, `categorias`, `usuarios`, `orcamentos`
- Variáveis de ambiente: `UPPER_SNAKE_CASE`

## Estrutura de pastas
```
src/atalaia/
  config.py              — carrega variáveis de ambiente e monta DATABASE_URL
  main.py                — entrypoint: inicializa QApplication e abre MainWindow
  db/
    base.py              — DeclarativeBase compartilhada por todos os models
    session.py           — engine + SessionLocal
    models/              — um arquivo por entidade (ex: produto.py, usuario.py)
  modules/               — um subpacote por módulo de negócio
    produtos/            — cadastro de produtos e controle de estoque
    orcamento/           — geração e gestão de orçamentos
    entrada_mercadorias/ — registro de entrada de estoque
    pdv/                 — ponto de venda + cupom ESC/POS
    relatorios/          — relatórios gerenciais
  ui/
    main_window.py       — janela principal; cada módulo adiciona sua própria tela
  utils/                 — helpers reutilizáveis sem dependência de negócio
tests/
  conftest.py            — fixtures globais do pytest
```

## Comandos

### Rodar a aplicação
```powershell
# PowerShell (Windows)
$env:PYTHONPATH = "src"; python -m atalaia.main
```

### Rodar testes
```powershell
$env:PYTHONPATH = "src"; pytest
```

### Migrations (Alembic)
```bash
# Aplicar todas as migrations pendentes
alembic upgrade head

# Gerar nova migration a partir das mudanças nos models
alembic revision --autogenerate -m "descricao_da_mudanca"
```

## Sessão de banco — padrão `get_session()`
Todos os módulos devem acessar o banco via `get_session()` de `atalaia.db.session`:

```python
from atalaia.db.session import get_session

with get_session() as session:
    # session faz commit automático ao sair sem erro
    # session faz rollback automático se houver exceção
    result = session.execute(...)
```

Nunca instanciar `SessionLocal` diretamente fora de `session.py`.

## Hash de senha — padrão passlib/bcrypt
Senhas de usuários **nunca** são armazenadas em texto puro. Use `passlib` com bcrypt:

```python
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Gerar hash (no cadastro/alteração de senha)
senha_hash = pwd_context.hash(senha_digitada)

# Verificar senha (no login)
ok = pwd_context.verify(senha_digitada, usuario.senha_hash)
```

O campo `senha_hash` do model `Usuario` armazena exclusivamente o resultado de `pwd_context.hash()`.

## Naming convention de constraints (SQLAlchemy + Alembic)

Toda constraint gerada pelos models herda automaticamente a convenção definida em `src/atalaia/db/base.py` via `MetaData(naming_convention=...)`. Os padrões são:

| Tipo | Padrão | Exemplo |
|---|---|---|
| Index | `ix_%(column_0_label)s` | `ix_usuarios_login` |
| Unique | `uq_%(table_name)s_%(column_0_name)s` | `uq_usuarios_login` |
| Check | `ck_%(table_name)s_%(constraint_name)s` | `ck_usuarios_ativo` |
| Foreign key | `fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s` | `fk_itens_produto_id_produtos` |
| Primary key | `pk_%(table_name)s` | `pk_usuarios` |

**Regra:** nunca nomear constraints manualmente nos models — deixar a convenção gerar o nome. O Alembic usa esses nomes para detectar renomeações e gerar `ALTER` corretos no `--autogenerate`. Toda nova tabela criada em qualquer módulo futuro herda essa convenção automaticamente via `Base`.

## Schema atual (tabelas em produção)

| Tabela | Descrição |
|---|---|
| `usuarios` | Usuários do sistema com perfil `admin` ou `operador` |
| `configuracoes` | Pares chave/valor de configuração global |
| `categorias` | Categorias de produtos |
| `produtos` | Produtos físicos e serviços vendidos/orçados; campos `preco_custo`, `preco_custo_anterior`, `custo_medio` (todos nullable) |
| `fornecedores` | Fornecedores de mercadoria; soft-delete via `ativo=False`; sem UNIQUE em `nome` ou `documento` (ver docstring do model) |
| `clientes` | Clientes do estabelecimento; soft-delete via `ativo=False`; sem UNIQUE em `nome` ou `documento`; histórico de compras será adicionado após Orçamentos e PDV existirem como fonte de dados |
| `entradas_mercadorias` | Cabeçalho de entrada de mercadoria; status `rascunho` ou `confirmada`; FK para `fornecedores` |
| `itens_entrada` | Itens de uma entrada; FK para `entradas_mercadorias` e `produtos`; CHECKs: `quantidade > 0`, `custo_unitario >= 0` |
| `orcamentos` | Orçamentos emitidos; status `aberto`/`aprovado`/`recusado`; `numero` via `max+1` em Python (não autoincrement); `data_criacao` via `date.today()` em Python (sem server_default); FK para `clientes` |
| `itens_orcamento` | Itens de um orçamento; FK para `orcamentos` e `produtos`; `preco_unitario` congelado no momento da adição via `obter_preco_vigente()`; CHECK `quantidade > 0` |
| `vendas` | Venda iniciada no PDV; status `aberta`/`finalizada`/`cancelada`; FK nullable para `orcamentos`, `clientes` e `caixas`; `forma_pagamento_principal` = forma com maior valor pago |
| `itens_venda` | Itens de uma venda; FK para `vendas` e `produtos`; CHECK `quantidade > 0` |
| `caixas` | Registro de abertura/fechamento de caixa; status `aberto`/`fechado`; campos de totais por forma de pagamento (dinheiro/pix/debito/credito); `hostname` identifica a máquina |
| `contas_pagar` | Contas a pagar; status `pendente`/`pago_parcialmente`/`pago`; CHECK `valor_total > 0`; FK nullable para `fornecedores`; suporte a parcelamento via `grupo_parcelas` UUID |
| `pagamentos_conta_pagar` | Pagamentos de conta a pagar; CHECK `valor > 0`; forma `dinheiro`/`pix`/`debito`/`credito` |
| `contas_receber` | Contas a receber; mesmos campos de contas_pagar + FK nullable para `clientes` e `orcamentos` |
| `pagamentos_conta_receber` | Pagamentos de conta a receber; mesmo schema de pagamentos_conta_pagar |
| `pagamentos_venda` | Pagamentos de uma venda; forma `dinheiro`/`pix`/`debito`/`credito`; CHECK `valor > 0`; FK para `vendas` |
| `devolucoes` | Devoluções de venda; tipo `troca`/`reembolso`; status `pendente`/`concluida`; `valor_reembolso` calculado com desconto proporcional |
| `itens_devolucao` | Itens devolvidos; FK para `devolucoes` e `produtos`; `produto_substituto_id` FK nullable para trocas; CHECK `quantidade > 0` |

### Lógica `caixa_individual` (config key)

A chave `caixa_individual` em `configuracoes` controla se o sistema permite um único caixa aberto para toda a rede ou um por máquina:

- `caixa_individual = 'false'` (padrão / ausente): apenas um caixa aberto em todo o sistema. `abrir_caixa` levanta `CaixaJaAbertoError` se qualquer caixa estiver aberto.
- `caixa_individual = 'true'`: um caixa aberto por `hostname` (`socket.gethostname()`). Permite que cada PC da rede abra seu próprio caixa simultaneamente.

A função `_caixa_individual()` em `caixa_service.py` lê essa configuração e retorna `bool`. Toda função de caixa que depende desse comportamento chama `_caixa_individual()` no início.

### Regras de negócio persistidas no banco

**Soft-delete em produtos:** produtos nunca são excluídos fisicamente do banco — apenas marcados como `ativo=False`. Produtos referenciados em vendas ou orçamentos passados devem permanecer acessíveis para histórico. Toda listagem de produtos ativos deve filtrar por `ativo=True`.

**`excluir_rascunho` — única exceção ao soft-delete do projeto:** rascunhos não confirmados são deletados fisicamente via `entrada_service.excluir_rascunho()`. Um rascunho nunca confirmado não tem valor histórico fiscal, então hard delete é correto. O cascade `all, delete-orphan` no relationship `itens` remove os `ItemEntrada` automaticamente. Entradas confirmadas nunca são deletadas — `excluir_rascunho` levanta `EntradaJaConfirmadaError` se status='confirmada'.

**Entradas confirmadas são imutáveis:** uma `EntradaMercadoria` com `status='confirmada'` não pode ter itens adicionados, removidos nem ser confirmada novamente. Qualquer tentativa levanta `EntradaJaConfirmadaError`. Essa imutabilidade garante rastreabilidade fiscal: o histórico de entradas reflete exatamente o que foi recebido.

**Custo médio — média simples dos dois últimos custos (decisão deliberada):** ao confirmar uma entrada, o custo do produto é atualizado assim: `preco_custo_anterior ← preco_custo atual`, `preco_custo ← custo_unitario do item`, `custo_medio ← (preco_custo_anterior + preco_custo) / 2`. Se `preco_custo` era `NULL` (primeiro custo registrado), `custo_medio = novo_custo`. Essa média simples de dois pontos foi escolhida intencionalmente em vez de média ponderada por volume — suficiente para o porte do negócio e fácil de auditar manualmente.

**Estoque nunca negativo (decisão deliberada):** o sistema proíbe estoque negativo por design, diferente do sistema legado que permitia. A regra é reforçada em duas camadas:
1. `CHECK (estoque_atual >= 0)` no banco — bloqueia qualquer INSERT/UPDATE inválido.
2. `finalizar_venda()` em `pdv/venda_service.py` valida estoque via UPDATE atômico antes de commitar — retorna `EstoqueInsuficienteError` ao operador se rowcount=0.

## Atualização atômica de estoque

Operações de entrada e saída de estoque **nunca** usam leitura seguida de escrita em Python. O padrão obrigatório é um único UPDATE com condição embutida no WHERE:

```python
# Baixa — atômico, sem race condition
session.execute(
    text(
        "UPDATE produtos"
        " SET estoque_atual = estoque_atual - :qtd"
        " WHERE id = :id AND controla_estoque = TRUE AND estoque_atual >= :qtd"
    ),
    {"qtd": quantidade, "id": produto_id},
)
# rowcount == 0 → estoque insuficiente ou produto sem controle; tratar após

# Entrada — atômico
session.execute(
    text(
        "UPDATE produtos"
        " SET estoque_atual = estoque_atual + :qtd"
        " WHERE id = :id AND controla_estoque = TRUE"
    ),
    {"qtd": quantidade, "id": produto_id},
)
```

**Por quê:** leitura → cálculo → escrita em Python cria race condition entre sessões concorrentes (duas sessões leem o mesmo estoque e ambas "aprovam" a venda antes de qualquer uma gravar). O UPDATE atômico resolve isso no nível do banco.

**Onde se repete:** `modules/produtos/service.py` → `modules/entrada_mercadorias/` → `modules/orcamentos/service.py` (`aprovar_orcamento`) → `modules/pdv/`. Qualquer novo módulo que mexa em `estoque_atual` deve seguir este padrão.

**`finalizar_venda` — transação atômica única (PDV):** verificação de pagamento + UPDATE estoque de cada item + `status='finalizada'` acontecem dentro de uma única `get_session()`. Commit só ocorre se tudo passar; qualquer exceção (incluindo `EstoqueInsuficienteError`) faz rollback completo. `adicionar_item` verifica disponibilidade mas **não baixa** estoque — só `finalizar_venda` faz a baixa. Após o commit, `registrar_pagamento_caixa` é chamado por forma de pagamento (sessões separadas — log de auditoria, não crítico para a venda).

## Convenções de UI (PySide6)

**Acesso ao banco:** telas nunca importam `get_session()` nem fazem queries diretamente. Toda leitura e escrita passa pelas funções de `service.py` do módulo correspondente. Exceções do service são capturadas e exibidas via `QMessageBox.critical` — nunca como traceback cru.

**Listagens:** usar `QTableView` + subclasse de `QAbstractTableModel` (nunca `QTableWidget`). O model expõe `atualizar(lista)` + `produto_em_linha(row)` e implementa `data()` com suporte a `DisplayRole`, `BackgroundRole`, `ForegroundRole` e `TextAlignmentRole`. Esse padrão se repete em todos os módulos futuros.

## Busca de fornecedores — `buscar_fornecedores_por_termo`

`fornecedor_service.buscar_fornecedores_por_termo(termo, apenas_ativos=True)` filtra fornecedores por nome **OU** documento via `LIKE %termo%` (case-insensitive) diretamente no banco — nunca filtro em memória. Termo vazio retorna todos. Parâmetro `apenas_ativos=False` inclui fornecedores inativos (usado no combo "Todos" de `TelaFornecedores`).

## Arquitetura de configuração — híbrida banco + config.ini

O sistema usa duas camadas de configuração:

| Camada | Arquivo | Escopo | Módulo |
|---|---|---|---|
| Dados de negócio | MySQL `configuracoes` | Compartilhado (rede) | `modules/configuracoes/service.py` |
| Preferências locais | `config.ini` | Por PC | `src/atalaia/config_local.py` |

**`config.ini`** — criado automaticamente na raiz do projeto se não existir, **no `.gitignore`**. Lido pelo singleton `ConfigLocal.instancia()`. Seções: `[interface]`, `[impressora]`, `[banco]`, `[backup]`, `[sistema]`.

**Chaves padrão em `configuracoes` (MySQL):**

| Grupo | Chave | Padrão |
|---|---|---|
| Empresa | `nome_empresa`, `cnpj`, `endereco`, `telefone`, `email`, `site`, `logo_path` | `""` |
| PIX | `pix_tipo_chave`, `pix_chave`, `pix_nome_recebedor`, `pix_cidade`, `pix_descricao` | `""` |
| Sistema | `validade_orcamento_dias` | `"10"` |
| Sistema | `caixa_individual` | `"false"` |
| Sistema | `desconto_maximo_global` | `"100"` |

**Atenção:** `Configuracao` usa `id` (int autoincrement) como PK — `chave` é UNIQUE mas não é PK. Sempre usar `select(Configuracao).where(Configuracao.chave == chave)` para buscar; nunca `session.get(Configuracao, chave)`.

**Senha do programador (backup_service.py):** apenas o hash bcrypt é armazenado em código como `_SENHA_HASH`. Nunca expor a senha original no código ou nos testes. Testes de senha correta usam a variável de ambiente `PROGRAMADOR_SENHA`.

## Regras inegociáveis
1. **Nunca commitar `.env` ou qualquer credencial** — o arquivo está no `.gitignore`.
2. **Toda mudança de schema vira migration** — nunca executar `ALTER TABLE` direto no servidor.
   Motivo: três PCs compartilham o mesmo servidor MySQL; migrations garantem schema consistente.
3. Credenciais de banco ficam exclusivamente em `.env` (nunca em código).
4. **Nunca armazenar senha em texto puro** — sempre usar `passlib[bcrypt]` conforme padrão acima.
