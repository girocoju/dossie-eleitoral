/*
  Distingue "a fonte tem alguns registros errados" de "nosso parsing quebrou".

  O cadastro do TSE traz datas de nascimento impossiveis — 21 casos em 180.718
  candidaturas (0,01%) em 27/08/2026. Isso e' erro de origem e esta' registrado em
  docs/LACUNAS.md (L-15); reprovar a build por causa disso seria transformar um
  defeito da fonte em impedimento.

  Mas se o `data_br` ou o calculo de idade quebrarem, a proporcao explode. Entao o
  teste falha quando mais de 0,5% das candidaturas com data de nascimento tem idade
  implausivel — um patamar 50x acima do observado, que so' e' alcancado por bug
  nosso, nunca por digitacao de cartorio.
*/

with medida as (

    select
        countif(not idade_plausivel)                                   as implausiveis,
        count(*)                                                       as com_data,
        safe_divide(countif(not idade_plausivel), count(*)) * 100      as pct
    from {{ ref('dim_candidato') }}
    where data_nascimento is not null

)

select *
from medida
where pct > 0.5
