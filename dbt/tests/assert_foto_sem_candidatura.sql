/*
  F-13: foto orfa e' esperada em pequena quantidade, mas nao em massa.

  Foto orfa = `sq_candidato` do nome do arquivo que nao existe no `consulta_cand`.

  POR QUE NAO E' MAIS "ZERO ORFAS"

  O TSE publica os dois pacotes de forma INDEPENDENTE, e durante o periodo de
  registro eles ficam momentaneamente dessincronizados. Medido em 28/08/2026: o
  pacote de fotos trazia 20.784 candidaturas e o `consulta_cand` 20.765 — 19 fotos
  (0,09%) de registros ainda nao publicados na lista de candidatos, espalhadas por
  8 UFs. Recarregar os candidatos nao resolveu: a lista simplesmente ainda nao os
  tinha.

  Exigir zero deixaria o pipeline diario vermelho por um comportamento normal da
  fonte, ate' 04/10/2026. E um pipeline que vive vermelho para de ser lido.

  POR QUE ESSA DIRECAO E' INOFENSIVA

  `dim_candidato` faz LEFT JOIN em fotos: uma foto sem candidatura simplesmente
  nao aparece em lugar nenhum. Nada errado chega a' tela. O caso perigoso e' o
  inverso — candidato sem foto — e quem cobre isso e' o
  `assert_cobertura_de_fotos`.

  O QUE O TETO AINDA PROTEGE

  Se a proporcao disparar, a causa nao e' dessincronia: e' `sk_candidatura` montada
  errada, ou o pacote de fotos de um ano casando com candidatos de outro. Um erro
  de chave nao produz 0,1% de orfas, produz dezenas de por cento.

  Teto de 1%, dez vezes o observado.
*/

with contagem as (

    select
        count(*)                                as fotos,
        countif(d.sk_candidatura is null)       as orfas
    from {{ ref('stg_tse__fotos') }} as f
    left join {{ ref('dim_candidato') }} as d using (sk_candidatura)

)

select
    fotos,
    orfas,
    round(orfas / fotos, 4) as taxa
from contagem
where orfas > fotos * 0.01
