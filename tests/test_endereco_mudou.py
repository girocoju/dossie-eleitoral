"""Ficha que mudou de endereco porque o nome de urna foi corrigido (F-30).

O endereco da ficha e' `slug(nome_urna)-sq`. O `sq` identifica a candidatura e
nao muda; o slug muda toda vez que a pessoa corrige o nome no TSE. Como o gerador
escreve e nunca apaga, o endereco velho sobrevivia a cada publicacao servindo a
grafia que a propria pessoa pediu para corrigir.

Medido em 05/09/2026: 7 candidaturas com dois enderecos, todas por correcao de
grafia — "RAFAEL DULTRA" para "RAFAEL DUTRA", "CAPITAO RODOLDO" para "CAPITAO
RODOLFO", "NEUMARA" para "NEMAURA".
"""

from __future__ import annotations

from scripts import render_site
from scripts.gerar_site import Candidato


def _cand(nome, sq):
    return Candidato(
        sk=f"sk-{sq}", sq=sq, cod_cargo=7, nome_urna=nome, nome_completo=nome,
        sg_uf="SP", sigla_partido="PT", nome_partido="PT", nr_candidato=13000,
        coligacao=None, composicao=None, federacao=None, situacao="DEFERIDO",
        url_foto=None, idade=40, genero=None, cor_raca=None, grau_instrucao=None,
        ocupacao=None, uf_nascimento=None, bens_total=None, bens_n=None,
        proposta_obrigatoria=False, tem_proposta=False, url_proposta=None,
    )


def _monta(tmp_path, antigo, novo, sq="10002544022"):
    """Simula o estado real: o diretorio antigo ja' no disco, o novo recem-escrito."""
    c = _cand(novo, sq)
    for slug in (f"candidato/{antigo}-{sq}", c.caminho):
        d = tmp_path / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(f"ficha de {slug}", encoding="utf-8")
    return c


def test_o_endereco_antigo_vira_encaminhamento(tmp_path):
    c = _monta(tmp_path, "rafael-dultra", "RAFAEL DUTRA")
    assert render_site._redirecionar_enderecos_antigos(tmp_path, [c]) == 1
    antigo = (tmp_path / "candidato" / "rafael-dultra-10002544022"
              / "index.html").read_text(encoding="utf-8")
    assert "canonical" in antigo
    assert "refresh" in antigo
    assert c.caminho in antigo


def test_a_grafia_corrigida_nao_e_republicada_na_pagina_de_encaminhamento(tmp_path):
    """Repetir o nome antigo ali seria continuar publicando exatamente o que se
    quer parar de publicar."""
    c = _monta(tmp_path, "rafael-dultra", "RAFAEL DUTRA")
    render_site._redirecionar_enderecos_antigos(tmp_path, [c])
    antigo = (tmp_path / "candidato" / "rafael-dultra-10002544022"
              / "index.html").read_text(encoding="utf-8")
    assert "DULTRA" not in antigo.upper().replace("RAFAEL-DULTRA", "")


def test_o_endereco_antigo_nao_e_apagado(tmp_path):
    """Apagar transforma em 404 todo link ja' compartilhado — e este site existe
    para ser citado."""
    c = _monta(tmp_path, "rafael-dultra", "RAFAEL DUTRA")
    render_site._redirecionar_enderecos_antigos(tmp_path, [c])
    assert (tmp_path / "candidato" / "rafael-dultra-10002544022" / "index.html").exists()


def test_o_encaminhamento_nao_e_indexado(tmp_path):
    """Duas URLs com o mesmo conteudo competem entre si no buscador."""
    c = _monta(tmp_path, "neumara", "NEMAURA")
    render_site._redirecionar_enderecos_antigos(tmp_path, [c])
    antigo = (tmp_path / "candidato" / "neumara-10002544022"
              / "index.html").read_text(encoding="utf-8")
    assert "noindex" in antigo


def test_a_ficha_atual_nao_e_tocada(tmp_path):
    c = _monta(tmp_path, "rafael-dultra", "RAFAEL DUTRA")
    render_site._redirecionar_enderecos_antigos(tmp_path, [c])
    atual = (tmp_path / c.caminho / "index.html").read_text(encoding="utf-8")
    assert atual.startswith("ficha de")


def test_sem_mudanca_de_nome_nada_acontece(tmp_path):
    c = _cand("RAFAEL DUTRA", "10002544022")
    d = tmp_path / c.caminho
    d.mkdir(parents=True)
    (d / "index.html").write_text("ficha", encoding="utf-8")
    assert render_site._redirecionar_enderecos_antigos(tmp_path, [c]) == 0
    assert (d / "index.html").read_text(encoding="utf-8") == "ficha"


def test_diretorio_de_candidatura_que_saiu_do_ar_nao_e_mexido(tmp_path):
    """Ficha de quem deixou de ser exibido nao vira encaminhamento para lugar
    nenhum: nao ha' destino. Ela fica como esta', e a decisao sobre remover e'
    outra — esta funcao nao inventa um alvo."""
    c = _cand("RAFAEL DUTRA", "10002544022")
    (tmp_path / c.caminho).mkdir(parents=True)
    (tmp_path / c.caminho / "index.html").write_text("ficha", encoding="utf-8")
    fora = tmp_path / "candidato" / "alguem-99999999999"
    fora.mkdir(parents=True)
    (fora / "index.html").write_text("ficha antiga", encoding="utf-8")
    render_site._redirecionar_enderecos_antigos(tmp_path, [c])
    assert (fora / "index.html").read_text(encoding="utf-8") == "ficha antiga"


def test_a_pagina_do_plano_tambem_encaminha(tmp_path):
    c = _monta(tmp_path, "rafael-dultra", "RAFAEL DUTRA")
    plano = tmp_path / "candidato" / "rafael-dultra-10002544022" / "plano"
    plano.mkdir(parents=True)
    (plano / "index.html").write_text("plano antigo", encoding="utf-8")
    render_site._redirecionar_enderecos_antigos(tmp_path, [c])
    assert "plano/" in (plano / "index.html").read_text(encoding="utf-8")
