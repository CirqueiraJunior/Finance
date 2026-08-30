# Playbook operacional — Finance 1.0.0

## Incidente de API/autenticação

Valide `/health`, HTTPS, horário do servidor, PostgreSQL e migrations. Não entregue credenciais do banco ao desktop. Para primeiro acesso use o bootstrap uma vez; para recuperação use tokens de uso único. Antes de migrar SQLite, faça backup e preview, valide contagens e obtenha autorização formal.

## Inicialização

1. Ative `C:\Users\jose.alves\.venvs\Finance`.
2. Confirme o `.env` e o acesso ao banco.
3. Execute `python -m alembic upgrade head`.
4. Execute `python -m app.main`.
5. Confirme que `logs/ja_finance.log` recebeu a inicialização.

## Rotina segura

- Faça backup manual antes de manutenção relevante.
- Em importação histórica, sempre analise o preview e corrija erros bloqueantes.
- Nunca mova, edite ou substitua planilhas oficiais pelo aplicativo.
- Mantenha `.env`, bancos, backups, exports locais e logs fora do Git.

## Incidentes

- Falha de importação: o sistema executa rollback; guarde o log e o preview.
- Banco indisponível: feche a aplicação, valide `DATABASE_URL` e restaure somente
  de backup verificado.
- CSV bloqueado: complete os 12 meses das Entidades ativas antes de exportar.

## Homologação

Execute `compileall`, `pytest`, `alembic current`, `alembic check` e abra a GUI.
Não publique release nem restaure backup sem autorização formal.
