"""Comissoes do Senado na ficha (F-29 / ADR-048).

A L-28 dizia que este bloco nao podia existir sem CPF. A premissa estava errada:
o bloco de atividade legislativa do Senado ja' estava no ar com a MESMA
identidade inferida e uma ressalva na tela. O criterio mais duro nao era
prudencia — era um bloco a menos por uma regra que o projeto nao tinha.

Este arquivo protege os quatro jeitos de o bloco mentir:

  - deduzir a natureza do colegiado da SIGLA (a armadilha do ADR-034);
  - exibir assento sem dizer que a identidade e' inferida;
  - deixar o leitor supor que quem nao aparece como Presidente nunca presidiu,
    quando a fonte simplesmente nao tem esse papel;
  - chamar frente e grupo de amizade de assento.
"""

from __future__ import annotations

from ingest.comissoes_senado import (
    CLASSES,
    CLASSES_DE_COLEGIADO,
    _classe_por_nome,
    _classificar,
)
from scripts.gerar_site import CLASSES_COMISSAO, Candidato
from scripts.render_site import _comissoes_senado, _papel_legivel
from tests.conftest import contem_frase, texto_visivel


def _cand(**kw):
    campos = dict(
        sk="sk-1", sq="70002540001", cod_cargo=5, nome_urna="SEN EXEMPLO",
        nome_completo="SEN EXEMPLO", sg_uf="SP", sigla_partido="PT",
        nome_partido="PT", nr_candidato=130, coligacao=None, composicao=None,
        federacao=None, situacao="DEFERIDO", url_foto=None, idade=60,
        genero=None, cor_raca=None, grau_instrucao=None, ocupacao=None,
        uf_nascimento=None, bens_total=None, bens_n=None,
        proposta_obrigatoria=False, tem_proposta=False, url_proposta=None,
    )
    campos.update(kw)
    return Candidato(**campos)


COLEGIADOS = [
    {"classe": "permanente", "sigla": "CDH",
     "nome": "Comissão de Direitos Humanos e Legislação Participativa",
     "tipo": "Comissão permanente", "papel": "Titular", "vezes": 12,
     "em_curso": True, "a1": 2005, "a2": 2026,
     "papel_maximo": "Titular", "cargos": 0, "comanda": False,
     "deduzido": False, "confiavel": False},
    {"classe": "temporaria", "sigla": "CPMIINSS",
     "nome": "CPMI - INSS", "tipo": "Comissão parlamentar mista de inquérito",
     "papel": "Titular", "vezes": 1, "em_curso": True, "a1": 2025, "a2": 2026,
     "papel_maximo": "Titular", "cargos": 0, "comanda": False,
     "deduzido": True, "confiavel": False},
]

# Vem da rota de cargos: papel de comando, e um colegiado que a lista de
# comissoes nao conhece. `vezes` = 0 de proposito — a fonte publica o cargo sem
# publicar a designacao.
PRESIDENCIA = {
    "classe": "mesa", "sigla": "Mesa",
    "nome": "Mesa Diretora do Congresso Nacional", "tipo": "Mesa",
    "papel": "PRESIDENTE", "papel_maximo": "PRESIDENTE", "vezes": 0, "cargos": 2,
    "em_curso": True, "comanda": True, "a1": 2025, "a2": 2026,
    "deduzido": False, "confiavel": False,
}


# ── a natureza vem do CODIGO, e o nome so' quando nao ha' codigo ──────────

def test_o_codigo_do_catalogo_tem_prioridade_sobre_o_nome():
    """Quando a fonte diz o tipo, e' o tipo da fonte que vale — o nome nunca
    sobrescreve o catalogo."""
    cod = next(iter(CLASSES))
    classe, _, origem = _classificar(cod, "Comissão Parlamentar de Inquérito")
    assert origem == "catalogo"
    assert classe == CLASSES[cod][0]


def test_o_nome_so_entra_quando_o_catalogo_nao_conhece():
    _, _, origem = _classificar(None, "Comissão Parlamentar Mista de Inquérito")
    assert origem == "nome"


def test_sem_codigo_e_sem_nome_reconhecivel_o_vinculo_fica_de_fora():
    """Regra 5: preferir a linha ausente a' linha errada."""
    classe, _, origem = _classificar(None, "CT - Reforma do Código de Processo Civil")
    assert origem == "nenhuma"
    assert classe == "desconhecida"
    assert classe not in CLASSES_DE_COLEGIADO


def test_a_forma_mais_especifica_vence_a_mais_geral():
    """"Comissao Parlamentar Mista de Inquerito" CONTEM "Comissao Mista". Se a
    ordem se inverter, toda CPMI vira comissao mista comum."""
    classe, rotulo = _classe_por_nome("Comissão Parlamentar Mista de Inquérito - Fake News")
    assert classe == "temporaria"
    assert "inquérito" in rotulo.lower()


def test_a_sigla_solta_nunca_classifica():
    """A armadilha do ADR-034: `RQI` parece "Requerimento de Informacao" e e'
    outra coisa. Um nome que so' tem a sigla no meio nao classifica nada."""
    assert _classe_por_nome("Reunião conjunta CPI/CAE sobre orçamento") is None
    assert _classe_por_nome("CSF") is None


def test_a_abreviacao_oficial_vale_ancorada_no_inicio():
    """A fonte escreve ora por extenso, ora "CPI da Pandemia". Um nome que
    COMECA com a abreviacao oficial e' inequivoco — 40 vinculos da CPI do Crime
    Organizado dependem disto."""
    classe, _ = _classe_por_nome("CPI da Pandemia")
    assert classe == "temporaria"
    assert _classe_por_nome("CPMI - INSS")[0] == "temporaria"


def test_frente_e_grupo_de_amizade_nao_sao_assento():
    """Adesao aberta nao e' cadeira. Mesma regra da Camara."""
    assert "frente" not in CLASSES_DE_COLEGIADO
    assert "grupo_amizade" not in CLASSES_DE_COLEGIADO


def test_toda_classe_exibivel_tem_rotulo_na_tela():
    for classe in CLASSES_DE_COLEGIADO:
        assert classe in CLASSES_COMISSAO


def test_todo_codigo_mapeado_tem_rotulo_em_portugues():
    for cod, (classe, rotulo) in CLASSES.items():
        assert rotulo and rotulo[0].isupper(), cod
        assert classe.islower(), cod


# ── a tela ────────────────────────────────────────────────────────────────

def test_a_ficha_mostra_o_colegiado_o_papel_e_o_periodo():
    html = _comissoes_senado(_cand(comissoes_senado=COLEGIADOS))
    t = texto_visivel(html)
    assert "CDH" in t
    assert "Titular" in t
    assert "2005" in t


def test_a_tela_diz_que_a_identidade_e_inferida():
    """Sem esta frase o bloco afirma, com a mesma confianca do da Camara, um
    assento que foi atribuido por nome e data de nascimento."""
    t = texto_visivel(_comissoes_senado(_cand(comissoes_senado=COLEGIADOS)))
    assert contem_frase(t, "identidade aqui é inferida")
    assert contem_frase(t, "nome e data de nascimento")


def test_a_presidencia_aparece_e_vem_destacada():
    """Ate' 05/09/2026 a fonte parecia nao publicar papel de comando — era a
    L-30. Publica, por outra rota: `/senador/{cod}/cargos` (ADR-049).

    Presidir a CCJ e ser suplente dela nao sao a mesma informacao, e a tabela
    ficaria plana se as duas linhas pesassem igual."""
    html = _comissoes_senado(_cand(comissoes_senado=COLEGIADOS + [PRESIDENCIA]))
    assert "<b>Presidente</b>" in html
    assert "Mesa Diretora do Congresso Nacional" in texto_visivel(html)


def test_a_tela_explica_que_o_papel_e_o_de_agora():
    """Quem presidiu a CDH em 2015 e segue titular dela hoje tem os dois fatos.
    A tabela nao pode transformar o primeiro em "presidente, em curso"."""
    t = texto_visivel(_comissoes_senado(_cand(comissoes_senado=COLEGIADOS)))
    assert contem_frase(t, "O papel mostrado é o de agora")


def test_a_tela_explica_a_segunda_rota_e_a_falta_de_designacao():
    t = texto_visivel(_comissoes_senado(_cand(comissoes_senado=COLEGIADOS)))
    assert contem_frase(t, "Mesa Diretora do Congresso")
    assert contem_frase(t, "sem contagem de designações")


def test_o_papel_em_caixa_alta_e_normalizado():
    """A rota de comissoes escreve "Titular"; a de cargos escreve "PRESIDENTE".
    Sem normalizar, a mesma coluna alterna de caixa linha a linha e o leitor le'
    a caixa alta como enfase — que nao existe no dado."""
    assert _papel_legivel("PRESIDENTE") == "Presidente"
    assert _papel_legivel("1º VICE-PRESIDENTE") == "1º vice-presidente"
    assert _papel_legivel("PRESIDENTE DO CONSELHO CONSULTIVO") == \
        "Presidente do conselho consultivo"


def test_o_que_a_fonte_ja_escreveu_bem_nao_e_mexido():
    """"Titular" e "Relator da Receita" vem certos. Passa-los pela normalizacao
    quebraria o que estava bom."""
    assert _papel_legivel("Titular") == "Titular"
    assert _papel_legivel("Relator da Receita") == "Relator da Receita"
    assert _papel_legivel("") == ""
    assert _papel_legivel(None) == ""


def test_a_tela_diz_que_frente_e_grupo_ficam_de_fora():
    t = texto_visivel(_comissoes_senado(_cand(comissoes_senado=COLEGIADOS)))
    assert contem_frase(t, "adesão aberta, não assento")


def test_a_tela_conta_quantos_tiveram_a_natureza_deduzida():
    """A procedencia da classe viaja ate' o leitor: um colegiado desta lista teve
    o tipo lido do nome, e a ficha diz isso em vez de esconder."""
    t = texto_visivel(_comissoes_senado(_cand(comissoes_senado=COLEGIADOS)))
    assert contem_frase(t, "nome oficial por extenso")
    assert contem_frase(t, "1 colegiado já encerrado")


def test_sem_deducao_a_tela_nao_fala_de_deducao():
    """Dizer "0 colegiados deduzidos" numa ficha em que todos vieram do catalogo
    seria ruido."""
    so_catalogo = [dict(COLEGIADOS[0])]
    t = texto_visivel(_comissoes_senado(_cand(comissoes_senado=so_catalogo)))
    assert "nome oficial por extenso" not in t


def test_o_bloco_agrupa_por_natureza_do_colegiado():
    t = texto_visivel(_comissoes_senado(_cand(comissoes_senado=COLEGIADOS)))
    assert CLASSES_COMISSAO["permanente"] in t
    assert CLASSES_COMISSAO["temporaria"] in t


def test_sem_colegiado_nao_ha_bloco():
    assert _comissoes_senado(_cand()) == ""


# ── a segunda rota, que fechou a L-30 (ADR-049) ───────────────────────────

def test_a_medida_provisoria_nao_vira_comissao_mista():
    """A rota de cargos escreve "Comissao Mista da Medida Provisoria n 1154",
    que CONTEM "Comissao Mista". Sem a regra da MPV testada antes, toda comissao
    de MPV viraria mista comum e afogaria a ficha — sao rotina, como na Camara."""
    classe, _ = _classe_por_nome("Comissão Mista da Medida Provisória n° 1154, de 2023")
    assert classe == "medida_provisoria"
    assert classe not in CLASSES_DE_COLEGIADO


def test_a_comissao_mista_comum_continua_mista():
    """A regra da MPV nao pode ter engolido a classe que ela protege."""
    assert _classe_por_nome("Comissão Mista de Planos e Orçamentos")[0] == "mista"


def test_a_mesa_e_colegiado_exibivel():
    """A Mesa Diretora e' o assento mais visivel do pais e so' existe na rota de
    cargos. Se ela nao for exibivel, a L-30 nao fechou."""
    assert "mesa" in CLASSES_DE_COLEGIADO
    assert "mesa" in CLASSES_COMISSAO


def test_o_vinculo_carrega_de_qual_rota_veio():
    """Sem `origem_do_vinculo` o mart nao consegue separar designacao de cargo, e
    "designado 4 vezes" apareceria onde houve duas designacoes e duas
    presidencias."""
    from dataclasses import fields

    from ingest.comissoes_senado import Vinculo

    assert "origem_do_vinculo" in {f.name for f in fields(Vinculo)}
