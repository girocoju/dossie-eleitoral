"""Resultado do Tesouro Nacional — S18 / F-04 (fecha a L-22).

    python -m ingest.rtn load   [--dry-run] [--target local]
    python -m ingest.rtn verify

POR QUE ESTE MODULO EXISTE

O projeto media o orcamento federal pela DCA do SICONFI, a mesma fonte dos
estados. Estava errado, e o erro so' apareceu ao conferir um numero contra a
realidade: a serie dava **-48 bi** para 2020, ano em que o resultado primario do
Governo Central foi da ordem de **-743 bi**.

A causa, medida no anexo I-C da Uniao de 2020: a receita da DCA inclui
**operacoes de credito** — R$ 1.647,9 bi, 45% do total. Divida emitida para cobrir
o deficit entra como se fosse arrecadacao, entao receita menos despesa tende a
zero por identidade contabil. Para 2025 a serie chegava a mostrar "superavit de
R$ 635 bi"; o resultado primario real foi **-61,7 bi de deficit**.

Os ESTADOS nao tem o problema (operacoes de credito sao 0,1% a 1,1% da receita
estadual), e por isso `RECEITA_ESTADUAL` e companhia continuam vindo do SICONFI.
A distorcao e' especifica da Uniao, que se financia por divida em escala
incomparavel com a de um estado. Ver L-22 e ADR-017.

O RTN entrega o conceito que o leitor ja' tem na cabeca quando le' "deficit" —
que e' o teste certo para uma tela publica.

A URL MUDA TODO MES

O arquivo se chama `seriehistoricajul26.xlsx` e vira `agosto`, `setembro`... A
URL e' resolvida a cada execucao pela API CKAN do Tesouro Transparente, pelo id
estavel do conjunto. Fixar o nome quebraria a carga em algum dia de setembro, sem
ninguem entender por que.

Conferido em 28/08/2026: 29 anos, 1997 a 2025.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

from ingest.common.cli import executar
from ingest.common.config import DATASET_RAW_TESOURO, get_settings
from ingest.common.http import download as baixar
from ingest.common.http import get_json, utc_now
from ingest.common.indicadores import (
    COLUNAS_NUMERICAS,
    COLUNAS_SAIDA,
    Indicador,
    Observacao,
    por_provedor,
)
from ingest.common.log import get_logger
from ingest.common.planilha import Planilha, abrir
from ingest.common.writer import NdjsonWriter

log = get_logger("rtn")

CKAN = "https://www.tesourotransparente.gov.br/ckan/api/3/action/package_show"
CONJUNTO = "resultado-do-tesouro-nacional"
RECURSO = "Mensal"  # o recurso "Serie Historica - Mensal" traz TAMBEM as abas anuais

FONTE = "Tesouro Nacional — Resultado do Tesouro Nacional (RTN), serie historica"

# A planilha esta' em R$ MILHOES; o resto do projeto guarda R$ absolutos.
ESCALA = 1_000_000

LINHA_ANOS = 5  # linha do cabecalho com os exercicios; conferida em 28/08/2026

_ESPACOS = re.compile(r"\s+")


def _rotulo(texto: Any) -> str:
    bruto = unicodedata.normalize("NFD", str(texto or "")).encode("ascii", "ignore").decode()
    return _ESPACOS.sub(" ", bruto).strip().upper()


def url_da_planilha() -> str:
    """Resolve a URL atual pelo CKAN. O nome do arquivo muda a cada mes."""
    dados = get_json(f"{CKAN}?id={CONJUNTO}", timeout=90)["result"]
    for r in dados.get("resources", []):
        if r.get("format") == "XLSX" and RECURSO in (r.get("name") or ""):
            return r["url"]
    raise ValueError(
        f"nenhum recurso XLSX com {RECURSO!r} no conjunto {CONJUNTO}. "
        "O Tesouro reorganizou a publicacao — confira em "
        "https://www.tesourotransparente.gov.br/ckan/dataset/" + CONJUNTO
    )


def _anos_por_coluna(pl: Planilha) -> dict[str, int]:
    anos = {}
    for coluna, texto in (pl.linhas.get(LINHA_ANOS) or {}).items():
        t = texto.strip()
        if t.isdigit() and 1990 <= int(t) <= 2100:
            anos[coluna] = int(t)
    if not anos:
        raise ValueError(
            f"nenhum ano na linha {LINHA_ANOS} da aba. O Tesouro mudou o layout: "
            "confira e ajuste LINHA_ANOS."
        )
    return anos


def extrair(caminho: Path, ind: Indicador, extraido_em: str, url: str) -> list[Observacao]:
    aba = str(ind.parametros["aba"])
    rubrica = _rotulo(ind.parametros["rubrica"])

    abas = abrir(caminho, normalizar=lambda n: n.strip())
    if aba not in abas:
        raise ValueError(f"aba {aba!r} nao existe. Abas: {sorted(abas)}")
    pl = abas[aba]
    anos = _anos_por_coluna(pl)

    # A rubrica e' casada por PREFIXO do rotulo da coluna A. O Tesouro numera as
    # linhas ("3. RECEITA LIQUIDA (1-2)") e muda a parte final entre edicoes —
    # em 2023 a nota de rodape passou de 1/ para 2/ em varias delas. O prefixo
    # numerado e' a parte estavel.
    candidatas = [
        n for n, celulas in pl.linhas.items()
        if _rotulo(celulas.get("A", "")).startswith(rubrica)
    ]
    if not candidatas:
        raise ValueError(
            f"rubrica {ind.parametros['rubrica']!r} nao encontrada na aba {aba!r}. "
            "O Tesouro renomeou a linha — confira a planilha antes de ajustar."
        )
    if len(candidatas) > 1:
        # Ambiguidade nao vira escolha silenciosa: duas linhas parecidas somariam
        # ou sobrescreveriam valores sem ninguem perceber.
        rotulos = [pl.linhas[n].get("A", "") for n in candidatas]
        raise ValueError(
            f"rubrica {ind.parametros['rubrica']!r} casa com {len(candidatas)} linhas "
            f"da aba {aba!r}: {rotulos}. Torne o prefixo mais especifico."
        )

    linha = pl.linhas[candidatas[0]]
    obs: list[Observacao] = []
    for coluna, ano in sorted(anos.items(), key=lambda x: x[1]):
        bruto = (linha.get(coluna) or "").strip()
        if not bruto:
            continue
        try:
            valor = float(bruto)
        except ValueError:
            continue
        obs.append(
            Observacao(
                cod_indicador=ind.cod_indicador,
                sg_uf="BR",
                ano=ano,
                valor=valor * ESCALA,
                unidade=ind.unidade,
                fonte=FONTE,
                extracted_at=extraido_em,
                source_url=url,
            )
        )
    return obs


def coletar(*, force: bool = False) -> list[Observacao]:
    settings = get_settings()
    destino = settings.download_dir / "tesouro"
    destino.mkdir(parents=True, exist_ok=True)

    url = url_da_planilha()
    log.info("planilha atual: %s", url.rsplit("/", 1)[-1])
    caminho = Path(baixar(url, destino / "rtn_serie_historica.xlsx", force=force).path)

    extraido_em = utc_now()
    obs: list[Observacao] = []
    for ind in por_provedor("rtn"):
        linhas = extrair(caminho, ind, extraido_em, url)
        anos = sorted(o.ano for o in linhas)
        log.info(
            "%s: %d anos (%d..%d)", ind.cod_indicador, len(linhas), anos[0], anos[-1]
        )
        obs.extend(linhas)
    return obs


def _schema():
    from google.cloud import bigquery

    from ingest.common.bq import build_schema

    schema = build_schema(list(COLUNAS_SAIDA))
    numericas = [bigquery.SchemaField(nome, tipo) for nome, tipo in COLUNAS_NUMERICAS]
    corte = len(COLUNAS_SAIDA)
    return schema[:corte] + numericas + schema[corte:]


def cmd_load(args: argparse.Namespace) -> int:
    settings = get_settings()
    settings.ensure_dirs()

    if args.dry_run:
        log.info("[dry-run] resolveria a URL no CKAN e baixaria a serie historica")
        return 0

    obs = coletar(force=args.force)
    if not obs:
        log.error("nenhuma observacao coletada — a carga nao substitui a tabela por vazio")
        return 1

    destino = settings.staging_dir / "indicadores" / "rtn.ndjson.gz"
    with NdjsonWriter(destino) as writer:
        for o in obs:
            writer.write(o.to_row())

    anos = sorted({o.ano for o in obs})
    log.info("%d observacoes | %d..%d", len(obs), anos[0], anos[-1])

    if args.target == "local":
        log.info("NDJSON em %s", destino)
        return 0

    from ingest.common.bq import ensure_datasets, load_ndjson

    ensure_datasets()
    load_ndjson(
        destino,
        DATASET_RAW_TESOURO,
        "rtn",
        schema=_schema(),
        particionar_por="ano",
        clustering=("cod_indicador", "sg_uf"),
    )
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Mostra a serie e a diferenca para o que a DCA dizia."""
    obs = coletar()
    por_ind: dict[str, dict[int, float]] = {}
    for o in obs:
        por_ind.setdefault(o.cod_indicador, {})[o.ano] = o.valor

    anos = sorted({o.ano for o in obs})
    recentes = [a for a in anos if a >= args.desde]

    print(f"\nResultado do Tesouro Nacional — {len(anos)} anos ({anos[0]}..{anos[-1]})")
    print(f"\n{'ano':<6}" + "".join(f"{c[:22]:>24}" for c in sorted(por_ind)))
    for ano in recentes:
        linha = f"{ano:<6}"
        for cod in sorted(por_ind):
            v = por_ind[cod].get(ano)
            linha += f"{(v / 1e9 if v is not None else 0):>21,.1f} bi"
        print(linha)
    print("\nValores em R$ bilhoes correntes. Negativo = deficit.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ingest.rtn", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_load = sub.add_parser("load", help="baixa a serie historica do RTN e carrega")
    p_load.add_argument("--ano", type=int, help="aceito por convencao do SPEC 9; nao filtra")
    p_load.add_argument("--force", action="store_true", help="rebaixa mesmo com cache valido")
    p_load.add_argument("--dry-run", action="store_true")
    p_load.add_argument("--target", choices=("bigquery", "local"), default="bigquery")
    p_load.set_defaults(func=cmd_load)

    p_ver = sub.add_parser("verify", help="mostra a serie do resultado primario")
    p_ver.add_argument("--desde", type=int, default=2015)
    p_ver.set_defaults(func=cmd_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return executar(args.func, args)


if __name__ == "__main__":
    sys.exit(main())
