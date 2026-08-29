/*
  A apuracao por votos precisa reproduzir o resultado que o TSE publicou.

  `int_resultado_por_votos` calcula quem se elegeu a partir dos votos oficiais e
  do numero de vagas, para preencher o que o TSE nao publicou — a eleicao
  presidencial de 2006 inteira, entre outros (L-16 / ADR-023).

  Uma apuracao que se aplica onde NAO ha' gabarito precisa provar que acerta onde
  HA'. Este teste roda a mesma regra sobre os anos publicados e compara.

  MEDIDO EM 29/08/2026: 2.636 acertos, 4 divergencias — 99,85%. Em Presidente,
  50 de 50.

  AS DIVERGENCIAS CONHECIDAS, E POR QUE ELAS NAO INVALIDAM O METODO

  Sao cassacao e eleicao suplementar: quem ocupou a cadeira nao foi quem teve
  mais voto na urna, e contagem nenhuma tem como saber disso.

    2014 · AM · Governador · AMAZONINO MENDES
    2018 · MT · Senador    · FAVARO

  Nesses casos o TSE publicou, e em `fct_candidatura` o TSE tem SEMPRE
  precedencia — a apuracao so' fala onde ele calou. A divergencia existe no
  laboratorio e nunca chega a' tela.

  O TETO E' 10. Nao e' zero de proposito: exigir zero faria o teste quebrar na
  proxima cassacao, que e' um evento normal da vida eleitoral e nao um defeito
  deste codigo. Mas um salto de 4 para dezenas significa que a aritmetica
  quebrou, e ai' e' para parar tudo.
*/

with confronto as (

    select
        f.ano_eleicao,
        f.cod_cargo,
        f.sg_ue,
        f.sk_candidatura,
        f.foi_eleito                as publicado_pelo_tse,
        d.eleito_por_votos          as apurado_dos_votos,
        d.posicao,
        d.qt_vagas
    from {{ ref('fct_candidatura') }} f
    join {{ ref('int_resultado_por_votos') }} d using (sk_candidatura)
    -- So' onde ha' gabarito: sem resultado publicado nao ha' o que conferir.
    where f.foi_eleito is not null
      and d.eleito_por_votos is not null

),

divergencias as (

    select count(*) as n
    from confronto
    where publicado_pelo_tse != apurado_dos_votos

)

select n as divergencias
from divergencias
where n > 10
