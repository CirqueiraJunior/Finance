# Análise técnica — Premiação de Meta x Realizado

## Fonte analisada

Arquivo oficial `Meta x Realizado - Oficial.xlsm`, inspecionado integralmente com
preservação das macros. Foram verificadas todas as planilhas e seus estados de
visibilidade: `Meta` (161 x 20), `Faturamento` (164 x 23), `Associações`
(79 x 50), `Geral` (85 x 38), `Geral Anual` (81 x 11), `Ranking` (80 x 26) e
`Visão Entidade` (78 x 38). Todas estão visíveis; não há aba hidden ou
veryHidden. Também não existe aba, célula ou fórmula contendo “Premiação”.

## Entradas e dependências identificadas

- metas e realizados mensais de Consultas e Registros;
- captações/associações mensais por entidade;
- cancelamentos mensais por entidade;
- consolidação trimestral (T1 a T4), por entidade;
- planilhas `Geral`, `Ranking` e `Visão Entidade` como saídas derivadas;
- nomes definidos legados, alguns com referências `#REF!`, que não constituem
  especificação segura de domínio.

## Cálculos inequívocos existentes

Em cada trimestre, a Meta Total soma as metas de Consultas e Registros e o
Realizado Total soma os respectivos realizados. O atingimento é
`Realizado Total / Meta Total`.

Pontuação de faturamento:

- abaixo de 100%: 0 ponto;
- de 100% até abaixo de 110%: 5 pontos;
- de 110% até abaixo de 150%: 6 pontos;
- a partir de 150%: 7 pontos.

Pontuação de associações/captações no trimestre:

- menos de 1: 0 ponto;
- de 1 a 7: 2 pontos;
- de 8 a 15: 3 pontos;
- 16 ou mais: 4 pontos.

Cancelamento vale 1 ponto quando não há cancelamentos e 0 nos demais casos. Nos
trimestres posteriores ao primeiro, a fórmula também atribui zero quando o
realizado trimestral é zero. A qualificação exibida na planilha usa atingimento
estritamente superior a 100% (`> 100%`).

O ranking trimestral soma os três grupos de pontos. O desempate usa uma chave
composta por pontos totais, percentual de atingimento, quantidade de associações
e menor quantidade de cancelamentos, nessa ordem.

## Saídas observadas

- pontuação trimestral de faturamento, associações e cancelamentos;
- total de pontos por trimestre;
- qualificação trimestral;
- posição no ranking por trimestre;
- visão consolidada por entidade.

## Mapeamento para o domínio atual

O sistema já possui metas/realizados mensais (`TargetEntry`) e associações
mensais (`AssociationEntry`). Não há modelo validado para cancelamentos,
qualificação trimestral, pontuação, ranking persistido ou concessão de prêmio.
Uma evolução futura pode calcular uma projeção trimestral a partir desses dados,
desde que a fonte e o significado dos cancelamentos sejam formalmente definidos.

## Conclusão corrigida com o Regulamento oficial

A aba `Ranking` representa operacionalmente a Premiação da Campanha Acelera
Goiás — Rumo ao Hexa. O Regulamento formal confirma apuração independente por
trimestre, mínimo de 100%, desempate pelo maior atingimento e prêmios de
R$ 3.000,00, R$ 2.000,00 e R$ 1.000,00 para 1º, 2º e 3º lugares.

A planilha usa `> 100%` na qualificação; o Regulamento exige `>= 100%`. O sistema
usa `>= 100%`, por prevalência da regra formal. Após empate no Score Final,
aplica-se maior percentual de atingimento, maior Captação e menor número de
Cancelamentos. Empate técnico somente ocorre quando os quatro critérios forem
idênticos. O Regulamento formaliza o primeiro desempate; Captação e
Cancelamentos são a regra operacional complementar validada na planilha.

Cancelamentos estão na aba `Associações`, na primeira coluna do bloco mensal
`CANC.`, `CAPTAÇÃO`, `SUSPENSO`, `TOTAL ASSC.`. Foram modelados em campo próprio,
sem reutilizar Captação ou Total de Associados.
