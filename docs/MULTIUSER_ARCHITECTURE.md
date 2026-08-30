# Arquitetura multiusuário do Finance 1.0.0

Produção: `Finance Desktop (PySide6) → HTTPS → Finance API (FastAPI) → PostgreSQL`.

O desktop não recebe credenciais do PostgreSQL. A API centraliza autenticação, autorização, validação, auditoria e concorrência. SQLite permanece somente para desenvolvimento e testes isolados.

- `src/app/api_client`: cliente HTTP único, timeout e tokens apenas em memória.
- `src/finance_server`: API 1.0.0, autenticação, RBAC, usuários e auditoria.
- `migrations`: schema atual `20260828_12`.
- `tools/migrate_sqlite_to_postgres.py`: preview, migração explícita e reconciliação.

Com `FINANCE_API_URL`, o login precede a MainWindow. Servidor indisponível bloqueia a operação, evitando base local divergente. O header identifica usuário/perfil e oferece logout.

Lançamentos via `/api/v1/cashflow` registram criador, último editor e versão. Atualização exige `expected_version`; versão obsoleta retorna HTTP 409. A atualização inicial ocorre por consulta/refresh, sem WebSocket.

Health: `/health`. Prefixo: `/api/v1`. Recursos: autenticação, usuários, entidades, fluxo de caixa, BOE, orçamento, metas, ranking, relatórios e auditoria. Permissões são verificadas no servidor.
