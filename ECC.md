Carregue @CLAUDE.md antes de começar. Este prompt NÃO altera nada no projeto Atalaia ainda; é só investigação.

CONTEXTO
Existe um repositório de referência clonado localmente em C:\adocao_refs\ECC (Everything Claude Code), um framework de configuração para Claude Code com subagentes, skills, hooks e regras. Quero adotar SELETIVAMENTE peças dele que façam sentido para este projeto (Python 3.11, PySide6, MySQL via SQLAlchemy, sem stack web), não instalar o framework inteiro. NÃO use /plugin marketplace add nem /plugin install; isso traz hooks, scripts de detecção de gerenciador de pacote JS (npm/pnpm/bun) e regras voltadas a TypeScript/web que não se aplicam aqui. A pasta C:\adocao_refs\ECC é só referência de leitura; nunca escreva ou modifique nada lá dentro.

TAREFA

1. Use um subagente (read-only, tipo Explore) para investigar C:\adocao_refs\ECC e responder, sem trazer o conteúdo bruto de cada arquivo para a conversa principal, só o resumo:

   a. Existe algum agente de code review específico ou adaptável para Python (procure em agents/, pode ter nome como python-reviewer, code-reviewer genérico com seção Python, ou similar)? Se sim, qual o caminho do arquivo e um resumo de 3-4 linhas do que ele cobre.

   b. Existe algum agente de resolução de erro de build/teste (build-error-resolver ou equivalente)? Mesmo formato de resposta.

   c. Existe algum agente de planejamento/arquitetura (planner, architect)? Resumo do que ele cobre e se depende de ferramentas ou convenções específicas de stack web que não se aplicam aqui.

   d. Existe alguma regra (rules/) específica de Python (rules/python/ ou equivalente) que seja agnóstica o suficiente para servir de inspiração (ex: convenção de tratamento de erro, validação de entrada), sem depender de ferramenta JS?

   d. Liste a estrutura de frontmatter (campos YAML) usada nos arquivos de agente do ECC, para eu confirmar se é compatível com o formato oficial do Claude Code (name, description, tools, model) ou se usa campos próprios que precisariam ser removidos na adaptação.

2. Com base nisso, NÃO copie nada ainda. Em vez disso, proponha um plano específico:
   - Quais 1 a 3 arquivos de agente valem a pena adaptar e copiar para .claude/agents/ no projeto Atalaia (nome de arquivo de destino, ex: .claude/agents/python-reviewer.md).
   - Para cada um, que ajustes seriam necessários: remover dependência de ferramenta JS/web se houver, ajustar o prompt para as convenções já documentadas em CLAUDE.md (estoque atômico, soft-delete, naming_convention, sessão curta com joinedload), e qual valor de model usar no frontmatter (sugira haiku para revisão de primeira passada/lint, sonnet para qualquer agente que vá propor mudança de código ou decisão de arquitetura).
   - Se algum candidato não valer a pena adaptar (ex: dependência forte demais de stack web, ou redundante com o Plan Mode que já uso), diga isso explicitamente em vez de forçar encaixe.

CRITÉRIO DE ACEITE
- Nenhum arquivo é criado, copiado ou modificado nesta etapa, nem dentro de C:\adocao_refs\ECC nem dentro do projeto Atalaia.
- A resposta traz um plano concreto e específico (nomes de arquivo, ajustes necessários, valor de model sugerido), não uma descrição genérica do que o ECC oferece.

Aguarde minha aprovação do plano antes de criar qualquer arquivo em .claude/agents/.