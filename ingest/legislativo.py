"""Ponte de identidade entre o TSE e as Casas legislativas — F-15 (S15, S16).

    python -m ingest.legislativo load   [--casa camara|senado] [--dry-run] [--target local]
    python -m ingest.legislativo verify

Liga cada parlamentar em exercicio a' pessoa que o projeto ja' conhece do TSE.
E' a fundacao de qualquer metrica de atividade parlamentar: sem ela, "o deputado
X votou assim" nao pode ser exibido na ficha do candidato X.

As duas Casas exigem estrategias diferentes, e a diferenca importa (ADR-014):

* **Camara** publica CPF em `/deputados/{id}`. Casa por `cpf_hash`, a mesma chave
  que liga eleicoes entre si. Conferido: 20 de 20 na amostra.
* **Senado** NAO publica CPF. Casa por nome completo normalizado + data de
  nascimento. Medido depois da carga em `dim_parlamentar`: **80 de 81** casam, e
  o 81o e' um homonimo com a mesma data de nascimento — fica sem `id_pessoa`, de
  proposito. Atribuir o mandato de um a outro seria pior do que nao mostrar nada.

  ATENCAO a um erro que ja' aconteceu aqui: a comparacao SO' POR NOME devolvia
  81 de 81 e parecia perfeita. A chave real inclui a data de nascimento e, mais
  importante, precisa ser resolvida contra o TSE — la' o senador TEM CPF, entao o
  `id_pessoa` dele e' o cpf_hash, nao o hash de nome. Duas chaves corretas que
  nunca se encontram. Por isso este modulo entrega as duas chaves e quem resolve
  e' `dim_parlamentar`.

A diferenca viaja com o dado, em `metodo_casamento` e `casamento_confiavel` — nao
fica num comentario. Uma tela que mostre atividade de senador carrega a marca de
que a identidade foi inferida, e nao confirmada.
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import unicodedata
from dataclasses import dataclass
from typing import Any

from ingest.common.cli import executar
from ingest.common.config import DATASET_RAW_LEGISLATIVO, get_settings
from ingest.common.http import get_json, utc_now
from ingest.common.log import get_logger
from ingest.common.textnorm import cpf_hash
from ingest.common.writer import NdjsonWriter

log = get_logger("legislativo")

API_CAMARA = "https://dadosabertos.camara.leg.br/api/v2"
API_SENADO = "https://legis.senado.leg.br/dadosabertos"

PAUSA = 0.4

# Quantos parlamentares cada Casa deve ter. Serve de trava: se a coleta voltar com
# muito menos, alguma coisa mudou na fonte e a ficha de dezenas de candidatos
# ficaria silenciosamente sem atividade.
ESPERADO = {"camara": 513, "senado": 81}
TOLERANCIA = 0.9  # aceita ate' 10% a menos (licencas, vagas em aberto)

_ESPACOS = re.compile(r"\s+")


def normaliza_nome(valor: Any) -> str:
    """Maiuscula, sem acento, espaco unico — para casar com o TSE."""
    texto = unicodedata.normalize("NFD", str(valor or "")).encode("ascii", "ignore").decode()
    return _ESPACOS.sub(" ", texto).strip().upper()


@dataclass(frozen=True)
class Parlamentar:
    casa: str
    id_casa: str
    nome_parlamentar: str | None
    nome_completo: str | None
    nome_normalizado: str | None
    data_nascimento: str | None
    sexo: str | None
    sigla_partido: str | None
    sg_uf: str | None
    cpf_hash: str | None
    metodo_casamento: str
    url_perfil: str | None

    @property
    def casamento_confiavel(self) -> bool:
        return self.metodo_casamento == "cpf"


def _json(url: str) -> dict[str, Any]:
    dados = get_json(url, timeout=60, attempts=3)
    time.sleep(PAUSA)
    return dados


def coletar_camara() -> list[Parlamentar]:
    """Deputados em exercicio. O CPF vem no detalhe, nao na lista."""
    saida: list[Parlamentar] = []
    pagina = 1
    while True:
        lote = _json(f"{API_CAMARA}/deputados?itens=100&pagina={pagina}&ordem=ASC&ordenarPor=nome")
        dados = lote.get("dados") or []
        if not dados:
            break
        for dep in dados:
            det = (_json(f"{API_CAMARA}/deputados/{dep['id']}") or {}).get("dados") or {}
            saida.append(
                Parlamentar(
                    casa="camara",
                    id_casa=str(dep["id"]),
                    nome_parlamentar=dep.get("nome"),
                    nome_completo=det.get("nomeCivil"),
                    nome_normalizado=normaliza_nome(det.get("nomeCivil")),
                    data_nascimento=det.get("dataNascimento"),
                    sexo=det.get("sexo"),
                    sigla_partido=dep.get("siglaPartido"),
                    sg_uf=dep.get("siglaUf"),
                    cpf_hash=cpf_hash(det.get("cpf")),
                    metodo_casamento="cpf" if cpf_hash(det.get("cpf")) else "nome_nascimento",
                    url_perfil=dep.get("uri"),
                )
            )
        log.info("camara: %d deputados coletados", len(saida))
        if len(dados) < 100:
            break
        pagina += 1
    return saida


def coletar_senado() -> list[Parlamentar]:
    """Senadores em exercicio. Sem CPF na fonte — casa por nome + nascimento."""
    lista = _json(f"{API_SENADO}/senador/lista/atual.json")
    parlamentares = lista["ListaParlamentarEmExercicio"]["Parlamentares"]["Parlamentar"]
    saida: list[Parlamentar] = []
    for p in parlamentares:
        ident = p.get("IdentificacaoParlamentar") or {}
        codigo = str(ident.get("CodigoParlamentar"))
        detalhe = _json(f"{API_SENADO}/senador/{codigo}.json")
        basicos = (
            (detalhe.get("DetalheParlamentar") or {}).get("Parlamentar") or {}
        ).get("DadosBasicosParlamentar") or {}
        nome_completo = ident.get("NomeCompletoParlamentar")
        saida.append(
            Parlamentar(
                casa="senado",
                id_casa=codigo,
                nome_parlamentar=ident.get("NomeParlamentar"),
                nome_completo=nome_completo,
                nome_normalizado=normaliza_nome(nome_completo),
                data_nascimento=basicos.get("DataNascimento"),
                sexo=ident.get("SexoParlamentar"),
                sigla_partido=ident.get("SiglaPartidoParlamentar"),
                sg_uf=ident.get("UfParlamentar"),
                cpf_hash=None,
                metodo_casamento="nome_nascimento",
                url_perfil=ident.get("UrlPaginaParlamentar"),
            )
        )
    log.info("senado: %d senadores coletados", len(saida))
    return saida


COLETORES = {"camara": coletar_camara, "senado": coletar_senado}


def _schema():
    from google.cloud import bigquery

    from ingest.common.bq import build_schema

    campos = [
        "casa",
        "id_casa",
        "nome_parlamentar",
        "nome_completo",
        "nome_normalizado",
        "data_nascimento",
        "sexo",
        "sigla_partido",
        "sg_uf",
        "cpf_hash",
        "metodo_casamento",
        "url_perfil",
    ]
    schema = build_schema(campos)
    corte = len(campos)
    return (
        schema[:corte]
        + [bigquery.SchemaField("casamento_confiavel", "BOOL")]
        + schema[corte:]
    )


def cmd_load(args: argparse.Namespace) -> int:
    settings = get_settings()
    settings.ensure_dirs()
    casas = [args.casa] if args.casa else list(COLETORES)

    if args.dry_run:
        for casa in casas:
            log.info("[dry-run] coletaria %s (~%d parlamentares)", casa, ESPERADO[casa])
        return 0

    todos: list[Parlamentar] = []
    for casa in casas:
        coletados = COLETORES[casa]()
        piso = int(ESPERADO[casa] * TOLERANCIA)
        if len(coletados) < piso:
            log.error(
                "%s devolveu %d parlamentares, esperado ao menos %d. A carga para "
                "aqui: seguir deixaria dezenas de fichas sem atividade, em silencio.",
                casa,
                len(coletados),
                piso,
            )
            return 1
        todos.extend(coletados)

    destino = settings.staging_dir / "legislativo" / "parlamentares.ndjson.gz"
    extraido_em = utc_now()
    with NdjsonWriter(destino) as writer:
        for p in todos:
            writer.write(
                {
                    "casa": p.casa,
                    "id_casa": p.id_casa,
                    "nome_parlamentar": p.nome_parlamentar,
                    "nome_completo": p.nome_completo,
                    "nome_normalizado": p.nome_normalizado,
                    "data_nascimento": p.data_nascimento,
                    "sexo": p.sexo,
                    "sigla_partido": p.sigla_partido,
                    "sg_uf": p.sg_uf,
                    "cpf_hash": p.cpf_hash,
                    "metodo_casamento": p.metodo_casamento,
                    "url_perfil": p.url_perfil,
                    "casamento_confiavel": p.casamento_confiavel,
                    "_extracted_at": extraido_em,
                    "_source_url": API_CAMARA if p.casa == "camara" else API_SENADO,
                    "_source_file": p.casa,
                    "_source_sha256": "",
                }
            )

    com_cpf = sum(1 for p in todos if p.cpf_hash)
    log.info("%d parlamentares | %d com CPF (%s)", len(todos), com_cpf, "casamento exato")

    if args.target == "local":
        log.info("NDJSON em %s", destino)
        return 0

    from ingest.common.bq import ensure_datasets, load_ndjson

    ensure_datasets()
    load_ndjson(
        destino,
        DATASET_RAW_LEGISLATIVO,
        "parlamentares",
        schema=_schema(),
        clustering=("casa", "sg_uf"),
    )
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Mede a taxa de casamento contra `dim_candidato`. Nao carrega nada."""
    from google.cloud import bigquery

    settings = get_settings()
    cliente = bigquery.Client(project=settings.project, location=settings.location)

    for casa in COLETORES:
        parlamentares = COLETORES[casa]()
        print(f"\n=== {casa}: {len(parlamentares)} parlamentares (esperado {ESPERADO[casa]})")

        com_cpf = [p for p in parlamentares if p.cpf_hash]
        if com_cpf:
            lista = "','".join(p.cpf_hash for p in com_cpf if p.cpf_hash)
            consulta = (
                f"select distinct cpf_hash from `{settings.project}.marts.dim_candidato` "
                f"where cpf_hash in ('{lista}')"
            )
            achados = {r.cpf_hash for r in cliente.query(consulta).result()}
            print(f"  por CPF            : {len(achados)} de {len(com_cpf)}")

        sem_cpf = [p for p in parlamentares if not p.cpf_hash and p.nome_normalizado]
        if sem_cpf:
            nomes = "','".join(p.nome_normalizado.replace("'", "''") for p in sem_cpf)
            consulta = f"""
                select distinct
                    upper(regexp_replace(normalize(nome_completo, NFD), r'\\pM', '')) as nome
                from `{settings.project}.marts.dim_candidato`
                where upper(regexp_replace(normalize(nome_completo, NFD), r'\\pM', ''))
                      in ('{nomes}')
            """
            achados = {r.nome for r in cliente.query(consulta).result()}
            faltando = [p for p in sem_cpf if p.nome_normalizado not in achados]
            print(f"  por nome+nascimento: {len(sem_cpf) - len(faltando)} de {len(sem_cpf)}")
            for p in faltando[:5]:
                print(f"     nao casou: {p.nome_parlamentar} ({p.nome_normalizado})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ingest.legislativo", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_load = sub.add_parser("load", help="coleta os parlamentares e carrega a ponte")
    p_load.add_argument("--casa", choices=tuple(COLETORES))
    p_load.add_argument("--ano", type=int, help="aceito por convencao do SPEC 9; nao filtra")
    p_load.add_argument("--dry-run", action="store_true")
    p_load.add_argument("--target", choices=("bigquery", "local"), default="bigquery")
    p_load.set_defaults(func=cmd_load)

    p_ver = sub.add_parser("verify", help="mede a taxa de casamento contra dim_candidato")
    p_ver.set_defaults(func=cmd_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return executar(args.func, args)


if __name__ == "__main__":
    sys.exit(main())
