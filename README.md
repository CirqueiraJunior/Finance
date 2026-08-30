# Finance

Produto Finance 1.0.0 da J.A. Technology. A pré-release multiusuário usa PySide6 → HTTPS/FastAPI → PostgreSQL; SQLite é restrito a desenvolvimento e testes. Consulte `docs/MULTIUSER_ARCHITECTURE.md`, `docs/SECURITY.md` e `docs/DEPLOYMENT.md`.

Aplicativo desktop profissional para substituir as planilhas de Controle
Financeiro, Meta x Realizado e BOE utilizadas pelo CESPC/GO.

Versão atual: **1.0.0**. A Release 1.0 reúne Dashboard, Financeiro, Orçamento,
BOE, Metas, Cadastros, Relatórios, Administração, CSV, backup e importação
histórica controlada com preview.

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

```powershell
alembic current
alembic revision --autogenerate -m "descricao"
alembic upgrade head
```

O head da Release 1.0 é `20260827_09`. Nunca altere migrations anteriores.

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
- [Manual do Usuário](docs/USER_MANUAL.md)
- [Manual Técnico](docs/TECHNICAL_MANUAL.md)
- [Playbook](docs/PLAYBOOK.md)
- [Release 1.0](docs/RELEASE_1_0.md)
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

## Release 1.0

Workspace oficial: `C:\Users\jose.alves\J.A. Technology\Finance`.
Venv oficial: `C:\Users\jose.alves\.venvs\Finance`.
Consulte `docs/RELEASE_1_0.md` para escopo, validações e limitações.
