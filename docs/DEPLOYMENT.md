# Deploy do Finance

## API

Configure fora do Git: `DATABASE_URL=postgresql+psycopg://...`, `SECRET_KEY`, tokens e `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`. Execute Alembic até o head, valide `current/check`, crie o primeiro administrador uma única vez com `BOOTSTRAP_ADMIN_*` e `python -m finance_server.bootstrap`, e inicie `uvicorn finance_server.main:app` atrás de HTTPS. O bootstrap recusa repetição quando já há Administrador.

## Desktop

Configure `FINANCE_API_URL=https://servidor` e timeout. O desktop não deve conter credenciais PostgreSQL.

## Migração controlada

`tools/migrate_sqlite_to_postgres.py` inicia em preview. Exige destino migrado e vazio, backup previamente verificado e autorização. Execução: `--execute --confirm "MIGRAR PARA POSTGRESQL"`; ao final reconcilia contagens. Nenhum dado oficial foi migrado nesta Sprint.

Monitore `/health`, proteja e teste backups, mantenha logs fora do Git e planeje a invalidação de sessões ao rotacionar chaves.
