"""Financiamento de campanha — S18 / F-11 (ADR-020).

    python -m ingest.financiamento load   [--ano 2026] [--dry-run] [--target local]
    python -m ingest.financiamento verify [--ano 2026]

Receitas e despesas declaradas pelas candidaturas ao TSE. E' o dado que mais
aproxima uma candidatura de quem a sustenta.

O CPF DO DOADOR NAO E' PERSISTIDO

O arquivo do TSE traz `NR_CPF_CNPJ_DOADOR` em TEXTO PURO. Conferido no primeiro
registro de `receitas_candidatos_2026_AM.csv`:

    NM_DOADOR            L***** C***** A***** N***
    NR_CPF_CNPJ_DOADOR   071********            <- CPF legivel

O doador e' publico por lei — e' essa publicidade que permite fiscalizar quem
financia quem. **O CPF dele nao precisa ser.** O nome cumpre a prestacao de
contas; o numero so' acrescenta risco.

Entao, aqui:

    pessoa fisica (11 digitos)   -> `cpf_hash`, o mesmo HMAC do candidato.
                                    Agrupar doacoes da mesma pessoa continua
                                    possivel; expor o numero, nao.
    pessoa juridica (14 digitos) -> fica EM CLARO. CNPJ identifica empresa,
                                    partido ou comite — nao e' dado pessoal, e e'
                                    o que permite rastrear doador institucional.

A Constituicao 0.7 nao abre excecao por origem do dado. Vale para candidato e vale
para doador — com mais razao para o doador, que nao se candidatou a nada.

DECLAROU ZERO NAO E' O MESMO QUE NAO ENTREGOU

A pagina do TSE mostra "Despesas R$ 0,00" para a maior campanha presidencial do
pais. Nao e' austeridade: e' prazo de prestacao ainda aberto. Quem nao aparece
neste arquivo NAO declarou zero — nao declarou nada. A carga preserva a diferenca
deixando a candidatura ausente da tabela, em vez de inventar uma linha zerada.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

from ingest.common.config import DATASET_RAW_TSE, get_settings
from ingest.common.http import download, utc_now
from ingest.common.log import get_logger
from ingest.common.textnorm import cpf_hash, only_digits
from ingest.common.writer import NdjsonWriter

log = get_logger("financiamento")

BASE = "https://cdn.tse.jus.br/estatistica/sead/odsele/prestacao_contas"
ARQUIVO = "prestacao_de_contas_eleitorais_candidatos_{ano}.zip"

# O TSE usa `#NULO`, `#NE` e negativos como sentinela de ausencia. Virar string
# vazia e' o certo: guardar "#NULO" como se fosse valor polui toda consulta.
SENTINELAS = {"#NULO", "#NE", "#NULO#", "-1", "-3", "-4", "N/A", ""}

_ASPAS = re.compile(r'^"|"$')


def _limpo(valor: Any) -> str | None:
    v = _ASPAS.sub("", str(valor or "")).strip()
    return None if v.upper() in SENTINELAS else v


def _numero(valor: Any) -> float | None:
    v = _limpo(valor)
    if v is None:
        return None
    try:
        return float(v.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _documento(bruto: Any) -> tuple[str | None, str | None, str]:
    """Devolve (cnpj_em_claro, cpf_hash, tipo_de_pessoa).

    A regra inteira da ADR-020 mora nestas dez linhas. CNPJ identifica empresa e
    fica legivel; CPF identifica pessoa e vira hash.
    """
    d = only_digits(_limpo(bruto)) or ""
    if len(d) == 14:
        return d, None, "juridica"
    if len(d) == 11:
        return None, cpf_hash(d), "fisica"
    return None, None, "nao informado"


def _acessor(indice: dict[str, int], linha: list[str]):
    def campo(chave: str) -> str | None:
        return _limpo(linha[indice[chave]]) if chave in indice else None
    return campo


def _abrir(caminho: Path, nome: str):
    with zipfile.ZipFile(caminho).open(nome) as bruto:
        texto = io.TextIOWrapper(bruto, encoding="latin-1", newline="")
        leitor = csv.reader(texto, delimiter=";")
        cabecalho = [_ASPAS.sub("", c).strip() for c in next(leitor)]
        indice = {c: i for i, c in enumerate(cabecalho)}
        for linha in leitor:
            if len(linha) >= len(cabecalho):
                # devolve um acessor ja' ligado a ESTA linha; fechar sobre a
                # variavel do laco daria valores trocados entre iteracoes
                yield _acessor(indice, linha)


def ler_receitas(caminho: Path, ano: int) -> list[dict[str, Any]]:
    z = zipfile.ZipFile(caminho)
    arquivos = [n for n in z.namelist() if n.startswith(f"receitas_candidatos_{ano}_")]
    log.info("%d arquivos de receita", len(arquivos))
    saida: list[dict[str, Any]] = []
    for nome in arquivos:
        for campo in _abrir(caminho, nome):
            cnpj, doador_hash, tipo = _documento(campo("NR_CPF_CNPJ_DOADOR"))
            origem = campo("DS_ORIGEM_RECEITA")
            sq = campo("SQ_CANDIDATO")
            sq_doador = campo("SQ_CANDIDATO_DOADOR")
            saida.append({
                "ano_eleicao": ano,
                "sq_candidato": sq,
                "sg_uf": campo("SG_UF"),
                "sg_ue": campo("SG_UE"),
                "cod_cargo": campo("CD_CARGO"),
                "nome_candidato": campo("NM_CANDIDATO"),
                "sigla_partido": campo("SG_PARTIDO"),
                "sq_receita": campo("SQ_RECEITA"),
                "data_receita": (campo("DT_RECEITA") or "")[:10] or None,
                "valor": _numero(campo("VR_RECEITA")),
                "fonte": campo("DS_FONTE_RECEITA"),
                "origem": origem,
                "natureza": campo("DS_NATUREZA_RECEITA"),
                "especie": campo("DS_ESPECIE_RECEITA"),
                "descricao": campo("DS_RECEITA"),
                # ── doador ────────────────────────────────────────────────
                "nome_doador": campo("NM_DOADOR_RFB") or campo("NM_DOADOR"),
                "doador_cnpj": cnpj,
                "doador_cpf_hash": doador_hash,
                "doador_tipo": tipo,
                "doador_uf": campo("SG_UF_DOADOR"),
                "doador_municipio": campo("NM_MUNICIPIO_DOADOR"),
                "doador_cnae": campo("DS_CNAE_DOADOR"),
                # Doador que TAMBEM e' candidato: e' o que transforma a lista em
                # rede de financiamento.
                "doador_sq_candidato": sq_doador,
                # Autofinanciamento NAO e' rede: em 6.501 dos 6.880 lancamentos
                # com doador-candidato, o doador e' o proprio candidato. Chamar
                # tudo de "candidato financia candidato" seria erro grosseiro.
                "e_autofinanciamento": bool(sq_doador and sq_doador == sq),
                "doador_cargo": campo("DS_CARGO_CANDIDATO_DOADOR"),
                "doador_partido": campo("SG_PARTIDO_DOADOR"),
            })
    return saida


def ler_despesas(caminho: Path, ano: int) -> list[dict[str, Any]]:
    """Despesas CONTRATADAS. Pagas sao subconjunto e mudariam o significado."""
    z = zipfile.ZipFile(caminho)
    arquivos = [n for n in z.namelist()
                if n.startswith(f"despesas_contratadas_candidatos_{ano}_")]
    log.info("%d arquivos de despesa contratada", len(arquivos))
    saida: list[dict[str, Any]] = []
    for nome in arquivos:
        for campo in _abrir(caminho, nome):
            cnpj, forn_hash, tipo = _documento(campo("NR_CPF_CNPJ_FORNECEDOR"))
            saida.append({
                "ano_eleicao": ano,
                "sq_candidato": campo("SQ_CANDIDATO"),
                "sg_uf": campo("SG_UF"),
                "cod_cargo": campo("CD_CARGO"),
                "sq_despesa": campo("SQ_DESPESA"),
                "data_despesa": (campo("DT_DESPESA") or "")[:10] or None,
                "valor": _numero(campo("VR_DESPESA_CONTRATADA")),
                "tipo_despesa": campo("DS_TIPO_DESPESA"),
                "descricao": campo("DS_DESPESA"),
                "fornecedor_nome": campo("NM_FORNECEDOR_RFB") or campo("NM_FORNECEDOR"),
                "fornecedor_cnpj": cnpj,
                "fornecedor_cpf_hash": forn_hash,
                "fornecedor_tipo": tipo,
                "fornecedor_uf": campo("SG_UF_FORNECEDOR"),
                "fornecedor_municipio": campo("NM_MUNICIPIO_FORNECEDOR"),
            })
    return saida


def _schema(colunas: list[str], numericas: list[str], inteiras: list[str],
            booleanas: list[str] | None = None):
    """`build_schema` tipa tudo como STRING; aqui as colunas que nao sao texto.

    `e_autofinanciamento` PRECISA chegar como BOOL: como STRING o dbt recebe
    "true"/"false" e um `IF()` sobre isso falha alto — o que e' melhor que a
    alternativa, um `if('false')` verdadeiro que somaria autofinanciamento errado
    em silencio.
    """
    from google.cloud import bigquery  # noqa: PLC0415

    from ingest.common.bq import build_schema  # noqa: PLC0415

    booleanas = booleanas or []
    fora = set(numericas) | set(inteiras) | set(booleanas)
    textos = [c for c in colunas if c not in fora]
    schema = build_schema(textos)
    corte = len(textos)
    tipados = ([bigquery.SchemaField(n, "FLOAT64") for n in numericas]
               + [bigquery.SchemaField(n, "INT64") for n in inteiras]
               + [bigquery.SchemaField(n, "BOOL") for n in booleanas])
    return schema[:corte] + tipados + schema[corte:]


def _gravar(settings, nome: str, linhas: list[dict[str, Any]], quando: str) -> Path:
    destino = settings.staging_dir / "tse" / f"{nome}.ndjson.gz"
    with NdjsonWriter(destino) as w:
        for linha in linhas:
            w.write({**linha, "_extracted_at": quando, "_source_url": BASE,
                     "_source_file": nome, "_source_sha256": ""})
    return destino


def cmd_load(args: argparse.Namespace) -> int:
    settings = get_settings()
    settings.ensure_dirs()
    ano = args.ano
    url = f"{BASE}/{ARQUIVO.format(ano=ano)}"

    if args.dry_run:
        log.info("[dry-run] baixaria %s", url)
        return 0

    caminho = Path(download(url, settings.download_dir / "tse" /
                            f"prest_contas_{ano}.zip").path)
    receitas = ler_receitas(caminho, ano)
    despesas = ler_despesas(caminho, ano)
    if not receitas:
        log.error("nenhuma receita lida — a carga nao substitui a tabela por vazio")
        return 1

    quando = utc_now()
    total_r = sum(r["valor"] or 0 for r in receitas)
    total_d = sum(d["valor"] or 0 for d in despesas)
    tipos = Counter(r["doador_tipo"] for r in receitas)
    log.info("receitas: %d lancamentos, %d candidaturas, R$ %.1f mi",
             len(receitas), len({r["sq_candidato"] for r in receitas}), total_r / 1e6)
    log.info("  doador: %s", dict(tipos))
    log.info("despesas: %d lancamentos, R$ %.1f mi", len(despesas), total_d / 1e6)

    # Trava da ADR-020: nenhum CPF pode sair daqui em claro.
    for lista, campo_hash in ((receitas, "doador_cpf_hash"), (despesas, "fornecedor_cpf_hash")):
        for linha in lista:
            for chave, valor in linha.items():
                if chave == campo_hash or not isinstance(valor, str):
                    continue
                if len(only_digits(valor) or "") == 11 and chave.endswith(("cnpj", "documento")):
                    log.error("CPF em claro em %s — carga abortada", chave)
                    return 1

    d_rec = _gravar(settings, "financiamento_receitas", receitas, quando)
    d_des = _gravar(settings, "financiamento_despesas", despesas, quando)

    if args.target == "local":
        log.info("NDJSON em %s e %s", d_rec, d_des)
        return 0

    from ingest.common.bq import ensure_datasets, load_ndjson  # noqa: PLC0415

    ensure_datasets()
    load_ndjson(d_rec, DATASET_RAW_TSE, "financiamento_receitas",
                schema=_schema(list(receitas[0]), ["valor"], ["ano_eleicao"],
                               ["e_autofinanciamento"]),
                particionar_por="ano_eleicao", clustering=("sq_candidato", "sg_uf"))
    if despesas:
        load_ndjson(d_des, DATASET_RAW_TSE, "financiamento_despesas",
                    schema=_schema(list(despesas[0]), ["valor"], ["ano_eleicao"]),
                    particionar_por="ano_eleicao", clustering=("sq_candidato", "sg_uf"))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    settings = get_settings()
    settings.ensure_dirs()
    caminho = Path(download(f"{BASE}/{ARQUIVO.format(ano=args.ano)}",
                            settings.download_dir / "tse" /
                            f"prest_contas_{args.ano}.zip").path)
    receitas = ler_receitas(caminho, args.ano)

    def mil(n: int) -> str:
        return f"{n:,}".replace(",", ".")

    total = sum(r["valor"] or 0 for r in receitas)
    print(f"\n{mil(len(receitas))} lancamentos de receita")
    print(f"{mil(len({r['sq_candidato'] for r in receitas}))} candidaturas")
    print(f"R$ {total / 1e6:.1f} milhoes declarados\n")

    print("por origem:")
    for origem, n in Counter(r["origem"] for r in receitas).most_common(8):
        soma = sum(r["valor"] or 0 for r in receitas if r["origem"] == origem)
        print(f"  {mil(n):>7}  R$ {soma / 1e6:>8.1f} mi  {origem}")

    print("\nprivacidade do doador:")
    for tipo, n in Counter(r["doador_tipo"] for r in receitas).most_common():
        print(f"  {tipo:<14}{mil(n):>7}")
    em_claro = sum(1 for r in receitas if r["doador_cpf_hash"]
                   and len(only_digits(r["doador_cpf_hash"]) or "") == 11)
    print(f"  CPF em claro na saida: {em_claro} (tem que ser zero)")

    # Autofinanciamento NAO e' rede. Somar os dois diria "candidato financia
    # candidato" para 6.880 lancamentos quando 6.501 sao o proprio candidato.
    proprio = [r for r in receitas if r["e_autofinanciamento"]]
    entre = [r for r in receitas
             if r["doador_sq_candidato"] and not r["e_autofinanciamento"]]
    for rotulo, grupo in (("autofinanciamento", proprio),
                          ("entre candidaturas distintas", entre)):
        soma = sum(r["valor"] or 0 for r in grupo) / 1e6
        print(f"\n{rotulo}: {mil(len(grupo))} lancamentos, R$ {soma:.1f} mi")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ingest.financiamento", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_load = sub.add_parser("load", help="baixa e carrega receitas e despesas")
    p_load.add_argument("--ano", type=int, default=2026)
    p_load.add_argument("--dry-run", action="store_true")
    p_load.add_argument("--target", choices=("bigquery", "local"), default="bigquery")
    p_load.set_defaults(func=cmd_load)

    p_ver = sub.add_parser("verify", help="mede o pacote sem carregar")
    p_ver.add_argument("--ano", type=int, default=2026)
    p_ver.set_defaults(func=cmd_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
