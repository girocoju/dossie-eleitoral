"""Votos e presenca dos deputados — S19 / F-20 (ADR-025).

    python -m ingest.plenario load   [--ano-inicio 2023] [--ano-fim 2026] [--dry-run]
    python -m ingest.plenario verify [--ano 2025]

Duas coisas que a Camara publica em lote e que faltavam ao dossie:

    votacoesVotos-{ano}.csv            como cada deputado votou, voto a voto
    eventosPresencaDeputados-{ano}.csv uma linha por presenca em evento

AGREGADO NA INGESTAO, E NAO NO BIGQUERY

`votacoesVotos` de um ano passa de 50 MB e tem centenas de milhares de linhas;
somando 2003-2026 seriam dezenas de milhoes. O dossie nao usa o voto individual:
usa quantas vezes a pessoa votou e como esses votos se distribuem. Agregar aqui
mantem a tabela na casa das dezenas de milhares e o custo perto de zero
(Constituicao 0.5) — a mesma decisao ja' tomada para a votacao do TSE.

O que se perde: nao da' para perguntar "como fulano votou na PEC tal". Se um dia
essa pergunta entrar no escopo, a fonte continua la'.

VOLUME DE PRESENCA, NAO TAXA

`eventosPresencaDeputados` diz em que eventos o deputado esteve. NAO diz quantos
eventos ele DEVIA ter comparecido, e sem denominador nao existe percentual.

Derivar um seria inventar: falta se confunde com comissao paralela, missao
oficial e licenca medica, e um "62% de presenca" errado e' uma acusacao publicada
sobre uma pessoa real. A frequencia oficial existe no portal da Camara, fora do
dado aberto.

Entao aqui vai o VOLUME — quantos eventos, quantos deles em plenario. E' fato
verificavel. Comparar dois deputados por esse numero exige saber que mandatos tem
duracoes diferentes, e a tela diz isso.
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter, defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ingest.common.cli import executar
from ingest.common.config import DATASET_RAW_LEGISLATIVO, get_settings
from ingest.common.http import DownloadError, download, utc_now
from ingest.common.log import get_logger
from ingest.common.writer import NdjsonWriter

log = get_logger("plenario")

BASE = "https://dadosabertos.camara.leg.br/arquivos"
ANO_INICIO = 2023
ANO_FIM = 2026

# `voto` chega com rotulo livre da Camara. Estes sao os que aparecem; qualquer
# outro cai em `outro`, sem ser descartado — o total tem que fechar.
VOTOS = {
    "SIM": "sim",
    "NAO": "nao",
    "NÃO": "nao",
    "ABSTENCAO": "abstencao",
    "ABSTENÇÃO": "abstencao",
    "OBSTRUCAO": "obstrucao",
    "OBSTRUÇÃO": "obstrucao",
    "ARTIGO 17": "artigo_17",
}

# `PLEN` e' a sigla do Plenario em `eventosOrgaos`. O resto e' comissao, e a
# distincao importa: sessao de plenario e reuniao de comissao sao trabalhos
# diferentes, e somar os dois num numero so' esconderia isso.
#
# A sigla, e nao o codigo numerico: o `id` do orgao muda entre legislaturas
# quando uma comissao e' recriada; a sigla do Plenario nao muda desde sempre.
SIGLA_PLENARIO = "PLEN"


def _url(nome: str, ano: int) -> str:
    return f"{BASE}/{nome}/csv/{nome}-{ano}.csv"


def _ler_csv(caminho: Path | str) -> Iterator[dict[str, str]]:
    """Streaming: `votacoesVotos` de um ano passa de 50 MB."""
    with Path(caminho).open("r", encoding="utf-8-sig", newline="") as fh:
        yield from csv.DictReader(fh, delimiter=";")


def coletar_votos(ano: int, destino_dir: Path, *, force: bool = False) -> list[dict[str, Any]]:
    """Agrega por (deputado, ano): quantas votacoes e a distribuicao dos votos."""
    csv_path = download(_url("votacoesVotos", ano),
                        destino_dir / f"votacoesVotos-{ano}.csv", force=force).path

    por_dep: dict[str, Counter[str]] = defaultdict(Counter)
    votacoes: dict[str, set[str]] = defaultdict(set)
    meta: dict[str, dict[str, str]] = {}
    lidas = 0

    for linha in _ler_csv(csv_path):
        dep = (linha.get("deputado_id") or "").strip()
        if not dep:
            continue
        lidas += 1
        bruto = (linha.get("voto") or "").strip().upper()
        por_dep[dep][VOTOS.get(bruto, "outro")] += 1
        votacoes[dep].add((linha.get("idVotacao") or "").strip())
        meta.setdefault(dep, {
            "nome_deputado": (linha.get("deputado_nome") or "").strip(),
            "sigla_partido": (linha.get("deputado_siglaPartido") or "").strip(),
            "sg_uf": (linha.get("deputado_siglaUf") or "").strip(),
            "id_legislatura": (linha.get("deputado_idLegislatura") or "").strip(),
        })

    log.info("%d: %d votos individuais, %d deputados", ano, lidas, len(por_dep))
    return [
        {
            "ano": ano,
            "id_deputado": dep,
            **meta[dep],
            "qt_votacoes": len(votacoes[dep]),
            "qt_sim": c["sim"],
            "qt_nao": c["nao"],
            "qt_abstencao": c["abstencao"],
            "qt_obstrucao": c["obstrucao"],
            "qt_artigo_17": c["artigo_17"],
            "qt_outro": c["outro"],
        }
        for dep, c in sorted(por_dep.items())
    ]


def coletar_presenca(ano: int, destino_dir: Path, *, force: bool = False) -> list[dict[str, Any]]:
    """Agrega por (deputado, ano): em quantos eventos esteve."""
    presenca_csv = download(_url("eventosPresencaDeputados", ano),
                            destino_dir / f"eventosPresencaDeputados-{ano}.csv",
                            force=force).path
    # De qual orgao e' cada evento. `eventos-{ano}.csv` NAO tem essa coluna — a
    # relacao vive em arquivo proprio, e um evento pode pertencer a mais de um
    # orgao (sessao conjunta), por isso o valor e' um CONJUNTO.
    orgaos_csv = download(_url("eventosOrgaos", ano),
                          destino_dir / f"eventosOrgaos-{ano}.csv", force=force).path

    plenario: set[str] = set()
    eventos_vistos: set[str] = set()
    for linha in _ler_csv(orgaos_csv):
        eid = (linha.get("idEvento") or "").strip()
        if not eid:
            continue
        eventos_vistos.add(eid)
        if (linha.get("siglaOrgao") or "").strip().upper() == SIGLA_PLENARIO:
            plenario.add(eid)

    eventos_por_dep: dict[str, set[str]] = defaultdict(set)
    plenario_por_dep: dict[str, set[str]] = defaultdict(set)
    lidas = 0
    for linha in _ler_csv(presenca_csv):
        dep = (linha.get("idDeputado") or "").strip()
        eid = (linha.get("idEvento") or "").strip()
        if not dep or not eid:
            continue
        lidas += 1
        eventos_por_dep[dep].add(eid)
        if eid in plenario:
            plenario_por_dep[dep].add(eid)

    log.info("%d: %d presencas, %d deputados, %d eventos (%d de plenario)",
             ano, lidas, len(eventos_por_dep), len(eventos_vistos), len(plenario))
    return [
        {
            "ano": ano,
            "id_deputado": dep,
            "qt_eventos": len(eventos),
            "qt_eventos_plenario": len(plenario_por_dep.get(dep, ())),
        }
        for dep, eventos in sorted(eventos_por_dep.items())
    ]


def _schema(textos: list[str], inteiros: list[str]):
    from google.cloud import bigquery  # noqa: PLC0415

    from ingest.common.bq import build_schema  # noqa: PLC0415

    schema = build_schema(textos)
    corte = len(textos)
    tipados = [bigquery.SchemaField(n, "INT64") for n in inteiros]
    return schema[:corte] + tipados + schema[corte:]


TABELAS = {
    "votos": {
        "coletar": coletar_votos,
        "tabela": "votos_deputado",
        "textos": ["id_deputado", "nome_deputado", "sigla_partido", "sg_uf", "id_legislatura"],
        "inteiros": ["ano", "qt_votacoes", "qt_sim", "qt_nao", "qt_abstencao",
                     "qt_obstrucao", "qt_artigo_17", "qt_outro"],
        "arquivo": "votacoesVotos",
    },
    "presenca": {
        "coletar": coletar_presenca,
        "tabela": "presenca_deputado",
        "textos": ["id_deputado"],
        "inteiros": ["ano", "qt_eventos", "qt_eventos_plenario"],
        "arquivo": "eventosPresencaDeputados",
    },
}


def cmd_load(args: argparse.Namespace) -> int:
    settings = get_settings()
    settings.ensure_dirs()
    anos = [args.ano] if args.ano else list(range(args.ano_inicio, args.ano_fim + 1))
    quais = [args.o_que] if args.o_que else list(TABELAS)

    if args.dry_run:
        for q in quais:
            for ano in anos:
                log.info("[dry-run] baixaria %s", _url(TABELAS[q]["arquivo"], ano))
        return 0

    bruto = settings.download_dir / "camara"
    bruto.mkdir(parents=True, exist_ok=True)
    quando = utc_now()
    houve_carga = False
    rede: DownloadError | None = None

    for q in quais:
        cfg = TABELAS[q]
        for ano in anos:
            try:
                linhas = cfg["coletar"](ano, bruto, force=args.force)
            except DownloadError as exc:
                # Sobe intacta para `executar` classificar pela CAUSA (ADR-022).
                log.warning("rede: %s", str(exc)[:100])
                rede = exc
                continue
            except Exception as exc:  # noqa: BLE001
                # O arquivo do ano corrente so' aparece depois da primeira
                # publicacao; anos antigos podem faltar sem aviso.
                log.warning("%s %d indisponivel: %s", q, ano, str(exc)[:110])
                continue
            if not linhas:
                log.warning("%s %d veio vazio — particao preservada", q, ano)
                continue

            destino = settings.staging_dir / "legislativo" / f"{q}-{ano}.ndjson.gz"
            with NdjsonWriter(destino) as w:
                for linha in linhas:
                    w.write({**linha, "_extracted_at": quando, "_source_url": BASE,
                             "_source_file": f"{cfg['arquivo']}-{ano}.csv",
                             "_source_sha256": ""})

            if args.target != "local":
                from ingest.common.bq import ensure_datasets, load_intervalo  # noqa: PLC0415

                ensure_datasets()
                load_intervalo(destino, DATASET_RAW_LEGISLATIVO, cfg["tabela"],
                               schema=_schema(cfg["textos"], cfg["inteiros"]),
                               coluna="ano", valor=ano,
                               clustering=("id_deputado",))
            houve_carga = True

    if not houve_carga:
        if rede is not None:
            # Ver ADR-022: a causa sobe para ser classificada.
            raise rede
        log.error("nada carregado — a carga nao substitui as tabelas por vazio")
        return 1
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Mostra o que um ano traz, sem carregar."""
    settings = get_settings()
    settings.ensure_dirs()
    bruto = settings.download_dir / "camara"
    bruto.mkdir(parents=True, exist_ok=True)

    votos = coletar_votos(args.ano, bruto)
    presenca = coletar_presenca(args.ano, bruto)
    por_dep = {p["id_deputado"]: p for p in presenca}

    print(f"\n{args.ano}: {len(votos)} deputados votaram, {len(presenca)} estiveram em evento\n")
    top = sorted(votos, key=lambda v: -v["qt_votacoes"])[:5]
    print(f"{'deputado':<26}{'votacoes':>9}{'sim':>7}{'nao':>7}{'obstr':>7}{'eventos':>9}{'plen':>7}")
    for v in top:
        p = por_dep.get(v["id_deputado"], {})
        print(f"{v['nome_deputado'][:24]:<26}{v['qt_votacoes']:>9}{v['qt_sim']:>7}"
              f"{v['qt_nao']:>7}{v['qt_obstrucao']:>7}"
              f"{p.get('qt_eventos', 0):>9}{p.get('qt_eventos_plenario', 0):>7}")
    print("\nO volume nao vira taxa: a fonte nao diz a quantos eventos cada um "
          "DEVIA comparecer, e sem denominador nao ha' percentual honesto.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ingest.plenario", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_load = sub.add_parser("load", help="votos e presenca, por ano")
    p_load.add_argument("--o-que", choices=tuple(TABELAS))
    p_load.add_argument("--ano", type=int)
    p_load.add_argument("--ano-inicio", type=int, default=ANO_INICIO)
    p_load.add_argument("--ano-fim", type=int, default=ANO_FIM)
    p_load.add_argument("--force", action="store_true")
    p_load.add_argument("--dry-run", action="store_true")
    p_load.add_argument("--target", choices=("bigquery", "local"), default="bigquery")
    p_load.set_defaults(func=cmd_load)

    p_ver = sub.add_parser("verify", help="mostra o que um ano traz")
    p_ver.add_argument("--ano", type=int, default=2025)
    p_ver.set_defaults(func=cmd_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return executar(args.func, args)


if __name__ == "__main__":
    sys.exit(main())
