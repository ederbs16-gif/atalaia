Você vai criar a estrutura inicial de um projeto desktop chamado Atalaia (sistema de gestão para Cyber e Papelaria Atalaia: papelaria, micrográfica e lan house). Este é o primeiro prompt de uma série; ainda não existe nenhum código no repositório.

CONTEXTO DO SISTEMA
- Aplicação desktop local, rodando em 3 PCs na mesma rede local, com 1 deles hospedando o servidor MySQL e os outros 2 conectando remotamente.
- Módulos previstos para os próximos prompts (a estrutura de pastas deve prever espaço para eles, mas eles ainda não devem ser implementados): Cadastro de Produtos (com estoque), Orçamento, Entrada de Mercadorias, PDV (com cupom não fiscal via ESC/POS), Relatórios gerenciais.

STACK
- Python 3.11+
- Interface: PySide6
- Banco: MySQL, acessado via SQLAlchemy 2.x (engine + ORM declarativo), com Alembic para migrations versionadas. Motivo: o schema vai evoluir em várias etapas ao longo dos próximos módulos e o mesmo servidor MySQL é acessado por 3 PCs diferentes; migrations versionadas evitam schema divergente entre máquinas e ALTER TABLE manual em produção.
- Impressão de cupom: python-escpos (não implementar nesta etapa, só prever a pasta do módulo)
- Empacotamento futuro: PyInstaller (não configurar nesta etapa)

TAREFA

1. Criar a seguinte estrutura de pastas, com __init__.py vazio em cada pacote Python:

atalaia/
├── CLAUDE.md
├── README.md
├── requirements.txt
├── .gitignore
├── .env.example
├── src/
│   └── atalaia/
│       ├── __init__.py
│       ├── main.py
│       ├── config.py
│       ├── db/
│       │   ├── __init__.py
│       │   ├── base.py
│       │   ├── session.py
│       │   └── models/
│       │       └── __init__.py
│       ├── modules/
│       │   ├── produtos/
│       │   ├── orcamento/
│       │   ├── entrada_mercadorias/
│       │   ├── pdv/
│       │   └── relatorios/
│       ├── ui/
│       │   ├── __init__.py
│       │   └── main_window.py
│       └── utils/
│           └── __init__.py
└── tests/
    └── conftest.py

2. As pastas dentro de modules/ ficam vazias por enquanto, sem __init__.py; serão preenchidas em prompts futuros, um módulo por vez.

3. requirements.txt deve conter pelo menos: PySide6, SQLAlchemy, alembic, mysql-connector-python (driver usado pelo SQLAlchemy), python-dotenv, pytest. Não invente números de versão; rode `pip index versions <pacote>` para confirmar a versão estável atual de cada um antes de fixar, ou use `>=` com teto de major version se preferir não fixar exato.

4. config.py carrega a configuração de conexão com o banco (host, porta, usuário, senha, nome do banco) a partir de variáveis de ambiente via python-dotenv. Nunca hardcode credencial. .env.example lista as variáveis esperadas sem valores reais. .gitignore ignora .env, __pycache__, *.pyc, ambiente virtual e artefatos de build do PyInstaller.

5. main.py apenas inicializa a QApplication do PySide6 e abre main_window.py com uma janela vazia (placeholder), título "Atalaia - Cyber e Papelaria". Nenhuma tela funcional ainda.

6. Criar CLAUDE.md na raiz cobrindo: stack técnica completa, convenção de nomenclatura (snake_case para arquivos e classes; tabelas e colunas do banco em português, nomes de tabela no plural, ex: produtos, categorias, usuarios), estrutura de pastas explicada em 1-2 linhas por pasta, comando para rodar a aplicação, comando para rodar testes (pytest), comandos de migration (alembic upgrade head e alembic revision --autogenerate -m "mensagem"), e a regra explícita: nunca commitar .env ou credencial; toda mudança de schema vira migration, nunca ALTER TABLE direto no servidor. Mantenha entre 40 e 80 linhas.

7. README.md com instruções básicas de setup: criar venv, instalar requirements, copiar .env.example para .env, rodar migrations, rodar a aplicação.

CRITÉRIOS DE ACEITE
- Estrutura de pastas criada exatamente como especificado.
- python -m atalaia.main abre uma janela vazia sem erro (assumindo PySide6 instalado).
- pip install -r requirements.txt instala sem conflito em ambiente limpo.
- CLAUDE.md existe, entre 40 e 80 linhas, cobrindo todos os pontos do item 6.
- Nenhuma credencial hardcoded em nenhum arquivo.
- pytest roda sem erro de coleta, mesmo sem testes ainda.

Antes de codar, mostre o plano de arquivos que pretende criar e espere minha aprovação.