# Finance — Release 1.0.0

> Bloqueada para publicação até homologação da Sprint 12.A, validação PostgreSQL no ambiente de deploy e autorização formal. Nenhum commit, push ou tag faz parte desta etapa.

Status técnico: aguardando homologação final.

## Escopo

Release desktop com oito páginas navegáveis, domínios financeiros e
operacionais, BOE homologado, Ranking e Premiação trimestral, relatórios/CSV,
Cadastros, Administração, backup e importação histórica controlada.

## Garantias

- `Decimal` nos valores; 7500 nunca é Entidade.
- Preview obrigatório e botão bloqueado quando há erro.
- Backup automático antes de importação e rollback integral.
- BOE reutiliza parser homologado; orçamento não recebe mapeamento arbitrário.
- `.env`, bancos, backups, exports locais, planilhas e logs não são versionados.
- Versão pública vem de `app.core.version.__version__`.
- A aba Ranking representa operacionalmente a Premiação da Campanha Acelera
  Goiás; o Regulamento prevalece e classifica atingimento `>= 100%`.
- Premiações não geram despesas automáticas no Fluxo de Caixa.
- O desempate operacional aplica Score, maior atingimento, maior Captação e
  menor número de Cancelamentos; igualdade nos quatro critérios é empate técnico.

## Estado de dados

Durante o desenvolvimento da Sprint 12 foram executados somente previews em
cópias temporárias. Nenhuma importação permanente foi feita no banco oficial.
As cópias temporárias foram removidas.

# Gate Multiusuário — Release 1.0

- [ ] PostgreSQL real provisionado
- [ ] Migrations aplicadas até `20260828_12`
- [ ] `alembic check` sem pendências
- [ ] API conectada ao PostgreSQL
- [ ] `/health` = 200
- [ ] Administrador bootstrap criado
- [ ] Login real funcionando
- [ ] Usuário A cria lançamento
- [ ] Usuário B visualiza lançamento
- [ ] Usuário B atualiza lançamento
- [ ] Usuário A recebe atualização
- [ ] Conflito concorrente retorna HTTP 409
- [ ] Auditoria registra usuário e operação
- [ ] Logout funciona
- [ ] Recuperação de senha testada
- [ ] Financeiro usa API
- [ ] BOE usa API
- [ ] Orçamento usa API
- [ ] Metas usa API
- [ ] Ranking usa API
- [ ] Cadastros usa API
- [ ] Relatórios consultam dados centrais
- [ ] Nenhum SQLite local é fonte oficial em produção
- [ ] Backup PostgreSQL definido
- [ ] Configuração de produção sem secrets no Git
