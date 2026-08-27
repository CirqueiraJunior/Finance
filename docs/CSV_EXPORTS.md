# Exportação CSV CESPC/GO

Os cinco layouts são contratos do site e usam `;` como separador.

## Associação

`wp25_membros_associacao.csv`

Cabeçalho:

`COD;ANO;JAN CAP;JAN EXEC;FEV CAP;FEV EXEC;MAR CAP;MAR EXEC;ABR CAP;ABR EXEC;MAI CAP;MAI EXEC;JUN CAP;JUN EXEC;JUL CAP;JUL EXEC;AGO CAP;AGO EXEC;SET CAP;SET EXEC;OUT CAP;OUT EXEC;NOV CAP;NOV EXEC;DEZ CAP;DEZ EXEC`

## Meta x Realizado

Os quatro arquivos usam:

`COD.;ANO;JAN;FEV;MAR;ABR;MAI;JUN;JUL;AGO;SET;OUT;NOV;DEZ`

Arquivos:

- `wp25_membros_consultas_metas.csv`
- `wp25_membros_consultas_realizadas.csv`
- `wp25_membros_registros_metas.csv`
- `wp25_membros_registros_realizados.csv`

## Regras

- dados vêm somente do banco;
- 7500 não é Entidade;
- todos os 12 meses precisam existir para todas as Entidades ativas;
- valores são gravados com quatro casas e vírgula decimal;
- não há edição manual posterior;
- a operação gera um relatório e registra o histórico em `csv_exports`;
- WordPress permanece integração futura.
