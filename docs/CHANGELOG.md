# Changelog

## 1.0.0 — Fechamento pré-release — 2026-10-03

- Dashboard Executivo com período unificado no Financeiro, inclusive intervalo multiano.
- BOE e Meta x Realizado mantidos com filtros multiano já homologados.
- Parser Meta x Realizado compatível com layouts oficiais 2025 e 2026 por estrutura/semântica.
- Regras de Premiação específicas por ano: estratégia 2025 preservada e estratégia 2026 mantida.
- Premiação 2026 documentada conforme Regulamento oficial: R$ 3.000,00, R$ 2.000,00 e R$ 1.000,00.
- Parser de Orçamento não assume mais 2026 silenciosamente quando o ano não é identificável.
- Compatibilidade futura de Orçamento validada com arquivo 2027.
- Build, instalador, módulo `.japackage` e tag `v1.0.0` permanecem pendentes até o fechamento integral da pré-release.
- Suíte completa final da Sprint: 672 testes aprovados, 28 warnings conhecidos.
- Testes focados do parser após remoção do fallback de Orçamento: 14 aprovados.

## 1.0.0 ? Release Final ? 2026-09-28

- Homologa??o final da interface e padroniza??o visual global.
- Importa??es controladas de Or?amento e Metas com inser??o/substitui??o audit?vel.
- Ajustes finais do BOE e escopo da entidade 7600.
- Integra??o confi?vel de identidade entre os componentes da J.A. Technology.
- Administra??o multiusu?rio com altera??o de nome, e-mail, usu?rio, perfil e situa??o.
- Valida??o de unicidade e normaliza??o de e-mail e username.
- Finance abre maximizado e o carregamento inicial do Dashboard foi estabilizado.
- Schema PostgreSQL homologado em `20260927_26`.
- Su?te consolidada: 613 testes aprovados.
- Distribui??o Windows por `Finance.exe`, `FinanceServer.exe` e instalador Inno Setup.


## 1.0.0 pré-release — Sprint 12.A

- API FastAPI, login, tokens, Argon2id, RBAC, usuários e auditoria.
- Recuperação/troca de senha, bootstrap administrativo e SMTP abstrato.
- Cliente desktop, login anterior à MainWindow, usuário/perfil e logout.
- Autoria financeira, concorrência otimista e migração controlada SQLite → PostgreSQL.
- Migrations `20260828_11` e `20260828_12`; Release não publicada.

## 1.0.0 — 2026-08-27

- Sprint 01: fundação técnica e navegação.
- Sprint 02: Base Mestre de Entidades.
- Sprint 03: importação BOE.
- Sprints 04–05: receitas, despesas e Fluxo de Caixa.
- Sprint 06: Orçamento e Orçado x Realizado.
- Sprint 07: Aplicações, Resgates e saldo aplicado.
- Sprint 08: detalhe BOE por Entidade.
- Sprint 09: Meta x Realizado.
- Sprint 10: Dashboard Executivo.
- Sprint 11/11A: Relatórios, cinco CSVs e aderência à planilha oficial.
- Sprint 12: Cadastros, Administração, backup, importação histórica com preview,
  hardening, documentação e preparação da Release 1.0.
- Release blocker: Ranking/Premiação trimestral da Campanha Acelera Goiás,
  cancelamentos mensais, visão por Entidade, consolidado anual informativo e
  valores oficiais dos três primeiros colocados.
- Divergência resolvida: planilha `> 100%`; Regulamento e sistema `>= 100%`.
- Desempate final alinhado à regra operacional validada: Score, atingimento,
  Captação e menor número de Cancelamentos; empate técnico apenas na igualdade
  dos quatro critérios.

Nenhuma tag foi criada durante a homologação técnica.
