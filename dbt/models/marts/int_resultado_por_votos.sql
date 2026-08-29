{{
  config(
    materialized = 'table',
    cluster_by   = ['ano_eleicao', 'cod_cargo'],
    description  = 'Resultado de cargo MAJORITARIO apurado a partir dos votos oficiais (ADR-023).'
  )
}}

/*
  Grao: uma candidatura a cargo majoritario (Presidente, Governador, Senador).

  POR QUE ESTE MODELO EXISTE

  O TSE nao publica `DS_SIT_TOT_TURNO` no `consulta_cand` para NENHUM dos 8
  candidatos a Presidente de 2006 (L-16). Sem isto, o segundo mandato do Lula
  (2007-2010) nao existe em `fct_mandato`, e a ficha dele dizia "2006 ·
  Presidente · Nao eleito" — afirmacao falsa sobre uma pessoa real, publicada.

  ISTO NAO E' PREENCHER BURACO DE DADO

  A regra 5 do CLAUDE.md proibe inventar dado ausente. Nada e' inventado aqui: o
  resultado sai de DOIS conjuntos oficiais do proprio TSE, ja' no lake:

      raw_tse.votacao   quantos votos cada candidatura teve, por turno
      raw_tse.vagas     quantas cadeiras estavam em disputa naquela UE

  Em cargo majoritario a regra e' aritmetica e nao admite discricao: elegem-se os
  N mais votados do ULTIMO turno realizado, com N vindo do TSE. Nao ha' quociente,
  sobra, media nem coligacao para interpretar.

  SO' MAJORITARIO — E ISSO NAO E' PREGUICA

  Deputado (cargos 6, 7, 8) fica de fora de proposito. Cadeira proporcional nao
  vai para quem teve mais voto pessoal: depende de quociente eleitoral, quociente
  partidario, sobras e do desempenho da legenda inteira. Um "top N por votos" ali
  produziria uma lista de eleitos ERRADA com aparencia de certa — pior que a
  ausencia que este modelo corrige.

  A CONFIANCA E' MEDIDA, NAO ASSUMIDA

  `assert_resultado_derivado_bate_com_o_tse` roda esta regra sobre os anos em que
  o TSE PUBLICOU e compara: 2.155 acertos em 2.158, 10 de 10 em Presidente. As
  tres divergencias sao cassacao e eleicao suplementar — casos em que quem ocupou
  a cadeira nao e' quem teve mais voto, e que contagem nenhuma tem como saber.
  Por isso o TSE tem SEMPRE precedencia em `fct_candidatura`; este modelo so'
  fala onde ele calou.
*/

with vagas as (

    -- Quantas cadeiras a UE elegia. Muda entre anos no Senado: 2006 renovou um
    -- terco (1 por estado), 2010 e 2018 renovaram dois tercos (2 por estado).
    -- Nenhum numero fixo no codigo — vem do proprio TSE.
    select
        ano_eleicao,
        {{ inteiro('cod_cargo') }}          as cod_cargo,
        {{ limpa('sg_ue') }}                as sg_ue,
        max({{ inteiro('qt_vagas') }})      as qt_vagas
    from {{ source('raw_tse', 'vagas') }}
    group by 1, 2, 3

),

votos as (

    select
        ano_eleicao,
        {{ inteiro('cod_cargo') }}                        as cod_cargo,
        -- PRESIDENTE E' NACIONAL. O cadastro de candidaturas usa `sg_ue = 'BR'`,
        -- mas a votacao vem quebrada por estado. Sem esta conversao a chave nunca
        -- casa, e o caso que motivou o modelo — 2006 — fica justamente de fora.
        if({{ inteiro('cod_cargo') }} = 1, 'BR', {{ limpa('sg_uf') }}) as sg_ue,
        sq_candidato,
        {{ inteiro('nr_turno') }}                         as nr_turno,
        -- ja' chega INTEGER da ingestao; passar por `limpa` daria TRIM(INT64)
        sum(qt_votos_nominais)                            as votos
    from {{ source('raw_tse', 'votacao') }}
    -- Presidente (1), Governador (3), Senador (5). Ver o cabecalho.
    where {{ inteiro('cod_cargo') }} in (1, 3, 5)
    group by 1, 2, 3, 4, 5

),

ultimo_turno as (

    -- O desfecho e' o do ULTIMO turno realizado. Somar os turnos daria um numero
    -- que nao decide nada: em 2006 Lula teve 46,7 milhoes no primeiro e 58,3 no
    -- segundo, e a soma nao e' a votacao de ninguem.
    select ano_eleicao, cod_cargo, sg_ue, max(nr_turno) as nr_turno
    from votos
    group by 1, 2, 3

),

por_candidato as (

    select
        v.ano_eleicao,
        v.cod_cargo,
        v.sg_ue,
        v.sq_candidato,
        u.nr_turno                                          as nr_turno_decisivo,
        -- Votos NO TURNO DECISIVO. Quem foi eliminado antes nao tem, e esse NULL
        -- e' o que separa "perdeu a disputa final" de "nem chegou la'".
        max(if(v.nr_turno = u.nr_turno, v.votos, null))      as votos,
        max(v.nr_turno) = u.nr_turno                         as chegou_ao_decisivo,
        any_value(g.qt_vagas)                                as qt_vagas
    from votos v
    join ultimo_turno u using (ano_eleicao, cod_cargo, sg_ue)
    left join vagas g using (ano_eleicao, cod_cargo, sg_ue)
    group by 1, 2, 3, 4, 5

),

classificada as (

    select
        *,
        -- `RANK` e nao `ROW_NUMBER`: em empate exato os dois recebem a mesma
        -- posicao, e o empate fica visivel em vez de ser desempatado pela ordem
        -- em que as linhas por acaso foram lidas.
        rank() over (
            partition by ano_eleicao, cod_cargo, sg_ue
            order by votos desc
        ) as posicao
    from por_candidato

),

com_empate as (

    select
        *,
        count(*) over (
            partition by ano_eleicao, cod_cargo, sg_ue, posicao
        ) as empatados
    from classificada

)

select
    {{ sk_candidatura(sg_ue='sg_ue') }}          as sk_candidatura,
    ano_eleicao,
    cod_cargo,
    sg_ue,
    sq_candidato,
    nr_turno_decisivo,
    votos                                        as votos_no_turno_decisivo,
    qt_vagas,
    if(chegou_ao_decisivo, posicao, null)        as posicao,
    case
        -- Eliminado antes do turno decisivo: NAO foi eleito. Nao e' inferencia,
        -- e' certeza — quem nao disputou o segundo turno nao ganhou nele.
        when not chegou_ao_decisivo                 then false
        when qt_vagas is null                       then null
        -- Empate exato numa vaga e' decidido por criterio legal (o mais idoso),
        -- e isso nao esta' na contagem de votos. Vira NULL, nao um chute.
        when posicao <= qt_vagas and empatados > 1  then null
        when posicao <= qt_vagas                    then true
        else false
    end                                          as eleito_por_votos
from com_empate
