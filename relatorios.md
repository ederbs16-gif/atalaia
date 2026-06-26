Carregue @CLAUDE.md antes de começar. Este prompt cria o módulo Relatórios completo. Todas as tabelas de dados já existem em produção (vendas, itens_venda, produtos, caixas, contas_pagar, contas_receber). Última migration: ab7ff4570cf0.

CONTEXTO
- Relatórios com gráficos (matplotlib) + tabelas
- Visualização na tela + impressão via QPrinter + exportação para PDF
- Filtros de período: Diário, Semanal, Mensal, Período personalizado
- 5 relatórios: Vendas por Período, Produtos Mais Vendidos, Estoque Baixo, Fluxo de Caixa, Contas a Pagar/Receber

PARTE 1 — Service de dados

1. Criar src/atalaia/modules/relatorios/__init__.py (vazio).

2. Criar src/atalaia/modules/relatorios/queries.py com funções de consulta puras (só leitura, sem side effects), todas recebendo data_inicio e data_fim como parâmetros:

   - vendas_por_periodo(data_inicio: date, data_fim: date) -> dict:
     Retorna: total_vendas (count), valor_bruto, valor_desconto, valor_liquido, ticket_medio, agrupado_por_dia (list[dict] com data e valor para o gráfico de linha)

   - produtos_mais_vendidos(data_inicio: date, data_fim: date, limit: int = 10) -> list[dict]:
     JOIN itens_venda → vendas (status='finalizada') → produtos
     Retorna: lista de {nome, quantidade_total, valor_total, categoria} ordenada por quantidade_total desc

   - estoque_baixo() -> list[dict]:
     Produtos onde estoque_atual <= estoque_minimo e ativo=True
     Retorna: lista de {nome, categoria, estoque_atual, estoque_minimo, diferenca}
     Sem filtro de período (é foto atual do estoque)

   - fluxo_de_caixa(data_inicio: date, data_fim: date) -> dict:
     Entradas: soma de pagamentos_venda por forma no período
     Saídas: soma de pagamentos_conta_pagar no período
     Retorna: {entradas_total, saidas_total, saldo, por_forma: {dinheiro, pix, debito, credito}, por_dia: list[dict] para gráfico}

   - contas_a_pagar_receber(data_inicio: date, data_fim: date) -> dict:
     Retorna: {
       pagar: {total_pendente, total_vencido, total_pago, itens: list[dict]},
       receber: {total_pendente, total_vencido, total_pago, itens: list[dict]}
     }
     Vencido = vencimento < hoje e status != 'pago'

3. Criar src/atalaia/modules/relatorios/periodo.py com helper:
   - calcular_periodo(tipo: str) -> tuple[date, date]:
     tipos: 'diario' (hoje), 'semanal' (últimos 7 dias), 'mensal' (mês atual), 'personalizado' (retorna None, None — UI fornece as datas)

PARTE 2 — UI

4. Criar src/atalaia/modules/relatorios/ui/__init__.py (vazio).

5. Criar src/atalaia/modules/relatorios/ui/tela_relatorios.py com TelaRelatorios(QWidget):

   Layout com QTabWidget com 5 abas:
   - 📈 Vendas
   - 🏆 Mais Vendidos
   - 📦 Estoque Baixo
   - 💰 Fluxo de Caixa
   - 📋 Contas

   Cada aba tem:
   - Painel de filtro no topo: botões rápidos (Hoje / Semana / Mês) + QDateEdit De/Até para período personalizado + botão "Gerar"
   - Área de conteúdo com gráfico matplotlib (FigureCanvasQTAgg) + tabela QTableView abaixo
   - Rodapé com botões "🖨️ Imprimir" e "📄 Exportar PDF"

   Aba Vendas:
   - Gráfico de linha: valor líquido por dia no período
   - Tabela: Data, Qtd Vendas, Valor Bruto, Desconto, Valor Líquido
   - Cards de resumo no topo: Total Vendas, Valor Líquido, Ticket Médio

   Aba Mais Vendidos:
   - Gráfico de barras horizontais: top 10 produtos por quantidade
   - Tabela: Produto, Categoria, Qtd Vendida, Valor Total

   Aba Estoque Baixo:
   - Sem gráfico (é foto atual, sem período)
   - Tabela: Produto, Categoria, Estoque Atual, Estoque Mínimo, Diferença
   - Diferença negativa em vermelho, zero em amarelo
   - Botão "Gerar Sugestão de Compra" (exporta lista para PDF com quantidades sugeridas)

   Aba Fluxo de Caixa:
   - Gráfico de barras empilhadas: entradas vs saídas por dia
   - Cards: Total Entradas, Total Saídas, Saldo do Período
   - Tabela por forma de pagamento: Dinheiro, PIX, Débito, Crédito

   Aba Contas:
   - Dois painéis lado a lado: Contas a Pagar | Contas a Receber
   - Cada painel: cards (Pendente, Vencido, Pago) + tabela com status colorido

6. Criar src/atalaia/modules/relatorios/ui/exportador.py com:
   - imprimir_relatorio(widget: QWidget, titulo: str) -> None:
     Usa QPrinter + QPrintDialog (diálogo nativo Windows), renderiza o widget via QPainter
   - exportar_pdf(widget: QWidget, titulo: str, caminho: str | None = None) -> None:
     Abre QFileDialog para escolher onde salvar, usa QPrinter com OutputFormat.PdfFormat
   - exportar_sugestao_compra(itens: list[dict]) -> None:
     Gera PDF com lista de produtos abaixo do estoque mínimo + quantidade sugerida (estoque_minimo - estoque_atual + margem de 20%)

7. Adicionar matplotlib ao requirements.txt. Usar matplotlib.backends.backend_qtagg.FigureCanvasQTAgg para embedar gráficos no PySide6.

8. Atualizar main_window.py: substituir placeholder de Relatórios por TelaRelatorios().

PARTE 3 — Testes

9. Criar tests/test_relatorios_queries.py:
   - vendas_por_periodo: período sem vendas retorna zeros, não erro
   - produtos_mais_vendidos: retorna ordenado por quantidade desc
   - estoque_baixo: produto com estoque_atual <= estoque_minimo aparece; produto com estoque ok não aparece
   - fluxo_de_caixa: soma de pagamentos por forma calculada corretamente
   - calcular_periodo: 'diario' retorna hoje, 'semanal' retorna 7 dias atrás até hoje, 'mensal' retorna primeiro dia do mês até hoje

10. Criar tests/test_ui_relatorios.py (pytest-qt, --timeout=60):
    - smoke: TelaRelatorios instancia sem erro
    - smoke: todas as 5 abas existem no QTabWidget
    - smoke: gerar relatório de vendas com período vazio não levanta exceção (retorna tabela vazia)

CRITÉRIOS DE ACEITE
- Nenhuma query SQL direta em arquivos de UI (sempre via queries.py)
- Gráficos matplotlib renderizam sem erro mesmo com dados vazios (período sem vendas)
- Exportar PDF abre diálogo de salvar arquivo
- Imprimir abre diálogo de impressora do Windows
- pytest passa em todos os testes novos e existentes (129 passed, 5 skipped era o estado anterior)

Mostre o plano antes de criar os arquivos.