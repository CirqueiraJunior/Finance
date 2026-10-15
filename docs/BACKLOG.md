# Finance — Backlog vigente

> **Referência documental: 14/10/2026.** Esta seção prevalece sobre registros históricos ao final deste arquivo.
> Auditoria baseada em inspeção de código, testes existentes e homologações informadas anteriormente.
> Não houve execução de testes, acesso a banco, mudança de código ou nova homologação nesta revisão.

## Estado de referência — Finance 1.0.0

- A release `Finance 1.0.0` foi homologada e publicada anteriormente, com instalador `Finance_Setup_1.0.0.exe` e módulo `Finance_Module_1.0.0.japackage` assinado digitalmente no processo de publicação.
- A suíte de **697 testes aprovados** é um **resultado histórico informado**, não uma execução realizada durante esta auditoria. A referência antiga a 672 testes não é o último resultado conhecido.
- Arquitetura multiusuário, API FastAPI, autenticação/permissões, PostgreSQL central e integração com Control Center constam como implementados no projeto. A presente auditoria inspecionou evidências de código, sem comprovar novamente o estado operacional do deploy.
- Fluxos de cadastro e catálogo utilizam API e carregamento sob demanda (`src/app/gui/controllers/registration_controller.py` e `src/app/gui/main_window.py`).
- O serviço SMTP existe (`src/finance_server/email_service.py`) e é conectado pela fábrica da API (`src/finance_server/app_factory.py`); o **envio real em infraestrutura de produção** não foi homologado nesta rodada.

## Pendências específicas e sua classificação

| Item | Situação em 14/10/2026 | Tratamento |
| --- | --- | --- |
| Limpar “Selecione uma Entidade.” ao alternar para Catálogo | **Ajuste visual ainda não verificado na UI** | Validar comportamento; não tratar como defeito comprovado |
| Backup centralizado pela API | **Evolução futura** | No modo servidor, botão de backup local fica desabilitado, conforme `src/app/gui/main_window.py` |
| Importação histórica via API em produção | **Evolução futura / fluxo controlado** | No modo servidor, importação depende de sinalização específica; o fluxo habilitado examinado utiliza serviços locais em DEV |
| SMTP real (envio, erros e infraestrutura) | **Homologação operacional pendente nesta auditoria** | Verificar somente quando houver necessidade operacional e ambiente autorizado |
| PostgreSQL isolado em infraestrutura de deploy | **Validação operacional não reexecutada nesta auditoria** | Confrontar evidências de homologação/deploy antes de marcar como pendência efetiva |
| Migração de dados oficiais SQLite → PostgreSQL | **Condicionada a autorização formal** | Não executar sem inventário, reconciliação, autorização e rollback aprovado; não confundir com migrations Alembic do esquema |
| Integração direta WordPress | **Futuro** | Fora do escopo da versão atual |
| Novos relatórios, análises, saldos históricos e melhorias financeiras/BOE | **Backlog evolutivo** | Priorizar apenas em sprint futura aprovada |

## Encerrado / não reabrir por documentação antiga

- **Instalador e módulo oficiais:** existem e tiveram publicação e homologação anteriores.
- **Login, autenticação, perfis e permissões:** implementação existente; não tratá-los como uma arquitetura exclusivamente planejada.
- **API FastAPI e PostgreSQL:** implementação existente; distinguir código implementado de validações operacionais de infraestrutura.
- **Cadastro de Entidades, catálogo e Dashboard:** há funcionalidades implementadas; cada evolução adicional continua sujeita a delimitação específica.
- **Importação histórica controlada local:** implementação e arquivos de teste identificados; isso não implica importação remota já liberada.

## Regra de leitura e continuidade

Não transformar itens antigos das Sprints 01–12, da antiga proposta “Finance 1.1 — Arquitetura Multiusuário” ou do antigo pré-release em pendências atuais sem confrontar código, testes e artefatos. Não alterar o Finance 1.0.0 durante a revisão documental. Homologações operacionais não comprovadas aqui permanecem **não verificadas**, não automaticamente reprovadas.

---

# Registro histórico preservado — BACKLOG original

> **ATENÇÃO: CONTEÚDO HISTÓRICO.** O texto abaixo foi mantido integralmente para rastreabilidade. Afirmações como “nenhum item desta arquitetura foi implementado” e “release pendente” descrevem o contexto da época, **não o estado atual**.

# Backlog

- Ajuste visual pequeno: limpar “Selecione uma Entidade.” ao trocar para a aba Catálogo.
- Centralizar backup e importação histórica na API; enquanto isso, essas ações ficam bloqueadas no modo servidor, sem acesso alternativo ao SQLite.

- Validar Sprint 12.A em PostgreSQL isolado na infraestrutura de deploy e homologar envio SMTP real.
- Migrar dados oficiais SQLite → PostgreSQL somente após autorização formal e plano de reversão aprovado.

Itens fora do escopo funcional da Sprint 10:

- Criar categorias financeiras parametrizáveis.
- Importar automaticamente o orçamento financeiro legado.
- Calcular Saldo acumulado.
- Permitir migração controlada de saldo aplicado inicial histórico.
- Implementar rendimentos, juros e rentabilidade de aplicações.
- Implementar edição controlada e exclusão lógica.
- Implementar auditoria financeira completa.
- Importar a planilha financeira legada.
- Evoluir relatórios financeiros com filtros e formatos adicionais.
- Avaliar análise BOE por produto apenas como evolução futura.
- Implementar reprocessamento/cancelamento controlado de BOE.
- Comparar períodos do BOE.
- Criar dashboard BOE.
- Criar relatórios BOE.
- Exportar dados BOE.
- Implementar auditoria completa do BOE.
- Criar notificações do BOE.
- Implementar fechamento mensal.
- Criar cadastro funcional de Entidades na GUI.
- Importar Entidades futuramente a partir das fontes legadas.
- Evoluir a exportação CSV e avaliar integração direta com o site.
- Avaliar integração futura com WordPress.
- Importar automaticamente metas e realizados operacionais das fontes legadas.
- Definir autenticação, perfis e permissões.
- Planejar CRUDs de cadastros após validação do domínio.
- Planejar importação e saneamento dos dados legados.
- Planejar exportações avançadas e relatórios PDF/Excel.
- Definir estratégia de backup, auditoria e recuperação.
- Definir empacotamento e distribuição do aplicativo desktop.
- Planejar release e publicação após homologação das funcionalidades previstas.
- Preparar configuração segura e operação do PostgreSQL em produção.
- Avaliar comparações históricas e detalhamento interativo do Dashboard.

## Sprint 08 — BOE detalhado por Entidade na GUI

Implementado: ao selecionar uma importação BOE, a interface apresenta as
Entidades persistidas com:

- Código;
- Entidade;
- Quantidade de Consultas;
- Valor do Repasse.

Também são apresentados Total de Entidades, Total de Consultas e Valor Total. O
código consolidado `7500` permanece excluído.

## Sprint 09 — Meta x Realizado

Implementado o domínio mensal por Entidade para os indicadores Consultas e
Registros, com cadastro, edição controlada, cálculo de Diferença e Atingimento,
consolidação e página funcional. A importação automática permanece no Backlog.

## Itens preservados após a Sprint 09

- Importação automática de Meta e Realizado;
- Relatórios avançados;
- WordPress;
- Administração;
- Release 1.0.

## Sprint 10 — Dashboard Executivo

Implementado o painel consolidado mensal com indicadores financeiros, BOE,
Orçado x Realizado e Meta x Realizado, além de três gráficos simples. O painel
tolera módulos sem dados e não persiste snapshots ou cálculos próprios.


## Registro de escopo

A Sprint 01 foi homologada em 24/08/2026. A Sprint 02 implementou a Base Mestra
de Entidades. A Sprint 03 implementou a importação resumida mensal do BOE. A
Sprint 04 implementou Receita Direta do BOE e Receita Indireta manual. A Sprint
05 implementou despesas manuais e saldo mensal. A Sprint 06 implementou orçamento
mensal/anual e Orçado x Realizado. A Sprint 07 implementou aplicações, resgates
e saldo aplicado. A Sprint 08 implementou o detalhe BOE por Entidade na GUI. A
Sprint 09 implementou Meta x Realizado operacional. A Sprint 10 implementou o
Dashboard Executivo; os demais itens da lista inicial e da seção preservada
continuam pendentes.

## Sprint 11 — Relatórios e CSV

Implementados relatório financeiro anual e motor dos cinco CSVs oficiais do site CESPC/GO, com validação de completude e histórico de exportação. Integração direta com WordPress permanece no Backlog.


## Correção concluída — Sprint 11A

- [x] Catálogo Descrição/Categoria/Tipo conforme `Lista Suspensa`
- [x] Categoria dependente da Descrição
- [x] Tipo derivado automaticamente
- [x] Campo BOE Sim/Não nos lançamentos
- [x] Preservação dos lançamentos existentes

## Sprint 12 — Importação histórica controlada

Importação histórica controlada das planilhas oficiais para evitar redigitação
dos meses anteriores.

Contempla Fluxo de Caixa, BOE, Meta x Realizado e os dados necessários
de Associação, com validação antes de gravar, preview, backup, prevenção de
duplicidade, relatório de inconsistências e reconciliação de totais.

### Preservado para evolução posterior após a Release 1.0

- tratamento de saldo inicial/saldo aplicado histórico;
- integração direta com WordPress.

Os itens de importação histórica, Cadastros, Administração e backup foram
concluídos na Sprint 12. Permanecem no backlog os itens futuros já registrados,
como autenticação/permissões, PostgreSQL de produção, auditoria completa,
empacotamento/distribuição e integrações avançadas.

## J.A. Finance 1.1 — Arquitetura Multiusuário

- PostgreSQL central;
- API FastAPI;
- autenticação;
- login;
- cadastro de usuário;
- esqueci minha senha;
- alteração de senha;
- perfis;
- permissões;
- auditoria;
- sessões;
- atualização compartilhada de dados;
- identificação de usuário em lançamentos;
- segurança;
- deploy central.

Proposta inicial de perfis, ainda sujeita à validação: Administrador, Gestor,
Operador Financeiro, Operador BOE e Consulta. Nenhum item desta arquitetura foi
implementado na Release 1.0.
