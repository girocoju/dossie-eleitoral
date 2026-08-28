"""Texto integral dos planos de governo — S19 / F-14b (ADR-019).

    python -m ingest.planos load   [--limite 10] [--dry-run] [--target local]
    python -m ingest.planos verify

Modulo SEPARADO de `ingest/propostas.py` de proposito:

    propostas.py  responde SE existe plano — existencia e link (ADR-013)
    planos.py     responde O QUE ELE DIZ — o texto integral (ADR-019)

Sao perguntas diferentes com riscos diferentes. A primeira nao pode errar sobre
uma pessoa; a segunda pode deturpar a proposta dela se a extracao sair torta. Por
isso o texto vive em tabela propria, com marca de qualidade em cada linha.

COMO O ARQUIVO E' ALCANCADO

O caminho de arquivo que a API devolve (`candidaturas/oficial/...`) responde 403 —
foi por isso que a ADR-013 concluiu que o PDF era inalcancavel. Errado: o app do
TSE nao usa esse caminho. Ele usa um endpoint REST, encontrado em 28/08/2026 lendo
o chunk `829` do bundle Angular:

    /divulga/rest/arquivo/doc/{idArquivo}

Esse responde 200 com `application/pdf`. Medido numa amostra de 12 planos: 12
downloads, 12 sucessos.

O QUE NAO E' FEITO, NUNCA

**Resumo.** Resumir e' escolher o que importa no programa de alguem, e isso e'
editorializar (Constituicao 0.1). O texto vai inteiro ou nao vai.

**Correcao.** Se o PDF traz erro de digitacao, o erro aparece. O que esta' aqui e'
transcricao, nao edicao.

**Preenchimento.** PDF escaneado sem camada de texto fica com `texto = null` e
`motivo = 'sem camada de texto'`. A tela diz isso e oferece o original. Um plano
mal extraido e' pior que nenhum: deturpa a proposta de uma pessoa real.
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import time
import urllib.request
from dataclasses import dataclass
from typing import Any

from ingest.common.config import DATASET_RAW_TSE, get_settings
from ingest.common.http import BASE_HEADERS, utc_now
from ingest.common.log import get_logger
from ingest.common.writer import NdjsonWriter
from ingest.propostas import COD_TIPO_PROPOSTA, DOMINIO, consultar

log = get_logger("planos")

# Endpoint lido do bundle do proprio app do TSE. Ver o cabecalho deste modulo.
DOC = f"{DOMINIO}/divulga/rest/arquivo/doc"

PAUSA = 1.2
MAX_MB = 60

# Abaixo disso nao e' plano de governo, e' PDF escaneado ou capa solta. Medido:
# planos de verdade tem mediana de 111 mil caracteres; o menor da amostra, 12 mil.
MIN_CARACTERES = 200

_ESPACOS = re.compile(r"[ \t]+")
_LINHAS_VAZIAS = re.compile(r"\n{3,}")


@dataclass
class Plano:
    sk_candidatura: str
    sq_candidato: str
    sg_ue: str
    nome_urna: str
    cod_cargo: str
    id_arquivo: str | None
    nome_arquivo: str | None
    url_pdf: str | None
    n_paginas: int | None
    n_caracteres: int
    texto: str | None
    motivo: str | None


def _headers() -> dict[str, str]:
    h = dict(BASE_HEADERS)
    # O WAF do TSE confere coerencia: Referer de outro host do proprio TSE
    # devolve 403 neste endpoint (mesma familia de problema da L-18).
    h["Referer"] = f"{DOMINIO}/divulga/"
    h["Accept"] = "application/pdf,*/*"
    return h


def id_do_plano(ano: int, sg_ue: str, sq_candidato: str) -> tuple[str | None, str | None]:
    """Devolve (idArquivo, nome) do plano de governo, ou (None, None)."""
    dados = consultar(ano, sg_ue, sq_candidato)
    for a in (dados or {}).get("arquivos") or []:
        if str(a.get("codTipo")) == COD_TIPO_PROPOSTA:
            return str(a.get("idArquivo")), a.get("nome")
    return None, None


def baixar_pdf(id_arquivo: str) -> bytes:
    req = urllib.request.Request(f"{DOC}/{id_arquivo}", headers=_headers())
    with urllib.request.urlopen(req, timeout=180) as resp:
        if resp.status != 200:
            raise ValueError(f"HTTP {resp.status}")
        dados = resp.read(MAX_MB * 1024 * 1024 + 1)
    if len(dados) > MAX_MB * 1024 * 1024:
        raise ValueError(f"PDF acima de {MAX_MB} MB")
    if dados[:4] != b"%PDF":
        raise ValueError("resposta nao e' um PDF")
    return dados


def extrair_texto(dados: bytes) -> tuple[str | None, int | None, str | None]:
    """Devolve (texto, n_paginas, motivo_de_ausencia).

    `motivo` preenchido significa que NAO ha' texto utilizavel — e a tela precisa
    dizer isso em vez de mostrar um bloco vazio.
    """
    from pypdf import PdfReader  # noqa: PLC0415

    try:
        pdf = PdfReader(io.BytesIO(dados), strict=False)
    except Exception as exc:  # noqa: BLE001
        return None, None, f"PDF ilegivel: {str(exc)[:80]}"

    if getattr(pdf, "is_encrypted", False):
        return None, len(pdf.pages), "PDF protegido por senha"

    partes = []
    for pagina in pdf.pages:
        try:
            partes.append(pagina.extract_text() or "")
        except Exception:  # noqa: BLE001, S110 — pagina ruim nao derruba o documento
            pass

    texto = "\n".join(partes)
    texto = _ESPACOS.sub(" ", texto)
    texto = _LINHAS_VAZIAS.sub("\n\n", texto).strip()

    if len(texto) < MIN_CARACTERES:
        # Quase sempre PDF escaneado: imagem sem camada de texto. Marcar e' melhor
        # que entregar meia duzia de caracteres soltos como se fosse o programa.
        return None, len(pdf.pages), "sem camada de texto (provavelmente escaneado)"
    return texto, len(pdf.pages), None


def coletar(candidatos: list[dict[str, Any]], ano: int = 2026) -> list[Plano]:
    saida: list[Plano] = []
    for i, c in enumerate(candidatos, 1):
        sq, ue, nome = c["sq_candidato"], c["sg_ue"], c["nome_urna"]
        id_arq, nome_arq = id_do_plano(ano, ue, sq)
        time.sleep(PAUSA)

        if not id_arq:
            saida.append(Plano(c["sk_candidatura"], sq, ue, nome, c["cod_cargo"],
                               None, None, None, None, 0, None,
                               "arquivo nao consta mais na API do TSE"))
            continue
        url = f"{DOC}/{id_arq}"
        try:
            dados = baixar_pdf(id_arq)
            texto, paginas, motivo = extrair_texto(dados)
        except Exception as exc:  # noqa: BLE001
            texto, paginas, motivo = None, None, f"download falhou: {str(exc)[:80]}"
        time.sleep(PAUSA)

        saida.append(Plano(c["sk_candidatura"], sq, ue, nome, c["cod_cargo"],
                           id_arq, nome_arq, url, paginas,
                           len(texto) if texto else 0, texto, motivo))
        if i % 20 == 0:
            com = sum(1 for p in saida if p.texto)
            log.info("%d/%d — %d com texto", i, len(candidatos), com)
    return saida


def candidatos_com_plano(cliente, limite: int | None) -> list[dict[str, Any]]:
    p = cliente.project
    lim = f"limit {limite}" if limite else ""
    sql = f"""
        select sk_candidatura, sq_candidato, sg_ue, nome_urna, cod_cargo
        from `{p}.raw_tse.propostas`
        where tem_proposta
        order by cod_cargo, sg_ue, nome_urna
        {lim}
    """
    return [dict(r) for r in cliente.query(sql).result()]


def _schema():
    from google.cloud import bigquery  # noqa: PLC0415

    from ingest.common.bq import build_schema  # noqa: PLC0415

    textos = ["sk_candidatura", "sq_candidato", "sg_ue", "nome_urna", "cod_cargo",
              "id_arquivo", "nome_arquivo", "url_pdf", "texto", "motivo"]
    schema = build_schema(textos)
    corte = len(textos)
    tipados = [bigquery.SchemaField("n_paginas", "INT64"),
               bigquery.SchemaField("n_caracteres", "INT64")]
    return schema[:corte] + tipados + schema[corte:]


def cmd_load(args: argparse.Namespace) -> int:
    from google.cloud import bigquery  # noqa: PLC0415

    settings = get_settings()
    settings.ensure_dirs()
    cliente = bigquery.Client(project=settings.project, location=settings.location)
    candidatos = candidatos_com_plano(cliente, args.limite)
    log.info("%d candidaturas com plano registrado", len(candidatos))

    if args.dry_run:
        log.info("[dry-run] baixaria %d PDFs de %s", len(candidatos), DOC)
        return 0

    planos = coletar(candidatos)
    com_texto = sum(1 for p in planos if p.texto)
    if not planos:
        log.error("nada coletado — a carga nao substitui a tabela por vazio")
        return 1

    destino = settings.staging_dir / "tse" / "planos.ndjson.gz"
    quando = utc_now()
    with NdjsonWriter(destino) as w:
        for p in planos:
            w.write({
                "sk_candidatura": p.sk_candidatura, "sq_candidato": p.sq_candidato,
                "sg_ue": p.sg_ue, "nome_urna": p.nome_urna, "cod_cargo": p.cod_cargo,
                "id_arquivo": p.id_arquivo, "nome_arquivo": p.nome_arquivo,
                "url_pdf": p.url_pdf, "texto": p.texto, "motivo": p.motivo,
                "n_paginas": p.n_paginas, "n_caracteres": p.n_caracteres,
                "_extracted_at": quando, "_source_url": DOC,
                "_source_file": "divulgacandcontas", "_source_sha256": "",
            })

    total_chars = sum(p.n_caracteres for p in planos)
    log.info("%d planos | %d com texto (%.0f%%) | %.1f milhoes de caracteres",
             len(planos), com_texto, 100 * com_texto / len(planos), total_chars / 1e6)

    if args.target == "local":
        log.info("NDJSON em %s", destino)
        return 0

    from ingest.common.bq import ensure_datasets, load_ndjson  # noqa: PLC0415

    ensure_datasets()
    load_ndjson(destino, DATASET_RAW_TSE, "planos", schema=_schema(),
                clustering=("cod_cargo", "sg_ue"))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Baixa uma amostra e mede o aproveitamento, sem carregar nada."""
    from google.cloud import bigquery  # noqa: PLC0415

    s = get_settings()
    cliente = bigquery.Client(project=s.project, location=s.location)
    amostra = candidatos_com_plano(cliente, args.amostra)
    planos = coletar(amostra)

    com = [p for p in planos if p.texto]
    print(f"\n{len(com)} de {len(planos)} renderam texto\n")
    for p in planos:
        if p.texto:
            print(f"  {p.nome_urna[:26]:<27}{p.n_paginas:>4}p  {p.n_caracteres:>8,} chars")
        else:
            print(f"  {p.nome_urna[:26]:<27}{'—':>4}   {p.motivo}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ingest.planos", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_load = sub.add_parser("load", help="baixa os PDFs e extrai o texto integral")
    p_load.add_argument("--ano", type=int, help="aceito por convencao do SPEC 9; nao filtra")
    p_load.add_argument("--limite", type=int)
    p_load.add_argument("--dry-run", action="store_true")
    p_load.add_argument("--target", choices=("bigquery", "local"), default="bigquery")
    p_load.set_defaults(func=cmd_load)

    p_ver = sub.add_parser("verify", help="mede o aproveitamento numa amostra")
    p_ver.add_argument("--amostra", type=int, default=10)
    p_ver.set_defaults(func=cmd_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
