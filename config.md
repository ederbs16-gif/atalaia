Carregue @CLAUDE.md antes de começar. Este prompt cria o módulo Configurações completo. Arquitetura híbrida: dados de negócio no banco MySQL (compartilhado), preferências locais no config.ini (por PC). Última migration: ab7ff4570cf0.

CONTEXTO
- Tabela configuracoes já existe com chave/valor
- config.ini é arquivo local por PC, no .gitignore, ao lado do .env
- Senha do programador: hash bcrypt "$2b$12$ltnUoYWLEe9QPEzhI/P1nOJlFB.tnTBVLxEqi4yk60hnJ9wWWMGdS" — nunca expor a senha original no código, só o hash
- mysqldump.exe será incluído no pacote de instalação em tools/mysqldump.exe
- Backup automático diário às 18:00 via QTimer
- PIX: dados para geração de QR Code estático (padrão EMV/BR Code)

PARTE 1 — ConfigLocal (arquivo config.ini)

1. Criar src/atalaia/config_local.py com ConfigLocal (singleton):
   - Lê/escreve config.ini usando configparser
   - Caminho: raiz do projeto (mesmo nível do .env)
   - Cria config.ini com valores padrão se não existir:

   [interface]
   fonte_tamanho_geral = 11
   fonte_tamanho_pdv = 14
   fonte_tamanho_titulo = 16
   campo_altura_minima = 30

   [impressora]
   escpos_ativada = false
   escpos_porta =
   escpos_modelo =

   [banco]
   host = localhost
   porta = 3306
   usuario = atalaia_app
   senha =

   [backup]
   pasta_destino =
   horario_automatico = 18:00
   backup_automatico = true

   [sistema]
   mysqldump_path = tools/mysqldump.exe

   - Métodos: get(secao, chave, fallback), set(secao, chave, valor), save()
   - instancia() → singleton

2. Atualizar src/atalaia/main.py:
   - Carregar ConfigLocal antes de criar MainWindow
   - Aplicar QSS global baseado nos valores:

   fonte = config.get('interface', 'fonte_tamanho_geral', '11')
   altura = config.get('interface', 'campo_altura_minima', '30')

   app.setStyleSheet(f"""
       QWidget {{ font-size: {fonte}px; }}
       QPushButton {{ font-size: {fonte}px; min-height: {altura}px; padding: 4px 12px; }}
       QLineEdit {{ font-size: {fonte}px; min-height: {altura}px; }}
       QComboBox {{ font-size: {fonte}px; min-height: {altura}px; }}
       QSpinBox {{ font-size: {fonte}px; min-height: {altura}px; }}
       QDoubleSpinBox {{ font-size: {fonte}px; min-height: {altura}px; }}
       QTableView {{ font-size: {int(fonte)-1}px; }}
       QTabBar::tab {{ font-size: {fonte}px; min-height: {altura}px; padding: 4px 16px; }}
       QGroupBox {{ font-size: {fonte}px; }}
   """)

PARTE 2 — Service de configurações da empresa

3. Criar src/atalaia/modules/configuracoes/__init__.py (vazio).

4. Criar src/atalaia/modules/configuracoes/service.py:
   - get_config(chave: str, default: str = '') -> str
   - set_config(chave: str, valor: str) -> None (upsert)
   - get_configs_empresa() -> dict
   - get_configs_pix() -> dict
   - get_configs_sistema() -> dict
   - inicializar_configs_padrao() -> None: insere chaves padrão se não existirem:
     Empresa: nome_empresa='', cnpj='', endereco='', telefone='', email='', site='', logo_path=''
     PIX: pix_tipo_chave='', pix_chave='', pix_nome_recebedor='', pix_cidade='', pix_descricao=''
     Sistema: validade_orcamento_dias='10', caixa_individual='false', desconto_maximo_global='100'

PARTE 3 — Serviço de Backup

5. Criar src/atalaia/modules/configuracoes/backup_service.py:

   - gerar_backup() -> str: (retorna caminho do arquivo gerado)
     * Lê pasta_destino do config.ini (erro se não configurada)
     * Nome do arquivo: atalaia_backup_YYYYMMDD_HHMMSS.sql.zip
     * Executa mysqldump via subprocess:
       mysqldump_path = config.get('sistema', 'mysqldump_path', 'tools/mysqldump.exe')
       Comando: [mysqldump_path, -h host, -P porta, -u usuario, -pSENHA, DB_NAME]
       Lê DB_NAME, host, porta, usuario, senha do .env (via config.py já existente)
     * Comprime o .sql em .zip com zipfile
     * Retorna caminho do arquivo gerado

   - restaurar_backup(caminho_zip: str) -> None:
     * PROTEGIDO: verificar hash bcrypt da senha antes de executar
     * SENHA_HASH = "$2b$12$ltnUoYWLEe9QPEzhI/P1nOJlFB.tnTBVLxEqi4yk60hnJ9wWWMGdS"
     * Extrai o .zip, executa mysql (não mysqldump) para restaurar
     * Aviso: operação destrutiva, sobrescreve o banco atual

   - verificar_senha_programador(senha: str) -> bool:
     * Usa passlib.context.CryptContext(schemes=['bcrypt'])
     * Compara contra SENHA_HASH hardcoded
     * Nunca loga nem expõe o hash em mensagens de erro

   - agendar_backup_automatico(app: QApplication) -> QTimer:
     * Cria QTimer que dispara às 18:00 diariamente
     * Calcula ms até o próximo horário das 18:00
     * Ao disparar: chama gerar_backup() silenciosamente; erro vai para log, não interrompe o sistema

PARTE 4 — Busca de servidor na rede

6. Criar src/atalaia/modules/configuracoes/network_scanner.py:
   - scan_mysql_servers(timeout: float = 0.5) -> list[str]:
     * Varre a subnet local (detecta automaticamente via socket/netifaces)
     * Para cada IP, tenta conectar na porta 3306 com timeout
     * Retorna lista de IPs que respondem na porta 3306
     * Roda em thread separada (QThread) para não travar a UI

PARTE 5 — UI

7. Criar src/atalaia/modules/configuracoes/ui/__init__.py (vazio).

8. Criar src/atalaia/modules/configuracoes/ui/tela_configuracoes.py com TelaConfiguracoes(QWidget):

   QTabWidget com 5 abas:

   ABA 1 — "🏢 Empresa" (banco MySQL):
   - Nome da empresa * (obrigatório)
   - CNPJ (texto livre)
   - Endereço, Telefone, Email, Site
   - Logo: campo path + botão "Selecionar..." (QFileDialog PNG/JPG/SVG)
     Preview da logo (QLabel QPixmap, max 200x100px)
   - Botão "Salvar Dados da Empresa"

   ABA 2 — "💳 PIX" (banco MySQL):
   - Tipo de chave: QComboBox (CPF, CNPJ, Email, Telefone, Chave Aleatória)
   - Chave PIX (campo texto)
   - Nome do Recebedor *
   - Cidade *
   - Descrição (opcional, aparece no QR Code)
   - Preview do payload PIX (QLabel read-only mostrando o BR Code gerado)
   - Botão "Salvar PIX"
   - Gerar payload via função _gerar_payload_pix() usando o padrão EMV/BR Code:
     implementar manualmente (sem biblioteca externa):
     campos obrigatórios: 00 (payload format), 26 (merchant account), 52 (MCC=0000),
     53 (currency=986), 59 (nome), 60 (cidade), 62 (txid), CRC16

   ABA 3 — "🖥️ Interface" (config.ini local):
   - Fonte geral (QSpinBox 8-20, default 11)
   - Fonte PDV (QSpinBox 10-24, default 14)
   - Fonte títulos (QSpinBox 10-24, default 16)
   - Altura mínima de campos (QSpinBox 24-50, default 30)
   - Preview ao vivo: QLabel e QLineEdit de exemplo atualizados em tempo real
   - Botão "Salvar Interface" → salva config.ini + QMessageBox "Reinicie o sistema para aplicar"

   ABA 4 — "🖨️ Impressora ESC/POS" (config.ini local):
   - Checkbox "Impressora ESC/POS ativada"
   - Porta (QLineEdit, ex: COM3) — habilitado só se ativada
   - Modelo (QComboBox: EPSON_TM20, BEMATECH_MP4200, CUSTOM)
   - Botão "Testar" → QMessageBox "Em desenvolvimento"
   - Botão "Salvar Impressora"

   ABA 5 — "🔧 Sistema" (PROTEGIDA por senha do programador):
   - Ao clicar na aba: QInputDialog.getText pedindo senha
   - Se senha incorreta (verificar_senha_programador()): volta para aba anterior + QMessageBox.warning
   - Se correta: exibe o conteúdo da aba normalmente

   Conteúdo da aba Sistema (após autenticação):

   Seção "Conexão com Banco":
   - Host (QLineEdit, lê do config.ini [banco])
   - Porta (QSpinBox 1-65535, default 3306)
   - Usuário, Senha
   - Botão "Buscar Servidores na Rede": abre QProgressDialog, roda NetworkScanner em QThread,
     ao terminar mostra lista de IPs encontrados em QListWidget, duplo clique preenche o Host
   - Botão "Testar Conexão": tenta conectar com os dados informados, QMessageBox sucesso/erro
   - Botão "Salvar Conexão": salva no config.ini (aviso: requer reinicialização)

   Seção "Backup":
   - Pasta destino: QLineEdit + botão "Selecionar..." (QFileDialog.getExistingDirectory)
   - Backup automático: checkbox + QTimeEdit (default 18:00)
   - Botão "Fazer Backup Agora": chama gerar_backup(), QMessageBox com caminho do arquivo gerado
   - Botão "Restaurar Backup" (vermelho): pede senha novamente (mesmo já estando na aba),
     QFileDialog para selecionar .zip, confirmação "ATENÇÃO: esta operação sobrescreve o banco atual",
     chama restaurar_backup()
   - Lista dos últimos 5 backups na pasta configurada (nome + data + tamanho)

   Seção "Parâmetros do Sistema":
   - Validade padrão orçamento (dias, QSpinBox)
   - Desconto máximo global % (QSpinBox 0-100)
   - Caixa individual por PC (checkbox)
   - Botão "Salvar Parâmetros"

9. Atualizar main_window.py:
   - Substituir placeholder de Configurações por TelaConfiguracoes()
   - No __init__, após criar a janela: inicializar_configs_padrao() e agendar_backup_automatico()

PARTE 6 — Testes

10. Criar tests/test_config_local.py:
    - ConfigLocal cria config.ini com valores padrão se não existir
    - get() retorna valor após set() + save()
    - get() retorna fallback para chave inexistente
    - instancia() retorna singleton

11. Criar tests/test_configuracoes_service.py:
    - get_config/set_config funcionam corretamente
    - inicializar_configs_padrao() cria todas as chaves esperadas
    - get_configs_pix() retorna dict com todas as chaves PIX

12. Criar tests/test_backup_service.py:
    - verificar_senha_programador('9qmid950') retorna True
    - verificar_senha_programador('senha_errada') retorna False
    - gerar_backup() com mysqldump_path inexistente levanta FileNotFoundError com mensagem clara

    ATENÇÃO: não incluir a senha '9qmid950' em texto puro no arquivo de teste.
    Use uma variável de ambiente ou leia de um arquivo .env.test para o teste de senha correta.
    O teste de senha incorreta pode usar qualquer string, sem problema.

13. Criar tests/test_ui_configuracoes.py (pytest-qt, --timeout=60):
    - smoke: TelaConfiguracoes instancia sem erro, 5 abas presentes
    - smoke: aba Empresa carrega campos do banco
    - aba Sistema exige senha antes de mostrar conteúdo

14. Atualizar CLAUDE.md:
    - Arquitetura híbrida banco + config.ini documentada
    - Chaves padrão de configuracoes listadas
    - Senha do programador: apenas o hash, nunca a senha original

CRITÉRIOS DE ACEITE
- config.ini criado automaticamente com valores padrão na primeira execução
- QSS global aplicado no main.py antes de criar MainWindow
- Aba Sistema protegida por senha (hash bcrypt, nunca texto puro no código)
- Backup gera arquivo .sql.zip na pasta configurada
- Busca de servidores roda em QThread sem travar UI
- Payload PIX gerado com CRC16 correto (padrão EMV/BR Code)
- pytest passa em todos os testes novos e existentes (145 passed, 5 skipped)

Mostre o plano antes de criar os arquivos.