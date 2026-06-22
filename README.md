# Atalaia — Sistema de Gestão

Sistema desktop para Cyber e Papelaria Atalaia (papelaria, micrográfica e lan house).

## Pré-requisitos

- Python 3.11+
- Servidor MySQL acessível na rede local

## Setup

### 1. Criar e ativar o ambiente virtual

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate
```

### 2. Instalar dependências

```bash
pip install -r requirements.txt
```

### 3. Configurar variáveis de ambiente

```bash
copy .env.example .env   # Windows
# ou
cp .env.example .env     # Linux/macOS
```

Edite `.env` com as credenciais do servidor MySQL:

```
DB_HOST=192.168.x.x
DB_PORT=3306
DB_USER=seu_usuario
DB_PASSWORD=sua_senha
DB_NAME=atalaia
```

### 4. Rodar migrations

```bash
alembic upgrade head
```

### 5. Rodar a aplicação

```bash
# Windows (PowerShell)
$env:PYTHONPATH = "src"; python -m atalaia.main

# Linux/macOS
PYTHONPATH=src python -m atalaia.main
```

## Testes

```bash
# Windows (PowerShell)
$env:PYTHONPATH = "src"; pytest

# Linux/macOS
PYTHONPATH=src pytest
```
