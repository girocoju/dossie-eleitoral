"""O vice tem ficha propria, e ela precisa dizer o que e' um vice (ADR-032).

Ate' 01/09/2026 o vice existia no site apenas como cartao na ficha do titular:
nome, foto e partido, sem pagina onde a propria trajetoria coubesse. Geraldo
Alckmin — tres mandatos de governador de Sao Paulo — nao tinha onde mostrar
nenhum deles.
"""

from __future__ import annotations

from types import SimpleNamespace

from scripts.gerar_site import CARGOS, VICES
from scripts.render_site import _chapa, _chapa_titular


def _cand(cod_cargo=2, chapa=None, titular=None, financiamento=None):
    return SimpleNamespace(
        cod_cargo=cod_cargo, chapa=chapa or [], chapa_titular=titular,
        financiamento=financiamento or [])


def test_vice_de_presidente_e_de_governador_tem_cargo_no_catalogo():
    assert VICES == {2, 4}
    for cod in VICES:
        assert cod in CARGOS, "sem entrada em CARGOS nao ha' listagem nem ficha"
    assert CARGOS[2][0] == "vice-presidente"
    assert CARGOS[4][0] == "vice-governador"


def test_a_ficha_do_vice_mostra_e_linka_o_titular():
    t = {"nome": "FLAVIO BOLSONARO", "completo": "FLAVIO NANTES BOLSONARO",
         "cargo": "Presidente", "partido": "PL", "foto": None,
         "url": "https://x/candidato/flavio-1/"}
    html = _chapa_titular(_cand(titular=t))
    assert "Concorre na chapa de" in html
    assert 'href="https://x/candidato/flavio-1/"' in html


def test_a_ficha_do_vice_diz_que_vice_nao_recebe_voto_proprio():
    """Sem isso, a ficha sugere uma candidatura que se elege sozinha."""
    t = {"nome": "X", "completo": "X", "cargo": "Governador", "partido": "P",
         "foto": None, "url": "https://x/c/1/"}
    assert "não recebe voto próprio" in _chapa_titular(_cand(titular=t))


def test_titular_sem_vice_nao_gera_bloco():
    assert _chapa_titular(_cand(titular=None)) == ""
    assert _chapa(_cand(cod_cargo=1, chapa=[])) == ""


def test_o_cartao_do_vice_linka_quando_ha_ficha():
    com = [{"cargo": "Vice-governador", "nome": "V", "completo": "V V",
            "partido": "P", "foto": None, "url": "https://x/candidato/v-2/"}]
    sem = [dict(com[0], url=None)]
    assert 'href="https://x/candidato/v-2/"' in _chapa(_cand(cod_cargo=3, chapa=com))
    # Suplente de senador nao tem ficha; link quebrado seria pior que ausencia.
    assert "href=" not in _chapa(_cand(cod_cargo=5, chapa=sem)).split("</div>")[0]


def test_o_titulo_da_chapa_vem_do_cargo_nao_da_contagem():
    """MARA ROCHA (Senadora) tinha UM suplente e a ficha o chamava de "Vice"."""
    um = [{"cargo": "1º Suplente", "nome": "S", "completo": "S", "partido": "P",
           "foto": None, "url": None}]
    assert "<h2>Suplente da chapa</h2>" in _chapa(_cand(cod_cargo=5, chapa=um))
    assert "<h2>Vice da chapa</h2>" in _chapa(_cand(cod_cargo=3, chapa=um))


def test_financiamento_do_vice_nao_promete_dado_que_nao_vem():
    """Medido em 01/09/2026: titulares 55-85% de cobertura, vices ZERO."""
    from scripts.render_site import _financiamento

    t = {"nome": "TITULAR", "completo": "T", "cargo": "Governador",
         "partido": "P", "foto": None, "url": "https://x/c/1/"}
    html = _financiamento(_cand(cod_cargo=4, titular=t))
    assert "a prestação é da chapa" in html
    assert "ainda não consta" not in html, (
        "dizer 'ainda nao entregue' promete um dado que nunca vai chegar")
    assert 'href="https://x/c/1/"' in html
