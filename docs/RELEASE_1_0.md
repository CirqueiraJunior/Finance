# Finance — Release 1.0.0

## Status

**HOMOLOGADA — código-fonte e ambiente central.**

Versão: `1.0.0`  
Tag Git: `v1.0.0`  
Commit homologado: `a539ab0535a7a1de5ffc5f3c22650216e208200f`  
Schema central: `20260922_24`

## Escopo

Release desktop com oito páginas navegáveis, domínios financeiros e
operacionais, BOE homologado, Ranking e Premiação trimestral, relatórios/CSV,
Cadastros, Administração, recuperação de acesso, atualização manual e
operação multiusuário por API central.

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
- O desktop não contém credenciais PostgreSQL.
- PostgreSQL central é a fonte oficial de dados em produção.

## Homologação técnica

- [x] PostgreSQL central provisionado e operacional
- [x] Migrations aplicadas até `20260922_24`
- [x] `alembic current` = `20260922_24 (head)`
- [x] `alembic check` sem operações pendentes
- [x] API conectada ao PostgreSQL central
- [x] `/health` = `status: ok`
- [x] Ambiente da API = `SERVER`
- [x] Setup inicial concluído
- [x] Administrador existente
- [x] Importação histórica desabilitada no ambiente SERVER
- [x] RBAC homologado
- [x] Fluxo de Caixa homologado
- [x] Financeiro homologado
- [x] BOE homologado
- [x] Orçado x Realizado homologado
- [x] Metas homologadas
- [x] Ranking e Premiação homologados
- [x] Cadastros homologados
- [x] Relatórios homologados
- [x] Administração homologada
- [x] Recuperação de acesso homologada
- [x] Verificação manual de atualização homologada
- [x] Nenhum SQLite local é fonte oficial em produção
- [x] Backup PostgreSQL pré-migração criado e validado
- [x] Configuração de produção sem secrets no Git
- [x] Suíte automatizada: 564 testes aprovados, 0 falhas

## Backup de segurança da migração central

Arquivo externo ao repositório:

`Finance_Central_PreMigration23_20260922_172220.dump`

Formato PostgreSQL custom validado com `pg_restore --list`.

SHA-256:

`9FD2787611E8A93CBA3DFC826B2B172E633478CCCA29BCA2698C9064C4E5EF2F`

## Distribuição

O empacotamento do aplicativo desktop não integra o escopo técnico fechado
desta release.

Backlog:

`DIST-001 — Definir e implementar empacotamento/distribuição desktop do
Finance para Windows, incluindo executável, instalador, atualização e
assinatura.`

Até a implementação do `DIST-001`, não há instalador oficial da versão 1.0.0.

## Rastreabilidade

Branch: `main`  
Tag: `v1.0.0`  
Commit: `a539ab0535a7a1de5ffc5f3c22650216e208200f`

O tag remoto `v1.0.0` foi validado apontando para o mesmo commit homologado.
