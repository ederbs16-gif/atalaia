Carregue @CLAUDE.md antes de começar. Fornecedor já tem model, service (criar_fornecedor, atualizar_fornecedor, inativar_fornecedor, listar_fornecedores, obter_fornecedor) e testes prontos. Este prompt cria a UI completa de gestão de fornecedores.

TAREFA

1. Criar src/atalaia/modules/entrada_mercadorias/ui/tela_fornecedores.py com TelaFornecedores(QWidget):

   Painel de filtros no topo:
   - campo de texto "Buscar" (filtra por nome ou documento, case-insensitive, contém)
   - combo "Status": Ativos / Inativos / Todos
   - botão "Buscar" e botão "Limpar"

   Tabela de resultados (QTableView + QAbstractTableModel, mesmo padrão de tela_produtos.py e tela_entradas.py):
   - Colunas: Nome, Documento, Telefone, Email, Status
   - Fornecedores inativos com texto acinzentado (mesmo padrão visual de produtos inativos)

   Botões de ação:
   - "Novo Fornecedor": abre FormularioFornecedor em modo criação
   - "Editar" (habilitado com linha selecionada): abre FormularioFornecedor em modo edição
   - "Inativar" (habilitado só com fornecedor ativo selecionado): pede confirmação via QMessageBox.question, chama fornecedor_service.inativar_fornecedor(id), recarrega tabela

   A busca por texto filtra nome (contém) e documento (contém), combinados com OR: retorna fornecedor se nome OU documento bater com o termo. Implementar como função separada e testável buscar_fornecedores_por_termo(termo, apenas_ativos) em fornecedor_service.py, não inline no widget.

2. Criar src/atalaia/modules/entrada_mercadorias/ui/formulario_fornecedor.py com FormularioFornecedor(QDialog):
   - Aceita fornecedor_id opcional: None = modo Criar, id = modo Editar
   - Campos: Nome * (obrigatório), Documento (opcional), Telefone (opcional), Email (opcional), Observações (opcional, multilinha)
   - Modo Editar: carrega dados via fornecedor_service.obter_fornecedor(id) antes de exibir
   - Salvar: chama criar_fornecedor ou atualizar_fornecedor conforme o modo; nome vazio capturado como QMessageBox.warning sem fechar; erros não mapeados via QMessageBox.critical
   - Botões: Salvar / Cancelar

   Nota: DialogoFornecedor em dialogo_fornecedor.py já existe (usado no "+" da entrada de mercadoria) e não deve ser removido nem alterado. FormularioFornecedor é a versão completa para gestão independente; DialogoFornecedor é o atalho rápido inline.

3. Adicionar buscar_fornecedores_por_termo(termo: str, apenas_ativos: bool = True) -> list[Fornecedor] em fornecedor_service.py: filtra por nome contém OU documento contém, case-insensitive, usando LIKE via SQLAlchemy (não list comprehension em memória).

4. Testes em tests/test_ui_fornecedores.py com pytest-qt:
   - smoke: TelaFornecedores instancia sem erro, combo de status populado
   - smoke: FormularioFornecedor abre em modo Criar sem erro
   - smoke: FormularioFornecedor abre em modo Editar com fornecedor existente, campos preenchidos
   - buscar_fornecedores_por_termo: termo batendo nome retorna fornecedor; termo batendo documento retorna fornecedor; termo sem correspondência retorna lista vazia; apenas_ativos=False inclui inativos

5. Atualizar CLAUDE.md adicionando buscar_fornecedores_por_termo na documentação do módulo.

CRITÉRIOS DE ACEITE
- Nenhum get_session() direto em tela_fornecedores.py ou formulario_fornecedor.py
- buscar_fornecedores_por_termo usa LIKE via SQL, não filtro em memória
- Inativar pede confirmação e atualiza tabela
- FormularioFornecedor modo Editar carrega dados existentes corretamente
- pytest passa em todos os testes novos e existentes

Mostre o plano antes de criar os arquivos.