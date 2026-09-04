"""A situacao no TSE ganha cor — sem que a cor vire juizo (F-25).

Nove valores em 2026, e "DEFERIDO" ao lado de "INDEFERIDO EM PRAZO RECURSAL OU
COM RECURSO" em texto puro obriga quem le' a decifrar. Cor resolve em um relance.

O que este arquivo protege e' o limite: cor e' a forma mais rapida de ranquear
sem escrever nada, e a Constituicao 0.1 proibe ranquear candidato. A cor diz em
que ponto do RITO o registro esta' — fato publicado pelo TSE — e nada mais.
"""

from __future__ import annotations

import json

from scripts.render_site import _SITUACAO, _listagem_proporcional, _marca_situacao


def test_deferido_e_verde():
    assert "m-ok" in _marca_situacao("DEFERIDO")


def test_indeferido_e_vermelho():
    assert "m-nao" in _marca_situacao("INDEFERIDO")


def test_aguardando_julgamento_e_ambar():
    assert "m-ausente" in _marca_situacao("AGUARDANDO JULGAMENTO")


def test_em_prazo_recursal_nao_e_verde_nem_vermelho():
    """A decisao ainda pode mudar. Pintar "INDEFERIDO EM PRAZO RECURSAL" de
    vermelho afirmaria um desfecho que a fonte nao declara — sobre uma pessoa
    real."""
    for v in ("DEFERIDO EM PRAZO RECURSAL OU COM RECURSO",
              "INDEFERIDO EM PRAZO RECURSAL OU COM RECURSO"):
        marca = _marca_situacao(v)
        assert "m-ausente" in marca, v
        assert "m-ok" not in marca and "m-nao" not in marca, v
        assert "não é desfecho final" in marca


def test_renuncia_e_cinza_e_nao_vermelho():
    """Renunciar e' ato do proprio candidato, nao decisao contra ele. Vermelho
    ali leria como recusa da Justica Eleitoral."""
    marca = _marca_situacao("RENÚNCIA")
    assert "m-na" in marca
    assert "m-nao" not in marca
    assert "Não é decisão da Justiça Eleitoral" in marca


def test_a_cor_nunca_carrega_a_informacao_sozinha():
    """Cerca de 8% dos homens tem alguma forma de daltonismo, e verde/vermelho e'
    justamente o par que some. O rotulo tem de estar escrito."""
    for v in _SITUACAO:
        assert v in _marca_situacao(v), v


def test_cada_situacao_explica_o_que_significa():
    """"PEDIDO NAO CONHECIDO" nao diz nada a quem nao e' do meio juridico."""
    for v in _SITUACAO:
        marca = _marca_situacao(v)
        assert 'title="' in marca and 'aria-label="' in marca, v
        assert len(_SITUACAO[v][1]) > 25, v


def test_situacao_desconhecida_nao_inventa_cor():
    """O TSE pode publicar um valor novo. Escolher verde ou vermelho por conta
    propria seria afirmar um desfecho que ninguem declarou."""
    marca = _marca_situacao("SITUACAO QUE AINDA NAO EXISTE")
    assert "m-na" in marca
    assert "SITUACAO QUE AINDA NAO EXISTE" in marca


def test_sem_situacao_nao_ha_marca():
    assert _marca_situacao(None) == "—"
    assert _marca_situacao("") == "—"


def test_a_listagem_usa_o_MESMO_mapa_e_nao_uma_copia():
    """Duas listas escritas a mao divergiriam no dia em que o TSE criasse um
    valor novo, e a listagem passaria a pintar diferente da ficha."""
    html = _listagem_proporcional(
        "deputado-federal", "Deputado Federal",
        {"SP": [{"s": "a", "sq": "1", "nome": "A", "situacao": "DEFERIDO"}]}, "x")
    serializado = json.dumps(_SITUACAO, ensure_ascii=False, separators=(",", ":"))
    assert f"const SITUACAO = {serializado};" in html


def test_nenhuma_cor_de_partido_entrou_junto():
    """Constituicao 0: cor de partido nunca e' padrao visual."""
    for _, (classe, _texto) in _SITUACAO.items():
        assert classe in {"m-ok", "m-nao", "m-ausente", "m-na"}
