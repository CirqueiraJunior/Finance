# Finance — Release 1.0.0

## Status

**PRÉ-RELEASE — fechamento técnico em andamento.**

Versão planejada: `1.0.0`
Branch oficial: `main`
Tag Git oficial planejada: `finance-v1.0.0` — **ainda não criada**
Instalador oficial: **ainda não gerado nesta homologação final**

A versão 1.0.0 só será considerada publicada depois da validação final do código,
build dos artefatos oficiais, homologação dos binários e criação da tag Git.

## Escopo consolidado

- Aplicação desktop Finance.
- API central FastAPI.
- PostgreSQL central como fonte oficial em produção.
- RBAC, administração, auditoria e recuperação de acesso.
- Fluxo de Caixa, Orçamento, Investimentos e saldos.
- BOE.
- Meta x Realizado.
- Ranking e Premiação com estratégia anual 2025/2026.
- Dashboard Executivo com períodos multiano.
- Relatórios e CSV.
- Importações históricas controladas com preview.

## Regras e garantias

- `Decimal` nos valores financeiros.
- Entidade 7500 não participa dos cálculos operacionais de Meta x Realizado.
- Importações críticas exigem preview e validação antes da persistência.
- PostgreSQL central é a fonte oficial em produção.
- O desktop não contém credenciais PostgreSQL.
- Premiações não geram despesas automáticas no Fluxo de Caixa.
- Ranking/Premiação 2026 usa atingimento mínimo `>= 100%`.
- Desempate 2026: Score, maior atingimento, maior Captação e menor número de Cancelamentos.
- Empate técnico somente na igualdade dos quatro critérios.
- Valores documentados da Premiação 2026:
  - 1º lugar: R$ 3.000,00
  - 2º lugar: R$ 2.000,00
  - 3º lugar: R$ 1.000,00
- Estratégia de Premiação 2025 permanece independente da estratégia 2026.
- O parser de Orçamento não atribui mais 2026 quando o ano não puder ser identificado.
- Arquivos futuros podem ser aceitos quando mantêm estrutura suportada e trazem ano identificável;
  mudanças de layout exigem nova validação com arquivo oficial real.

## Validação automatizada

- Suíte completa final desta Sprint: **679 testes aprovados, 28 warnings conhecidos**.
- Testes focados do parser: **14 testes aprovados**.
- `git diff --check`: sem erro após correção de whitespace e encoding.

## Artefatos oficiais planejados

A arquitetura de release da versão 1.0.0 prevê dois artefatos:

- `Finance_Setup_1.0.0.exe`
- `Finance_Module_1.0.0.japackage`

Nenhum dos dois deve ser tratado como artefato final antes da homologação desta
pré-release.

## Checklist de fechamento

- [x] Dashboard multiano consolidado.
- [x] Meta x Realizado 2025/2026 validado.
- [x] Estratégias de Premiação 2025/2026 separadas.
- [x] Valores da Premiação 2026 documentados.
- [x] Fallback silencioso de Orçamento para 2026 removido.
- [x] Compatibilidade de Orçamento 2027 coberta por teste.
- [x] Suíte completa final.
- [ ] Revisão de release readiness.
- [ ] Build dos dois artefatos.
- [ ] Homologação do instalador e do `.japackage`.
- [ ] Tag `finance-v1.0.0`.

## Homologação do binário Desktop

- Commit fonte: `7e159c7`
- Versão: `1.0.0`
- Build Desktop compilado homologado visualmente.
- SHA-256 do `Finance.exe` homologado:
  `7FBF7F4569B8B5B60675A50D04192A60A21A781C120348F281FA2B78908CC26C`
- Homologação realizada contra a API de pré-release em `127.0.0.1:8011`.
- O artefato homologado é de validação pré-release e não constitui publicação oficial.

## Rastreabilidade

A rastreabilidade final (commit, hashes SHA-256 e tag) será preenchida somente
após o build e a homologação dos artefatos oficiais.
