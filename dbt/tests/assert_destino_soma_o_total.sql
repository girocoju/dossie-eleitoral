/*
  Os quatro destinos tem que somar exatamente o total de proposicoes.

  `qt_virou_norma`, `qt_arquivada`, `qt_em_tramitacao` e `qt_destino_desconhecido`
  sao construidos como categorias mutuamente exclusivas e exaustivas. Se a Camara
  mudar a grafia de uma situacao — como ja' fez com "Transformad**o**" no
  masculino, que zerou a contagem de leis — uma proposicao pode cair fora das
  quatro ou em duas ao mesmo tempo, e o buraco aparece aqui e nao na tela.

  E' a mesma familia de falha que este projeto ja' levou uma vez: o numero nao
  quebra, ele so' fica errado em silencio.
*/

select
    id_deputado,
    ano,
    classe_proposicao,
    qt_proposicoes,
    qt_virou_norma + qt_arquivada + qt_em_tramitacao + qt_destino_desconhecido as soma_destinos
from {{ ref('fct_atividade_legislativa') }}
where qt_virou_norma + qt_arquivada + qt_em_tramitacao + qt_destino_desconhecido
      != qt_proposicoes
