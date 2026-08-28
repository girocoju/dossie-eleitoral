/*
  Homonimo com a mesma data de nascimento NAO pode receber `id_pessoa`.

  Sem esta trava, o painel colaria o historico eleitoral, os bens declarados e a
  atividade parlamentar de uma pessoa no rosto de outra — e faria isso com a mesma
  confianca visual de um dado correto. Nao mostrar e' ruim; mostrar errado sobre
  uma pessoa identificada e' outra categoria de problema.
*/

select
    casa,
    id_casa,
    nome_completo,
    metodo_id_pessoa
from {{ ref('dim_parlamentar') }}
where id_ambiguo
  and id_pessoa is not null
