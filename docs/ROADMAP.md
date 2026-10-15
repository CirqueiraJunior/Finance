# Finance — Roadmap vigente

> **Referência documental: 14/10/2026.** O estado vigente abaixo substitui as indicações de “pré-release em execução” contidas no histórico preservado ao final do arquivo.
> Esta atualização é documental, baseada em auditoria estática e em resultados de homologação previamente registrados.

## Versão 1.0.0 — Publicada e homologada anteriormente

- **Status:** release 1.0.0 publicada e homologada em registros anteriores; não está aguardando o primeiro build.
- **Artefatos oficiais conhecidos:** `Finance_Setup_1.0.0.exe` e `Finance_Module_1.0.0.japackage`.
- **Publicação central conhecida:** repositório `JA-Technology-Releases`, tag `finance-v1.0.0`.
- **Teste de regressão:** 697 testes aprovados em execução anterior, sem reexecução nesta auditoria.
- **Arquitetura atual:** aplicação PySide6, serviços, API FastAPI, autenticação, permissões e PostgreSQL central implementados; integração com Control Center existente.
- **Observação:** a antiga indicação “criar tag `v1.0.0`” era uma tarefa anterior ao processo de publicação. A tag de distribuição conhecida é `finance-v1.0.0`; não inferir que exista tag `v1.0.0` no repositório do produto.

## Próxima etapa — documentação e validações direcionadas (sem nova sprint de código)

1. Conciliar BACKLOG, ROADMAP, playbooks e informações de release; manter os registros antigos como históricos.
2. Verificar, apenas quando necessário, o ajuste visual “Selecione uma Entidade.” no Catálogo.
3. Conferir evidências operacionais do PostgreSQL isolado e do SMTP real, sem assumir reprovação por ausência de prova nesta auditoria.
4. Manter backup/importação remotos como evolução controlada: não habilitar operação local indevida no modo servidor.
5. Só planejar transferência de dados oficiais SQLite → PostgreSQL mediante autorização escrita e plano de reversão.

## Evoluções para futura priorização

- Backup administrativo centralizado e importação histórica pelo serviço/API.
- Requisitos financeiros, BOE, relatórios e exportações adicionais conforme demanda validada.
- Integração direta com WordPress e outras integrações externas.
- Ajustes de interface e fluxos somente após constatação de necessidade concreta.

## Governança de entrega

Não reabrir Sprints 01–12 com base apenas em checklists desatualizados. Não realizar build, commit, push, migração ou intervenção nos softwares durante a auditoria documental. A preparação de uma nova distribuição exige verificação dos artefatos e do ambiente aplicável, independentemente da homologação histórica.

---

# Registro histórico preservado — ROADMAP original

> **ATENÇÃO: CONTEÚDO HISTÓRICO.** A seção original abaixo foi preservada para auditoria. Os itens antigos não marcados como concluídos não definem o estado vigente.

# Roadmap

## Fechamento pré-release Finance 1.0.0 — em execução

Pendências obrigatórias antes do instalador oficial:

- [x] Dashboard Financeiro com período unificado e multiano.
- [x] Premiação 2025 e 2026 separadas por estratégia anual.
- [x] Valores monetários 2026 confirmados na documentação do Regulamento oficial.
- [x] Parser Meta x Realizado 2025/2026 validado.
- [x] Remoção do fallback silencioso de Orçamento para 2026.
- [x] Compatibilidade de Orçamento com ano futuro validada em teste para 2027.
- [x] Suíte completa após os ajustes finais desta Sprint: 672 testes aprovados.
- [ ] Revisão final de release readiness.
- [ ] Build dos artefatos `Finance_Setup_1.0.0.exe` e `Finance_Module_1.0.0.japackage`.
- [ ] Homologação dos artefatos finais.
- [ ] Criação da tag `v1.0.0` somente após homologação final.

### Pós-release / Backlog

- Reorganização do workspace `J.A. Technology` em `Softwares` e `Complementos`.
- Compatibilidade de novos layouts anuais será tratada quando houver arquivos oficiais reais que divirjam da estrutura suportada.

- Sprint 12.A: fundação multiusuário, segurança, API, auditoria e concorrência — implementada tecnicamente, pendente de homologação e validação PostgreSQL no ambiente de deploy.

## Release 1.0.0

Sprints 01–12: fundação, Entidades, BOE, Fluxo, Orçamento, Investimentos, Metas,
Dashboard, Relatórios/CSV, UX, Cadastros, Administração, backup e importação
histórica controlada.

## Depois da 1.0

Itens já preservados no Backlog: autenticação e permissões, auditoria completa,
PostgreSQL de produção, empacotamento/distribuição, WordPress, fechamento mensal,
relatórios avançados e tratamento controlado de saldos históricos.
