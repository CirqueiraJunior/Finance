# J.A. Finance

Aplicativo desktop em construção para substituir as planilhas de Controle
Financeiro, Meta x Realizado e BOE utilizadas pelo CESPC/GO.

Esta versão (`0.1.0`) contém apenas a fundação da Sprint 01. Não contém regras de
negócio, CRUD, importação, exportação nem estrutura definitiva do banco.

## Requisitos

- Python 3.13
- Git
- PostgreSQL apenas para o futuro ambiente de produção

## Preparação do ambiente

No PowerShell:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Edite `.env` se necessário. O padrão usa SQLite:

```dotenv
DATABASE_URL=sqlite:///./ja_finance.db
```

Para PostgreSQL, a URL segue este formato:

```dotenv
DATABASE_URL=postgresql+psycopg://usuario:senha@host:5432/ja_finance
```

## Executar

```powershell
ja-finance
```

Alternativamente:

```powershell
python -m app.main
```

## Testes

```powershell
pytest
```

## Migrações

O Alembic está configurado, mas não há tabelas ou revisões de negócio nesta
sprint.

```powershell
alembic current
alembic revision --autogenerate -m "descricao"
alembic upgrade head
```

Só crie revisões quando os modelos tiverem sido aprovados para uma sprint futura.

## Arquitetura

O fluxo planejado é:

```text
View -> Controller -> Service -> Repository -> Model/Database
```

A interface não acessa diretamente o banco. Controllers coordenam eventos,
services concentrarão casos de uso e repositories isolarão a persistência.

Consulte:

- [Arquitetura](docs/ARCHITECTURE.md)
- [Estrutura](docs/STRUCTURE.md)
- [Registro da Sprint 01](docs/SPRINT_01.md)
- [Backlog](docs/BACKLOG.md)

## Configuração

| Variável | Padrão | Finalidade |
|---|---|---|
| `APP_NAME` | `J.A. Finance` | Nome da aplicação |
| `APP_ENV` | `development` | Identificação do ambiente |
| `APP_DEBUG` | `false` | Sinalizador de diagnóstico |
| `DATABASE_URL` | SQLite local | Conexão SQLAlchemy |
| `LOG_LEVEL` | `INFO` | Nível mínimo de log |
| `LOG_DIR` | `logs` | Diretório de logs |

## Estado da Sprint 01

Entregue: infraestrutura, shell visual, navegação e placeholders. O escopo
funcional das planilhas permanece intencionalmente no backlog para levantamento
e planejamento da Sprint 02.

## Status da Sprint 01

APROVADA em 24/08/2026.

Ambiente homologado:
- Python 3.13.15
- Venv: C:\Users\jose.alves\.venvs\Finance
- Workspace: C:\Users\jose.alves\J.A. Technology\Finance
- Testes: 5 passed in 0.94s

A Sprint 01 contem apenas a fundacao tecnica. Nenhuma regra de negocio da Sprint 02 foi iniciada.
