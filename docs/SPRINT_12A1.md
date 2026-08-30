# Sprint 12.A.1 — Centralização multiusuário

Status técnico: **APTO PARA HOMOLOGAÇÃO** em 29/08/2026.

## Resultado

Com `FINANCE_API_URL` configurada, o Desktop utiliza exclusivamente adapters HTTP. O `MainWindow` não cria sessão nem repositories SQLite. O modo local continua usando os services e repositories homologados.

Foram centralizados Financeiro, aplicações/resgates, BOE com upload, Orçado x Realizado, Metas, Ranking/Premiação, Dashboard, Relatório anual, validação/exportação dos cinco CSVs, Entidades e Catálogo. Administração consulta servidor/usuários/auditoria pela API; backup e importação histórica ficam bloqueados no modo servidor até possuírem execução central, sem fallback local.

Rotas funcionais: `/api/v1/financial-flow`, `/investments`, `/cashflow`, `/boe`, `/boe/validate`, `/boe/import`, `/budgets`, `/targets`, `/ranking`, `/dashboard`, `/reports/annual`, `/reports/csv-validation` e `/reports/csv-export`.

RBAC permanece aplicado no servidor. Consulta não pode criar/editar nem exportar CSV. O Cashflow preserva `version`, `expected_version` e conflito HTTP 409. As regras de ranking permanecem nos services existentes, sem duplicação no Desktop.

## Validação

- Python 3.13.15.
- `compileall`: aprovado.
- `pytest`: 260 passed, 1 warning não bloqueante.
- Alembic SQLite: `20260828_12 (head)`; check sem operações pendentes.
- PostgreSQL: não executado porque `DATABASE_URL` PostgreSQL não estava disponível na sessão.
- Migration nova: nenhuma.
- `git diff --check`: aprovado.
- Commit/push/tag: não executados.

O teste crítico substitui a factory SQLite por uma função que falha se chamada, inicia o `MainWindow` em modo servidor e confirma que o arquivo-sentinela `ja_finance.db` não mudou. Os testes de API cobrem RBAC, operações, BOE e Receita Direta. O teste multiusuário anterior continua cobrindo visibilidade compartilhada e conflito 409.

## Backlog e riscos

- Homologar contra o PostgreSQL Supabase usando credenciais disponibilizadas por ambiente.
- Centralizar backup e importação histórica na API antes de habilitá-los em produção.
- Homologar download/extração dos CSVs no Desktop contra o servidor real.
- Ajuste visual pequeno do rodapé entre Entidades e Catálogo.
