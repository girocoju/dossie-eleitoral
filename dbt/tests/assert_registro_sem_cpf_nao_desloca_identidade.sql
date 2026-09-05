/*
  A resolucao por nome nunca pode ficar com a identidade SEM CPF quando existe
  uma COM CPF para a mesma chave.

  `id_pessoa` e' o cpf_hash quando o ano publica CPF e a chave de nome quando nao
  publica (ADR-005). A mesma pessoa fica com dois ids quando tem candidatura dos
  dois lados dessa fronteira, e a ambiguidade que isso produzia foi o que manteve
  a presidencia da Comissao de Agricultura do Senado fora da tela (L-31 /
  ADR-050).

  Este teste guarda o erro na direcao contraria — o mais perigoso dos dois. Ficar
  com o id sem CPF significaria pendurar o mandato de um parlamentar de hoje num
  registro antigo que pode nem ser dele, e sem nada na tela indicando isso.

  Falha tambem se alguem trocar a ordem das duas condicoes no `case` do modelo:
  o teste olha o RESULTADO, nao o texto da regra.
*/

with identidades as (

    select
        chave_nome_nascimento,
        count(distinct if(cpf_hash is not null, id_pessoa, null)) as ids_com_cpf,
        array_agg(distinct if(cpf_hash is null, id_pessoa, null)
                  ignore nulls)                                   as ids_sem_cpf
    from {{ ref('dim_candidato') }}
    where id_pessoa is not null
      and chave_nome_nascimento is not null
    group by chave_nome_nascimento

)

-- A chave nao esta' em `dim_parlamentar` — ela e' insumo do casamento, nao
-- atributo do parlamentar. Vem do staging, que e' de onde o proprio modelo a le'.
select
    p.casa,
    p.id_casa,
    p.nome_parlamentar,
    p.id_pessoa,
    i.ids_com_cpf
from {{ ref('dim_parlamentar') }} as p
join {{ ref('stg_camara__parlamentares') }} as s
  on s.casa = p.casa and s.id_casa = p.id_casa
join identidades as i
  on i.chave_nome_nascimento = s.chave_nome_nascimento
where p.metodo_id_pessoa = 'nome_nascimento'
  and i.ids_com_cpf >= 1
  and p.id_pessoa in unnest(i.ids_sem_cpf)
