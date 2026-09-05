"""O relatorio analitico em PDF (F-28).

A primeira edicao foi montada fora do repositorio e ficou orfa: os numeros
estavam escritos no texto e envelheceram em silencio — "a UNICA candidatura
acima de R$ 1 bilhao" quando ja' eram duas, "72 trocas de cargo" quando eram 73,
"a ficha de senador nao traz comissoes" quando ja' trazia.

Nenhum teste automatico pega um numero desatualizado. O que da' para proteger e'
a ESTRUTURA que impede o numero de ser digitado: se o gerador le' do dado, ele
nao pode divergir do site. Estes testes protegem isso.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
GERADOR = (RAIZ / "scripts" / "gerar_relatorio.py").read_text(encoding="utf-8")
COLETOR = (RAIZ / "scripts" / "dados_relatorio.py").read_text(encoding="utf-8")


def test_a_coleta_le_os_mesmos_marts_do_site():
    """Caminho paralelo e' como um relatorio passa a discordar da ficha sobre a
    mesma pessoa. Tudo sai de `marts` (ou de `stg`, para o que o mart nao expoe
    de proposito, como o valor do item de bem)."""
    fontes = set(re.findall(r"`\{p\}\.(\w+)\.", COLETOR))
    assert fontes <= {"marts", "stg"}, fontes


def test_nenhuma_consulta_fora_do_coletor():
    """CLAUDE.md: nenhum SQL fora do dbt — e, aqui, nenhuma consulta fora do
    modulo de coleta. O gerador so' formata."""
    assert " from `" not in GERADOR.lower()
    assert "cliente" not in GERADOR


def test_o_gerador_nao_tem_numero_de_candidatura_escrito_a_mao():
    """Um total como "20.162" no texto e' o erro que esta suite existe para
    impedir: ele fica bonito e fica errado. Numeros de quatro ou cinco digitos
    com separador de milhar nao entram no codigo do gerador.

    A excecao sao os poucos que NAO vem deste pipeline e estao ancorados em
    fonte externa citada no proprio texto — o Censo, o catalogo de MPV, a
    contagem de vinculos ja' publicada num ADR.
    """
    ancorados = {
        # medicoes ja' publicadas num ADR ou numa lacuna, com data
        "1.393", "79.140", "1.228.019", "402.446", "829.989", "15.962",
        "11.771", "11.778", "13.731", "19.263", "6.699", "1.649", "1.060",
        "1.483", "7.226", "4.645", "73.856",
        # conferencias contra fonte externa, citadas no proprio texto
        "94.463", "68.366",
        # o caso: a hipotese do separador decimal, e o item redondo
        "1.109.124", "1.109.124.020", "3.000.000",
        # Lei 9.504/97
        "9.504",
    }
    achados = set(re.findall(r"\b\d{1,3}(?:\.\d{3})+\b", GERADOR)) - ancorados
    assert not achados, f"numero escrito a mao no gerador: {sorted(achados)}"


def test_o_pdf_espera_o_arquivo_terminar():
    """O navegador sai antes de terminar de gravar. Medir o tamanho ali reporta
    um numero menor que o real — um log que mente sobre o proprio produto."""
    assert "%%EOF" in GERADOR


def test_o_navegador_usa_headless_new():
    """O `--headless` antigo renderiza UMA pagina e descarta o resto. O erro nao
    aparece como erro: aparece como um PDF curto que parece pronto."""
    assert "--headless=new" in GERADOR
    assert '"--headless"' not in GERADOR


def test_a_descricao_do_bem_nunca_e_coletada():
    """Texto livre com endereco residencial, placa e CNPJ (ADR-041). O que nao
    chega ao JSON nao chega ao PDF por descuido de quem escrever a proxima
    secao."""
    # O nome aparece em comentario nos dois arquivos, explicando POR QUE nao
    # entra. O que nao pode e' ele estar numa consulta ou numa interpolacao.
    def sem_comentario(txt: str) -> str:
        vivas = [ln for ln in txt.splitlines() if not ln.lstrip().startswith("#")]
        return " ".join(vivas)

    assert "descricao_bem" not in sem_comentario(COLETOR)
    assert "descricao_bem" not in sem_comentario(GERADOR)


def test_o_json_de_dados_cobre_o_que_o_gerador_le():
    """Uma chave que o gerador le' e a coleta nao grava e' um KeyError no meio
    da geracao — que foi exatamente como esta migracao quebrou na primeira
    tentativa."""
    dados = RAIZ / "data" / "relatorio" / "dados.json"
    if not dados.exists():
        return  # sem coleta local, nao ha' o que conferir
    tem = set(json.loads(dados.read_text(encoding="utf-8")))
    lidas = set(re.findall(r'D\["(\w+)"\]', GERADOR))
    assert lidas <= tem, f"o gerador le' o que a coleta nao grava: {sorted(lidas - tem)}"
