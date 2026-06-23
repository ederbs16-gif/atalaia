Carregue @CLAUDE.md antes de começar. Este prompt integra todos os módulos prontos no main_window.py com navegação por menu lateral + QStackedWidget, usando ícones SVG.

CONTEXTO
Módulos com UI pronta: Produtos (TelaProdutos), Entrada de Mercadorias (TelaEntradas), Fornecedores (TelaFornecedores).
Módulos ainda não implementados: PDV, Orçamentos, Relatórios, Configurações — aparecem no menu mas abrem placeholder por enquanto.
Ícones SVG disponíveis em: src/atalaia/assets/icons/ (pdv.svg, produtos.svg, fornecedor.svg, entrada.svg, orcamento.svg, relatorios.svg, config.svg, clientes.svg, compras.svg, financeiro.svg, desligar.svg)

TAREFA

1. Reescrever src/atalaia/ui/main_window.py com MainWindow(QMainWindow):

   Layout geral:
   - Layout horizontal fixo: sidebar à esquerda (largura fixa 200px), QStackedWidget ocupando o restante
   - Tamanho mínimo: 1024x600; abre maximizada por padrão
   - Barra de status inferior mostrando nome do módulo ativo

   Menu lateral (sidebar):
   QSS aplicado via setStyleSheet na MainWindow:
   - Fundo sidebar: #1e1e2e
   - Botões: fundo transparente, texto #ffffff, padding 12px, alinhado à esquerda, sem borda, largura total do sidebar
   - Hover: fundo #2a2a3e
   - Item ativo: fundo #313244 + borda esquerda 3px solid #00B89A + texto em negrito

   Cada item do menu é um QPushButton com:
   - Ícone SVG carregado via QIcon(str(Path(__file__).parent.parent / "assets/icons/nome.svg")), tamanho 24x24
   - Texto ao lado do ícone
   - setCheckable(True) para controle de estado ativo

   Itens na ordem:
   🖥 PDV → pdv.svg
   📦 Produtos → produtos.svg
   🏭 Fornecedores → fornecedor.svg
   📥 Entradas → entrada.svg
   📋 Orçamentos → orcamento.svg
   📊 Relatórios → relatorios.svg
   ⚙️ Configurações → config.svg

   Separador visual antes de Configurações (QFrame linha horizontal).

   Botão "Sair" no rodapé do sidebar → desligar.svg; ao clicar, fecha a aplicação via QApplication.quit() com confirmação QMessageBox.question.

   Páginas do QStackedWidget:
   - PDV: placeholder QLabel centralizado "🖥️ PDV\nEm desenvolvimento"
   - Produtos: TelaProdutos()
   - Fornecedores: TelaFornecedores()
   - Entradas: TelaEntradas()
   - Orçamentos: placeholder
   - Relatórios: placeholder
   - Configurações: placeholder

   Ao iniciar, selecionar PDV por padrão.

2. Carregar SVGs com cor branca: SVGs do Material Icons são pretos por padrão. Use QIcon com QPixmap + QPainter para colorir os ícones de branco antes de atribuir ao botão. Crie um helper load_icon(path: str, color: QColor = QColor("white")) -> QIcon reutilizável em src/atalaia/ui/icon_loader.py.

3. Atualizar src/atalaia/main.py para abrir MainWindow maximizada.

4. Smoke tests em tests/test_main_window.py com pytest-qt:
   - MainWindow instancia sem erro
   - Clicar em Produtos troca para TelaProdutos no QStackedWidget
   - Clicar em Fornecedores troca para TelaFornecedores
   - Clicar em Entradas troca para TelaEntradas
   - Botão Sair existe no sidebar

CRITÉRIOS DE ACEITE
- Janela abre maximizada com sidebar visível e PDV selecionado por padrão
- Ícones SVG aparecem brancos no sidebar (não pretos)
- Item ativo tem borda esquerda #00B89A e fundo #313244
- Hover funciona via QSS
- Navegação entre módulos prontos funciona sem erro
- pytest passa em todos os testes (84 passed, 5 skipped era o estado anterior)

Mostre o plano antes de criar os arquivos.