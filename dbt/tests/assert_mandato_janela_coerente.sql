/*
  SPEC 5, "Janela de mandato": Governador/Presidente 4 anos, Senador 8, Deputados 4,
  comecando em ano_eleicao + 1.

  Duas excecoes legitimas, ambas deduzidas da fonte e nao inventadas:

  - **Eleicao suplementar**: quem vence assume no proprio ano da eleicao e cumpre o
    que resta do ciclo. A janela e' mais curta e nao comeca em ano_eleicao + 1.
  - **Mandato interrompido**: quando houve suplementar para o mesmo cargo e UE
    dentro da janela, o mandato original termina antes (`motivo_fim = interrompido`).

  Falha se um mandato ORDINARIO e NAO interrompido tiver janela fora do previsto,
  ou se qualquer mandato tiver janela invertida ou mais longa que a duracao do cargo.
*/

select
    sk_mandato,
    cod_cargo,
    sg_ue,
    ano_eleicao,
    ano_inicio,
    ano_fim,
    anos_de_mandato,
    duracao_mandato_anos,
    is_eleicao_suplementar,
    motivo_fim
from {{ ref('fct_mandato') }}
where
    -- janela invertida ou mais longa que o cargo permite: erro em qualquer caso
    ano_fim < ano_inicio
    or anos_de_mandato > duracao_mandato_anos
    -- mandato ordinario e completo tem de bater exatamente com o previsto
    or (
        not is_eleicao_suplementar
        and motivo_fim != 'interrompido'
        and (ano_inicio != ano_eleicao + 1 or anos_de_mandato != duracao_mandato_anos)
    )
