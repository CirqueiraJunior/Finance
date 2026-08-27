# Sprint 11 — Relatórios e CSV CESPC/GO

## Objetivo

Transformar a página Relatórios em uma área funcional de consulta anual e
implementar o gerador dos cinco CSVs oficiais usados pelo site CESPC/GO.

## Entregas

- Relatório financeiro anual, mês a mês, a partir dos serviços já homologados.
- Persistência mensal de dados de Associação (Captação/Execução), necessária ao
  contrato `wp25_membros_associacao.csv`.
- Histórico de tentativas de exportação em `csv_exports`.
- Validação anual antes da exportação.
- Geração conjunta dos cinco arquivos:
  - `wp25_membros_associacao.csv`
  - `wp25_membros_consultas_metas.csv`
  - `wp25_membros_consultas_realizadas.csv`
  - `wp25_membros_registros_metas.csv`
  - `wp25_membros_registros_realizados.csv`
- Separador `;`, cabeçalhos contratuais e decimal com vírgula.
- Relatório textual da exportação.
- Nenhuma integração HTTP/WordPress nesta Sprint.

## Regra de completude

A exportação dos cinco arquivos é atômica no nível funcional: se faltar qualquer
mês de Meta/Realizado ou Associação para uma Entidade ativa no ano selecionado,
a geração é bloqueada e a inconsistência é apresentada. Nenhum zero é inventado.

## Código 7500

O código 7500 continua reservado ao consolidado e nunca é exportado como Entidade.

## Fora do escopo

Integração direta WordPress, autenticação, permissões, auditoria completa,
importação automática das planilhas legadas e empacotamento Release 1.0.
