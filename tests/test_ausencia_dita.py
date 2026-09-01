"""A ausencia de um indicador precisa ser DITA, nao apenas respeitada.

A Regra 5 proibe preencher buraco de dado, e o bloco de mandato cumpre: onde a
serie nao alcanca a janela, a linha nao existe. Mas omitir sem dizer que omitiu
deixa o leitor sem distinguir "nao ha' dado" de "esconderam" ou de "o site esta'
pela metade".

Em 01/09/2026 o proprio dono do projeto perguntou por que a ficha do Lula nao
mostrava desemprego nos mandatos de 2003-2006 e 2007-2010 — a PNAD Continua
comeca em 2012 (L-06). Se ele precisou perguntar, o leitor tambem precisaria.
"""

from __future__ import annotations

import re
from types import SimpleNamespace

from scripts.render_site import _indicadores, _nota_ausencias


def _linha(cod, a1, a2, ue="BRASIL", cargo=1):
    return {"cod": cod, "indicador": cod, "unidade": "%", "ue": ue,
            "uf": "BR" if ue == "BRASIL" else "GO", "cargo": cargo,
            "a1": a1, "a2": a2, "ref1": a1 - 1, "ref2": a2, "v1": 1.0, "v2": 2.0,
            "pct": 10.0, "pct_br": 5.0, "delta": 5.0, "incompleta": False}


def _ausente(cod, motivo, s1, s2, a1, a2, ue="BRASIL", cargo=1):
    return {"a1": a1, "a2": a2, "ue": ue,
            "uf": "BR" if ue == "BRASIL" else "GO", "cargo": cargo, "cod": cod,
            "motivo": motivo, "s1": s1, "s2": s2}


def _notas(html):
    return [re.sub(r"<[^>]+>", "", " ".join(m.split()))
            for m in re.findall(r"<p style=\"font-size:12.5px[^>]*>(.*?)</p>", html, re.S)]


def test_o_caso_que_originou_isto_o_lula_sem_desemprego():
    c = SimpleNamespace(
        indicadores=[_linha("IPCA", 2003, 2006)],
        indicadores_ausentes=[
            _ausente("DESOCUPACAO", "serie_comeca_depois", 2012, 2025, 2003, 2006)])
    nota = _notas(_indicadores(c))[0]
    assert "Desemprego" in nota
    assert "série começa em 2012" in nota, (
        "sem dizer POR QUE falta, a omissao continua muda")


def test_indicadores_com_o_mesmo_motivo_sao_agrupados():
    """Uma frase por motivo, nao um parenteses repetido por indicador."""
    c = SimpleNamespace(
        indicadores=[_linha("IPCA", 2003, 2006)],
        indicadores_ausentes=[
            _ausente("DESOCUPACAO", "serie_comeca_depois", 2012, 2025, 2003, 2006),
            _ausente("RENDIMENTO_MEDIO", "serie_comeca_depois", 2012, 2025, 2003, 2006)])
    nota = _notas(_indicadores(c))[0]
    assert nota.count("série começa em 2012") == 1
    assert "Desemprego e Rendimento do trabalho" in nota


def test_cada_bloco_recebe_so_as_suas_ausencias():
    c = SimpleNamespace(
        indicadores=[_linha("IPCA", 2003, 2006), _linha("IPCA", 2023, 2026)],
        indicadores_ausentes=[
            _ausente("DESOCUPACAO", "serie_comeca_depois", 2012, 2025, 2003, 2006),
            _ausente("MORTALIDADE_INFANTIL", "serie_termina_antes", 2000, 2016, 2023, 2026)])
    notas = _notas(_indicadores(c))
    assert len(notas) == 2
    recente, antigo = notas          # blocos saem do mais recente para o mais antigo
    assert "Mortalidade infantil" in recente and "Desemprego" not in recente
    assert "Desemprego" in antigo and "Mortalidade infantil" not in antigo


def test_o_rotulo_da_ausencia_segue_o_ente_governado():
    """"PIB do estado" numa ficha presidencial seria falso tambem na ausencia."""
    faltando = [_ausente("PIB", "serie_comeca_depois", 2020, 2025, 2003, 2006)]
    assert "PIB do Brasil" in _nota_ausencias(faltando, nacional=True)
    assert "PIB do estado" in _nota_ausencias(faltando, nacional=False)


def test_a_frase_mais_explicativa_vem_primeiro():
    faltando = [
        _ausente("IDHM", "serie_nao_cobre_a_janela", 1991, 2010, 2003, 2006),
        _ausente("DESOCUPACAO", "serie_comeca_depois", 2012, 2025, 2003, 2006)]
    nota = re.sub(r"<[^>]+>", "", _nota_ausencias(faltando, nacional=True))
    assert nota.index("começa em 2012") < nota.index("1991–2010"), (
        "ordem alfabetica jogaria o caso de canto na frente do caso comum")


def test_sem_ausencia_nenhuma_nao_ha_nota():
    assert _nota_ausencias([], nacional=True) == ""
    c = SimpleNamespace(indicadores=[_linha("IPCA", 2003, 2006)], indicadores_ausentes=[])
    assert _notas(_indicadores(c)) == []


def test_a_nota_diz_que_nada_foi_estimado():
    """A Regra 5 na tela: ausencia nomeada, e a garantia de que nao virou numero."""
    faltando = [_ausente("DESOCUPACAO", "serie_comeca_depois", 2012, 2025, 2003, 2006)]
    assert "Nada foi estimado" in _nota_ausencias(faltando, nacional=True)
