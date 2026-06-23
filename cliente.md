Carregue @CLAUDE.md antes de começar. Este prompt cria o módulo Clientes completo (model + service + UI), sem histórico de compras por enquanto (depende de Orçamentos e PDV que ainda não existem), e atualiza o menu lateral com o novo item.

CONTEXTO
Clientes serão referenciados por FK em orcamentos e vendas (PDV). O histórico de compras no cadastro do cliente será adicionado em prompt futuro, após Orçamentos e PDV existirem como fonte de dados. CPF/CNPJ é texto livre (mesmo padrão de documento em fornecedores, sem validação de dígitos verificadores).

TAREFA

PARTE 1 — Model e migration

1. Criar src/atalaia/db/models/cliente.py com modelo Cliente (tabela clientes):
   - id: INT, PK, autoincrement
   - nome: VARCHAR(150), NOT NULL
   - telefone: VARCHAR(20), nullable
   - documento: VARCHAR(20), nullable (CPF ou CNPJ, texto livre)
   - ativo: BOOLEAN, NOT NULL, default True (soft-delete)
   - criado_em: DATETIME, NOT NULL, server_default=func.now()
   - atualizado_em: DATETIME, NOT NULL, server_default=func.now(), onupdate=func.now()

   Sem UNIQUE em nome nem documento (mesmo padrão e justificativa de fornecedores). Documentar em docstring.

2. Gerar migration via alembic revision --autogenerate -m "cria tabela clientes". Mostrar conteúdo completo antes de rodar alembic upgrade head. Confirmar down_revision aponta para 9a4823b3ecbf (última migration aplicada).

3. Não rodar alembic upgrade head ainda.

PARTE 2 — Service

4. Criar src/atalaia/modules/clientes/__init__.py (vazio).

5. Criar src/atalaia/modules/clientes/exceptions.py:
   - ClientesError(Exception)
   - ClienteNaoEncontradoError(ClientesError)
   - ClienteInativoError(ClientesError)

6. Criar src/atalaia/modules/clientes/service.py com:
   - criar_cliente(dados: dict) -> Cliente: valida nome não vazio
   - atualizar_cliente(cliente_id: int, dados: dict) -> Cliente
   - inativar_cliente(cliente_id: int) -> None: soft-delete, nunca DELETE físico
   - listar_clientes(apenas_ativos: bool = True) -> list[Cliente]: ordena por nome
   - obter_cliente(cliente_id: int) -> Cliente: levanta ClienteNaoEncontradoError se não existir
   - buscar_clientes_por_termo(termo: str, apenas_ativos: bool = True) -> list[Cliente]: filtra nome OU documento contém termo, case-insensitive, via LIKE no SQL (não list comprehension em memória)

PARTE 3 — UI

7. Criar src/atalaia/modules/clientes/ui/__init__.py (vazio).

8. Criar src/atalaia/modules/clientes/ui/tela_clientes.py com TelaClientes(QWidget):

   Painel de filtros:
   - campo "Buscar" (nome ou documento)
   - combo "Status": Ativos / Inativos / Todos
   - botões "Buscar" e "Limpar"

   Tabela (QTableView + QAbstractTableModel):
   - Colunas: Nome, Telefone, Documento, Status
   - Inativos em texto acinzentado

   Botões de ação:
   - "Novo Cliente": abre FormularioCliente em modo criação
   - "Editar" (habilitado com linha selecionada): abre FormularioCliente em modo edição
   - "Inativar" (habilitado só com ativo selecionado): confirmação + inativar_cliente() + recarrega tabela
   - "Histórico" (habilitado com linha selecionada): por enquanto QMessageBox.information("Em desenvolvimento — disponível após módulo de Orçamentos e PDV")

9. Criar src/atalaia/modules/clientes/ui/formulario_cliente.py com FormularioCliente(QDialog):
   - cliente_id opcional: None = Criar, id = Editar
   - Campos: Nome * (obrigatório), Telefone (opcional), Documento (opcional)
   - Modo Editar: carrega via obter_cliente(id)
   - Salvar: criar_cliente ou atualizar_cliente; nome vazio → QMessageBox.warning sem fechar; erros não mapeados → QMessageBox.critical
   - Botões: Salvar / Cancelar

10. Criar src/atalaia/modules/clientes/ui/dialogo_cliente.py com DialogoCliente(QDialog): versão compacta para uso inline no formulário de orçamento (mesmo padrão de DialogoCategoria e DialogoFornecedor): campos Nome e Telefone apenas, botões Salvar/Cancelar, obter_cliente_criado().

PARTE 4 — Integração no menu lateral

11. Atualizar src/atalaia/ui/main_window.py:
    - Adicionar TelaClientes() ao QStackedWidget
    - Adicionar item "Clientes" no sidebar entre Fornecedores e Entradas, usando clientes.svg
    - Nova ordem: PDV, Produtos, Clientes, Fornecedores, Entradas, Orçamentos, Relatórios, Configurações

PARTE 5 — Testes

12. Criar tests/test_clientes.py cobrindo:
    - criar_cliente com nome vazio levanta ValueError
    - criar_cliente válido com documento None persiste corretamente
    - inativar_cliente seta ativo=False; listar_clientes(apenas_ativos=True) não retorna mais
    - obter_cliente com id inexistente levanta ClienteNaoEncontradoError
    - buscar_clientes_por_termo: termo batendo nome retorna; termo batendo documento retorna; sem correspondência retorna vazio

13. Criar tests/test_ui_clientes.py com pytest-qt:
    - smoke: TelaClientes instancia sem erro
    - smoke: FormularioCliente abre em modo Criar
    - smoke: FormularioCliente abre em modo Editar com cliente existente, campos preenchidos

14. Atualizar CLAUDE.md: adicionar clientes na seção de schema; nota que histórico de compras no cliente será adicionado após Orçamentos e PDV.

CRITÉRIOS DE ACEITE
- Migration com down_revision correto
- buscar_clientes_por_termo usa LIKE via SQL
- Nenhum get_session() direto nos arquivos de UI
- Botão Histórico existe mas abre placeholder
- TelaClientes aparece no menu lateral entre Fornecedores e Entradas
- pytest passa em todos os testes novos e existentes (89 passed, 5 skipped era o estado anterior)

Mostre o plano antes de criar os arquivos.