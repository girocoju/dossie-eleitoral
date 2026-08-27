/*
  Constituicao 0.7 / ADR-007: CPF, titulo de eleitor e e-mail nao existem em
  lugar nenhum do warehouse. `cpf_hash` tem 64 caracteres hexadecimais; um CPF
  em claro tem 11 digitos.

  Falha se algum valor de `cpf_hash` parecer um CPF em vez de um hash.
*/

select
    sq_candidato,
    length(cpf_hash) as tamanho
from {{ ref('dim_candidato') }}
where cpf_hash is not null
  and (length(cpf_hash) != 64 or not regexp_contains(cpf_hash, r'^[0-9a-f]{64}$'))
