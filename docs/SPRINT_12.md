# Sprint 12 — Release 1.0

## Entregas

- Cadastros funcionais de Entidades e catálogo.
- Administração local com informações, CSVs, logs e backup manual.
- Importação histórica de Fluxo, BOE, Meta, Associação e Orçamento compatível.
- Preview, inconsistências, deduplicação, backup e rollback.
- UX revisada, fonte estabilizada, navegação e botões testados.
- Versão 1.0.0 e documentação final.

## Decisões

Sem nova migration: o domínio necessário já existia em `20260827_09`.
Saldo técnico e Receita Direta da planilha financeira não viram lançamentos
manuais; Receita Direta continua originada do BOE. Detalhes orçamentários sem
correspondência inequívoca ficam como warning e não são persistidos.

## Homologação

Baseline inicial: 200 testes. Homologação técnica final: **213 testes aprovados**,
0 falhas, 0 erros; Alembic `20260827_09 (head)` sem operações pendentes e
aplicação aberta sem o warning de `QFont`.
