/*
  Bem declarado com valor negativo e' legitimo — mas so' para um tipo de bem.

  Saldo de conta corrente no cheque especial entra na declaracao com sinal
  negativo, e o TSE publica assim (conferido em 27/08/2026: 5 casos em 76.410
  bens de 2026, todos "deposito bancario"/"outros depositos a vista", o menor
  -R$ 38.101,07). Um imovel ou um veiculo com valor negativo, ao contrario, seria
  erro de origem ou de parsing.

  Falha se aparecer valor negativo em qualquer tipo de bem que nao seja conta,
  deposito ou aplicacao — que e' o caso que realmente precisa de investigacao.
*/

select
    sq_candidato,
    ano_eleicao,
    nr_ordem_bem,
    tipo_bem,
    valor_bem
from {{ ref('stg_tse__bens') }}
where valor_bem < 0
  and not regexp_contains(
        {{ sem_acento('tipo_bem') }},
        r'DEPOSITO|CONTA CORRENTE|POUPANCA|APLICACAO|DINHEIRO|CREDITO'
      )
