# Sprint 10 — Dashboard Executivo

Data técnica: 25/08/2026

## Escopo entregue

- Dashboard como página inicial da aplicação.
- Filtros de ano e mês.
- Resumo financeiro completo do período.
- Resumo BOE com Entidades, Consultas e valor.
- Orçado x Realizado de Receitas, Despesas e Resultado.
- Meta x Realizado separado para Consultas e Registros.
- Três gráficos simples.
- Estados vazio e parcialmente preenchido.
- Serviço de composição, controller, View, testes e documentação.

## Referência controlada — julho/2026

- Receita Direta BOE: R$ 21.967,2684.
- Receita Indireta: R$ 100,0000.
- Receita Total: R$ 22.067,2684.
- Despesas: R$ 500,0000.
- Resultado Operacional: R$ 21.567,2684.
- Aplicações: R$ 10.000,0000.
- Resgates: R$ 2.500,0000.
- Movimentação de Caixa: R$ 14.067,2684.
- Saldo Aplicado: R$ 7.500,0000.
- BOE: 77 Entidades, 316.988 Consultas e R$ 21.967,2684.
- Orçamento: Receitas R$ 20.200,0000; Despesas R$ 2.000,0000; Resultado
  R$ 18.200,0000.
- Meta Consultas: 1.271.634,8800; Realizado: 1.153.124,2400;
  Atingimento: 90,6805%.
- Meta Registros: 166.763,9400; Realizado: 173.762,6500;
  Atingimento: 104,1968%.

Os dados de Meta x Realizado da referência completa são validados em cenário de
teste controlado; a base oficial pode permanecer sem carga desse módulo.

## Decisões técnicas

O `DashboardService` apenas coordena os services existentes e produz DTOs
imutáveis. Não há persistência de totais do Dashboard. Ausência de um módulo é
tratada localmente, preservando os demais resultados. Nenhuma migration foi
criada nesta sprint.

## Validação

Há testes automatizados para cenário completo, período vazio, ausência isolada
de BOE, Orçamento e Metas, meta zero, filtros, apresentação e gráficos. A
homologação final depende da execução integral da suíte e da abertura real da
interface no ambiente oficial.
