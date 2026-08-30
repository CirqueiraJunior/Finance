# Manual do Usuário — Finance 1.0.0

## Acesso e segurança

Com o servidor configurado, informe usuário/e-mail e senha antes de abrir o sistema. “Esqueci minha senha” envia instruções sem confirmar a existência da conta. O nome e o perfil aparecem discretamente no header; “Sair” invalida a sessão. Administradores gerenciam ativação e perfis de usuários e consultam auditoria; demais ações dependem do perfil. Em indisponibilidade do servidor, aguarde a normalização: não há base offline de escrita.

## Dashboard

Escolha Ano e Mês e clique **Atualizar**. Os blocos Financeiro, BOE, Orçamento
e Metas podem exibir estado sem dados sem impedir os demais.

## Financeiro

Use **Aplicar filtro** para consultar o período. Em **Novo Lançamento**, selecione
Descrição, Categoria, BOE e Valor. O Tipo é derivado do catálogo. Aplicações e
Resgates aparecem no mesmo fluxo.

## Orçado x Realizado

Filtre ano/mês ou ano completo. **Novo Orçamento** cadastra somente o valor
orçado; o realizado vem do Financeiro.

## BOE

Selecione a planilha, valide o preview e importe apenas quando aprovado. O código
7500 é consolidado e não é Entidade. A Receita Direta é criada automaticamente.

## Metas

Cadastre Meta e Realizado mensal de CONSULTAS ou REGISTROS por Entidade. Os
campos são números operacionais, sem símbolo monetário.

Na aba **Ranking e Premiação**, selecione Ano e Trimestre. O sistema soma apenas
os três meses do trimestre, classifica quem alcançou pelo menos 100% e apresenta
Score, componentes, campeões e valores. Após empate no Score Final, aplica-se
maior percentual de atingimento, maior Captação e menor número de Cancelamentos.
Empate técnico somente ocorre quando os quatro critérios forem idênticos, sem
vencedor arbitrário. A visão anual é informativa e não soma Scores para escolher
vencedores.

## Cadastros

Na aba **Base Mestre**, crie, edite, ative/inative e consulte aliases. O código
7500 é reservado. Na aba **Catálogo**, mantenha combinações coerentes de
Descrição/Categoria/Tipo; alterações não modificam lançamentos anteriores.

## Relatórios e CSV

O relatório anual consolida dados existentes. A exportação gera os cinco CSVs
oficiais com `;`, decimal por vírgula e 7500 somente como consolidado.

## Administração, backup e importação histórica

Administração mostra versão, ambiente, banco, Alembic, logs e contagens. **Fazer
Backup** cria uma cópia única em `backups/manual/`. Em **Importação histórica**:

1. Selecione `.xlsx` ou `.xlsm`.
2. Clique **Analisar e gerar preview**.
3. Confira tipo, ano, válidas, warnings, erros, duplicidades e totais.
4. O botão **Importar** só fica ativo sem erro bloqueante.
5. Ao confirmar, o sistema cria backup em `backups/imports/` e usa transação.

O orçamento só aceita agregações inequívocas. Saldo técnico, consolidado 7500 e
linhas ambíguas não são persistidos automaticamente.
Na importação de Associação, o preview mostra separadamente Captação,
Cancelamento e Total de Associados. O ranking não cria despesas no Financeiro;
o pagamento permanece um lançamento manual controlado.
