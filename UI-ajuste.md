Carregue @CLAUDE.md antes de começar. Este prompt aplica dois ajustes visuais/funcionais identificados na revisão das telas.

AJUSTE 1 — formulario_produto.py: reposicionar Código de Barras

Mova o campo "Código de Barras" para antes do campo "Nome" no layout do formulário. A ordem nova fica:
1. Código de Barras (opcional)
2. Nome * (obrigatório)
3. Descrição
4. ... restante sem alteração

A lógica de validação e o dict de dados não mudam, só a posição visual no layout.

AJUSTE 2 — formulario_entrada.py: produto não encontrado na busca

Quando o usuário buscar um produto (por nome ou código de barras) e a busca retornar lista vazia, em vez de simplesmente não preencher o combo de seleção, exibir QMessageBox.question com a mensagem:

"Produto não encontrado. Deseja cadastrar um novo produto agora?"

Botões: Sim / Não.

- Se Não: fecha o QMessageBox e limpa o campo de busca, permitindo nova tentativa.
- Se Sim: abre FormularioProduto(produto_id=None, parent=self) sobreposto ao FormularioEntrada (modal). Ao fechar o FormularioProduto com sucesso (produto_salvo=True):
  - Recuperar o produto recém-criado via service.buscar_por_codigo_barras(codigo) ou service.listar_produtos() filtrando pelo nome que foi digitado na busca — use o método mais confiável disponível no service existente
  - Preencher automaticamente o combo de seleção de produto com o produto recém-cadastrado
  - Preencher o campo Custo Unitário com produto.preco_custo se existir
  - Colocar foco no campo Quantidade para o operador continuar o lançamento sem clique extra

A tela de cadastro de produto abre sobre a entrada de mercadoria sem fechar nem desabilitar a entrada; ao salvar o produto, o controle volta para a entrada com o produto já selecionado.

CRITÉRIOS DE ACEITE
- Campo Código de Barras aparece antes de Nome no formulário de produto (visual confirmado)
- Busca sem resultado na entrada oferece opção de cadastrar
- Após cadastro via fluxo integrado, produto aparece selecionado no combo e custo unitário preenchido automaticamente
- Nenhuma mudança de comportamento nos testes existentes
- pytest passa em todos os testes (rodar após os ajustes)

Mostre quais trechos de código serão alterados antes de aplicar.