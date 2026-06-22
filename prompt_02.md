Este prompt assume que a estrutura de pastas do prompt anterior já existe (CLAUDE.md, src/atalaia/db/, requirements.txt). Carregue @CLAUDE.md antes de começar para seguir as convenções já definidas. Alembic ainda não foi inicializado.

TAREFA

1. Em src/atalaia/db/base.py, criar a Base declarativa do SQLAlchemy 2.x (DeclarativeBase). Em src/atalaia/db/session.py, criar o engine (lendo a string de conexão de config.py) e uma função get_session() que retorna uma sessão via context manager, para ser reutilizada por todos os módulos futuros sem duplicar lógica de conexão.

2. Inicializar o Alembic na raiz do projeto (alembic init alembic). Configurar alembic.ini e alembic/env.py para ler a URL de conexão de config.py (não duplicar a lógica de conexão que já existe) e apontar para a Base de db/base.py, para que autogenerate funcione.

3. Criar dois modelos cross-cutting em src/atalaia/db/models/, um arquivo por entidade:

   - Usuario (tabela usuarios): id (PK, auto-increment), nome (string, obrigatório), login (string, único, obrigatório), senha_hash (string, obrigatório; usar passlib com bcrypt para gerar o hash, nunca armazenar senha em texto puro), perfil (enum: 'admin', 'operador'), ativo (boolean, default True), criado_em (datetime, default now).

   - Configuracao (tabela configuracoes): id (PK), chave (string, único, ex: 'nome_loja', 'cnpj', 'endereco', 'telefone'), valor (string). Modelo chave-valor simples para os dados que aparecem no cabeçalho de cupom e orçamento.

4. Adicionar passlib[bcrypt] ao requirements.txt.

5. Gerar a primeira migration com Alembic (alembic revision --autogenerate -m "cria tabelas usuarios e configuracoes") e confirmar que ela cria as duas tabelas com os constraints corretos, incluindo único em login e em chave.

6. Criar tests/test_db_connection.py com um teste que abre e fecha uma sessão via get_session() sem erro. Documente no próprio teste se está usando SQLite em memória ou um banco MySQL de teste, e por quê.

CRITÉRIOS DE ACEITE
- alembic upgrade head roda sem erro contra um MySQL vazio e cria usuarios e configuracoes com os campos especificados.
- Nenhuma senha em texto puro em código ou teste.
- get_session() é reutilizável pelos módulos futuros sem duplicar lógica.
- pytest passa, incluindo o teste de conexão.
- Atualize o CLAUDE.md acrescentando a convenção de hash de senha e o padrão de uso de get_session(), se ainda não estiver coberto.

Rode os testes existentes antes de considerar a tarefa concluída.