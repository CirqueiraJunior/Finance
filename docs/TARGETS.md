# Meta x Realizado

## Modelo oficial analisado

Fonte: `Meta x Realizado - Oficial.xlsm`, analisada em modo somente leitura.
O arquivo contém sete abas:

- `Meta`: metas mensais, trimestrais e anuais de Consultas e Registros;
- `Faturamento`: realizados mensais, trimestrais e anuais dos mesmos indicadores;
- `Associações`: informações complementares das Entidades;
- `Geral`: composição trimestral;
- `Geral Anual`: composição anual;
- `Ranking`: classificação existente apenas na planilha e fora desta Sprint;
- `Visão Entidade`: recorte individual existente apenas na planilha.

As tabelas funcionais de referência são `MetaConsulta`, `MetaRegistro`,
`ConsRealizada` e `RegRealizado`. Elas possuem 77 Entidades, códigos, valores
mensais de janeiro a dezembro e fórmulas de soma trimestral/anual. As abas de
resumo calculam o percentual como `Realizado / Meta`.

## Domínio implementado

Os indicadores homologados são:

- `CONSULTAS`;
- `REGISTROS`.

Cada registro identifica Entidade, ano, mês e indicador, armazenando Meta,
Realizado disponível e observação. A combinação é única. Valores usam
`Numeric(18,4)` porque a fonte oficial possui valores decimais mesmo para os
indicadores operacionais.

O Realizado da planilha vem da aba `Faturamento`. Ele não corresponde ao BOE e
não existe em outro módulo do sistema. Por isso, a Sprint 09 persiste o valor
operacional estritamente necessário no próprio `TargetEntry`, sem implementar
importação automática. Na edição, somente Meta e observação são alteráveis; o
Realizado registrado permanece imutável.

## Cálculos

- Diferença: `Realizado - Meta`;
- Atingimento: `Realizado / Meta × 100`;
- Meta igual a zero: atingimento nulo e `—` na GUI;
- consolidação: soma das Entidades persistidas, nunca uma linha artificial.

Não há classificação favorável/desfavorável, ranking ou cores de desempenho.

## Código 7500

O código `7500` não aparece nas quatro tabelas operacionais analisadas. O
service rejeita seu uso como Entidade e os consolidados são calculados pela soma
dos registros reais.

## Cenário de referência — julho de 2026

| Indicador | Entidades | Meta | Realizado |
| --- | ---: | ---: | ---: |
| Consultas | 77 | 1.271.634,8800 | 1.153.124,2400 |
| Registros | 77 | 166.763,9400 | 173.762,6500 |

Para Goiânia (`7501`) em Consultas: Meta `645.495,9100`, Realizado
`517.670,6800`, Diferença `-127.825,2300` e Atingimento `80,1974%`.

## Limites

Não foram implementados importação automática, ranking, gráficos, análise por
produto, dashboard, exportação, exclusão, autenticação ou permissões.
