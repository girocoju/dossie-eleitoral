"""O site nao pode publicar para sempre paginas que ele nao gera mais.

O gerador nao limpa o diretorio de saida, entao pagina de geracao antiga ficava
no ar indefinidamente. Medido em 03/09/2026: seis fichas vivas, entre elas
`/candidato/helio-bolsonaro-.../`, mostrando um nome de urna que o TSE nao
registra mais — a ficha atual da mesma pessoa estava em outra URL, e a velha
congelou no dia em que o nome mudou.

Duas das seis eram candidaturas com `e_registro_exibido = false`: registro
duplicado que o projeto decidiu NAO mostrar, e que continuava publicado.
"""

from __future__ import annotations

import ftplib
import json

import pytest

from scripts.publicar import (
    CARIMBO,
    LIMITE_REMOCAO,
    MANIFESTO,
    PISO_REMOCAO,
    corpo_do_manifesto,
    hashes_locais,
    listar_arquivos,
    remover_orfas,
)


class SessaoFalsa:
    def __init__(self, arvore: dict[str, list[tuple[str, dict]]] | None = None) -> None:
        self.apagados: list[str] = []
        self.recusa: set[str] = set()
        self.pastas_removidas: list[str] = []
        self.arvore = arvore or {}

    def rmd(self, caminho: str) -> None:
        self.pastas_removidas.append(caminho)

    def mlsd(self, caminho: str = "/"):
        if caminho not in self.arvore:
            raise ftplib.error_perm("550 nao lista")
        return list(self.arvore[caminho])

    def delete(self, caminho: str) -> None:
        if caminho in self.recusa:
            raise ftplib.error_perm("550 nao da")
        self.apagados.append(caminho)


def _site(tmp_path, nomes):
    for n in nomes:
        alvo = tmp_path / n
        alvo.parent.mkdir(parents=True, exist_ok=True)
        alvo.write_text("x", encoding="utf-8")
    return tmp_path


def test_listar_usa_caminho_posix_como_o_servidor(tmp_path):
    _site(tmp_path, ["index.html", "candidato/a-1/index.html"])
    assert listar_arquivos(tmp_path) == ["candidato/a-1/index.html", "index.html"]


def test_remove_o_que_saiu_do_ar(tmp_path):
    s = SessaoFalsa()
    anterior = ["index.html", "candidato/helio-bolsonaro-1/index.html"]
    atuais = ["index.html", "candidato/helio-fernando-1/index.html"]
    n = remover_orfas(s, "/", atuais, anterior)
    assert n == 1
    # raiz "/" -> base vazia, caminho relativo, igual ao que `enviar` usa
    assert s.apagados == ["candidato/helio-bolsonaro-1/index.html"]


def test_nao_toca_no_que_nunca_esteve_no_manifesto(tmp_path):
    """Arquivo posto no servidor a mao nao e' nosso para apagar."""
    s = SessaoFalsa()
    remover_orfas(s, "/", ["index.html"], ["index.html"])
    assert s.apagados == []


def test_manifesto_e_carimbo_nunca_sao_removidos():
    s = SessaoFalsa()
    remover_orfas(s, "/", ["index.html"], ["index.html", MANIFESTO, CARIMBO])
    assert s.apagados == []


def test_sem_manifesto_varre_o_servidor_uma_vez():
    """As orfas que ja' estao no ar nunca entraram em manifesto nenhum.

    Sem esta varredura elas ficariam para sempre: a limpeza compara contra o
    manifesto, e o manifesto so' passa a existir a partir da primeira publicacao
    com a limpeza ligada.
    """
    s = SessaoFalsa({
        "/": [("index.html", {"type": "file"}), ("candidato", {"type": "dir"})],
        "/candidato": [("helio-bolsonaro-1", {"type": "dir"})],
        "/candidato/helio-bolsonaro-1": [("index.html", {"type": "file"})],
    })
    n = remover_orfas(s, "/", ["index.html"], None)
    assert n == 1
    assert s.apagados == ["candidato/helio-bolsonaro-1/index.html"]


def test_varredura_que_nao_devolve_nada_nao_remove():
    """Servidor que recusa listagem nao pode virar 'entao apague tudo'."""
    s = SessaoFalsa()
    assert remover_orfas(s, "/", ["index.html"], None) == 0
    assert s.apagados == []


def test_geracao_truncada_nao_apaga_o_site():
    """O teto existe para isto: poucos arquivos gerados NAO significa site vazio."""
    s = SessaoFalsa()
    anterior = [f"p{i}.html" for i in range(100)]
    atuais = ["p0.html"]                       # geracao que falhou pela metade
    with pytest.raises(SystemExit) as exc:
        remover_orfas(s, "/", atuais, anterior)
    assert "RECUSADO" in str(exc.value)
    assert "--forcar" in str(exc.value)
    assert s.apagados == [], "nada pode ser apagado antes da recusa"


def test_forcar_permite_a_remocao_grande():
    s = SessaoFalsa()
    anterior = [f"p{i}.html" for i in range(100)]
    n = remover_orfas(s, "/", ["p0.html"], anterior, forcar=True)
    assert n == 99


def test_remocao_dentro_do_teto_passa():
    s = SessaoFalsa()
    anterior = [f"p{i}.html" for i in range(100)]
    atuais = [f"p{i}.html" for i in range(90)]  # 10% saiu
    assert 10 / 100 <= LIMITE_REMOCAO
    assert remover_orfas(s, "/", atuais, anterior) == 10


def test_falha_ao_apagar_uma_nao_derruba_a_publicacao():
    """O site ja' subiu inteiro; nao apagar uma orfa nao justifica abortar."""
    s = SessaoFalsa()
    s.recusa = {"b.html"}
    n = remover_orfas(s, "/", [], ["a.html", "b.html", "c.html"], forcar=True)
    assert n == 2 and "b.html" not in s.apagados


def test_o_manifesto_gravado_traz_nome_e_hash(tmp_path):
    """Formato v2 (ADR-039). O v1 era so' a lista de nomes."""
    _site(tmp_path, ["index.html"])
    nomes = listar_arquivos(tmp_path)
    lido = json.loads(corpo_do_manifesto(hashes_locais(tmp_path, nomes)))
    assert lido["versao"] == 2
    assert set(lido["arquivos"]) == {"index.html"}
    assert len(lido["arquivos"]["index.html"]) == 16


def test_o_proprio_manifesto_nunca_entra_na_lista(tmp_path):
    """Ele sobe por ultimo e sozinho — entrar em `atuais` o faria subir no meio,
    afirmando o fim da publicacao antes da hora."""
    _site(tmp_path, ["index.html"])
    (tmp_path / MANIFESTO).write_text("{}", encoding="utf-8")
    assert listar_arquivos(tmp_path) == ["index.html"]


def test_punhado_de_orfas_nunca_precisa_de_forcar():
    """Churn normal — ficha que mudou de URL — nao pode exigir intervencao.

    Sem o piso, uma orfa num site de duas paginas seria 50% e travaria.
    """
    s = SessaoFalsa()
    anterior = ["a.html", "b.html"]
    assert remover_orfas(s, "/", ["a.html"], anterior) == 1
    assert PISO_REMOCAO >= 20


def test_varredura_incompleta_nao_dirige_remocao():
    """Inventario parcial tratado como completo apagaria o que nao foi visto.

    A conexao TLS cai no meio da varredura (`SSL: BAD_LENGTH`, 03/09/2026), e uma
    listagem que morre devolve MENOS arquivos — o que parece um inventario limpo.
    """
    s = SessaoFalsa({
        "/": [("index.html", {"type": "file"}), ("candidato", {"type": "dir"})],
        # /candidato nao esta' na arvore: a listagem dele falha, como a conexao
        # que cai no meio.
    })
    assert remover_orfas(s, "/", ["index.html"], None) == 0
    assert s.apagados == [], "varredura incompleta nao pode apagar nada"


def test_pasta_que_ficou_vazia_tambem_sai():
    """So' apagar o index deixa a pasta, e o servidor responde 403 em vez de 404.

    403 e' pior para quem chega por link antigo: "proibido" sugere que existe
    algo ali.
    """
    s = SessaoFalsa()
    remover_orfas(s, "/", ["index.html"],
                  ["index.html", "candidato/helio-bolsonaro-1/index.html"])
    assert s.pastas_removidas == ["candidato/helio-bolsonaro-1"]


def test_pasta_com_arquivo_vivo_nao_e_removida():
    s = SessaoFalsa()
    remover_orfas(s, "/", ["candidato/a-1/index.html"],
                  ["candidato/a-1/index.html", "candidato/a-1/plano/index.html",
                   "candidato/a-1/velho.html"])
    assert "candidato/a-1" not in s.pastas_removidas
