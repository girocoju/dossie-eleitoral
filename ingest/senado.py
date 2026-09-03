"""Atividade legislativa no Senado — fecha a L-20.

A F-16 cobria so' a Camara. Os 81 senadores tinham a ponte de identidade (F-15) e
apareciam em `dim_parlamentar`, mas nenhuma proposicao deles existia no projeto —
e 42 deles sao candidatos em 2026, incluindo um a presidente.

═══════════════════════════════════════════════════════════════════════
O QUE A L-20 EXIGIA RESOLVER, E COMO FOI RESOLVIDO
═══════════════════════════════════════════════════════════════════════

A lacuna dizia, com razao, que montar uma contagem sem equivalente ao filtro
`proponente` da Camara produziria numeros que PARECEM comparaveis e nao sao: um
senador com 200 assinaturas de apoio apareceria ao lado de um deputado com 200
projetos proprios, na mesma coluna, com o mesmo rotulo.

O equivalente existe: `documento.autoria[].ordem`. Autor de `ordem = 1` e' o
autor principal; os demais assinam junto.

── Por que NAO o endpoint que traz a flag pronta ──

`/senador/{cod}/autorias` devolve `IndicadorAutorPrincipal` numa unica chamada
por senador. Seria oito vezes mais barato. Mas ele esta' DESCONTINUADO: os
proprios metadados trazem `DataDepreciacao: 2025-03-18` e
`DataDesativacaoCompleta: 2026-02-01` — data ja' vencida quando isto foi escrito
(02/09/2026). Ele ainda responde, e e' exatamente por isso que e' perigoso:
construir em cima faria a secao apodrecer em silencio no dia em que sair do ar.

Ele foi usado uma vez, para VALIDAR o substituto — ver abaixo.

── Por que NAO ler o nome do primeiro autor da string ──

A lista (`/processo?codigoParlamentarAutor=`) traz `autoria` como texto corrido:
"Senador Fulano (PL/RJ), Senador Beltrano (PT/SP), ...". O primeiro nome e' o
autor principal, e bastaria compara-lo com o nome do senador.

Medido nas 445 autorias de Flavio Bolsonaro: 438 acertos e 7 erros — todos o
mesmo caso, "Lider do PL Flavio Bolsonaro (PL/RJ)", em que o titulo nao e'
"Senador". Da' para remendar o regex, e vao aparecer "Lider do Governo",
"Presidente da Comissao" e o que mais o Senado inventar. 1,6% de erro numa
contagem que a tela apresenta ao lado da contagem da Camara e' exatamente a
comparacao falsa que a L-20 mandava evitar.

── A validacao que autorizou usar `ordem` ──

Comparadas as duas fontes para o mesmo senador, em 02/09/2026:

    amostra inicial (25 primeiras)      24 concordam, 0 divergem, 1 sem par
    amostra estratificada (12 Sim +
      12 Nao, sorteadas)                24 concordam, 0 divergem

48 comparacoes nas duas direcoes, nenhuma divergencia. `ordem = 1` e'
`IndicadorAutorPrincipal = Sim`.

═══════════════════════════════════════════════════════════════════════
O CUSTO, E POR QUE ELE E' ACEITAVEL
═══════════════════════════════════════════════════════════════════════

A autoria estruturada so' existe no DETALHE do processo, um por requisicao. Sao
57.156 autorias somadas entre os 81 senadores, mas apenas 30.234 processos
UNICOS — o mesmo processo aparece na lista de cada coautor, entao um detalhe
resolve todos eles de uma vez (reuso de 1,89x).

E o indice em disco (`processos.ndjson.gz`) guarda o que ja' foi extraido: a
primeira carga busca 30 mil detalhes, e as seguintes so' os processos novos.
Sem ele, a atualizacao diaria refaria tudo.
"""

from __future__ import annotations

import argparse
import gzip
import json
import sys
from collections.abc import Iterable, Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from ingest.common.config import DATASET_RAW_LEGISLATIVO, get_settings
from ingest.common.http import get_json, utc_now
from ingest.common.log import get_logger
from ingest.common.writer import NdjsonWriter

log = get_logger("senado")

# ═══════════════════════════════════════════════════════════════════════
# AS MESMAS QUATRO CLASSES DA CAMARA, COM O VOCABULARIO DO SENADO
# ═══════════════════════════════════════════════════════════════════════
#
# `fct_atividade_legislativa` nao tem linha "total do deputado", de proposito:
# somar requerimento com projeto de lei produz o numero que circula na imprensa
# e nao significa nada. O Senado precisa da mesma separacao, ou os dois blocos
# ficariam lado a lado medindo coisas diferentes.
#
# O mapeamento saiu da LISTA OFICIAL de siglas do Senado
# (`/dadosabertos/dados/ListaSiglas.json`, 184 siglas com descricao), nao de
# palpite. Isso importa: `RQI` PARECE "Requerimento de Informacao" e seria
# fiscalizacao — a descricao oficial diz "Requerimento da Comissao de Servicos
# de Infraestrutura", que e' rito de comissao. Classificar pelo formato da sigla
# teria posto no lugar errado.
CLASSES = {
    # Cria ou altera norma.
    "normativa": {
        "MPV", "PDA", "PDC", "PDF", "PDL", "PDN", "PDR", "PDS", "PEC", "PER",
        "PL", "PLC", "PLCNC", "PLD", "PLN", "PLP", "PLS", "PLV", "PR.", "PRA",
        "PRC", "PRF", "PRFC", "PRN", "PROJ", "PRR", "PRS",
    },
    # Exige contas ou investigacao. Funcao constitucional, nao enfeite.
    #   INQ  Inquerito (SF)              PFC/PFS  Proposta de Fiscalizacao e Controle
    #   RIC  Requerimento de Informacao  SIT      Solicitacao de Informacao ao TCU
    "fiscalizacao": {"INQ", "PFC", "PFS", "RIC", "SIT"},
    # Analisou o texto de outro. NAO e' autoria.
    "relatoria": {"P.C", "P.S", "PAC", "PAR", "PCA", "PCS",
                  "RELA", "RELAT", "SCD", "SDS"},
}
CLASSE_POR_TIPO = {t: c for c, tipos in CLASSES.items() for t in tipos}

# Todo o resto e' rito: requerimento de comissao (RQI, RQJ, RRA, RDH...),
# requerimento de plenario (RQS, REQ), recurso, oficio, indicacao. Volume alto e
# custo baixo — nao e' desmerecimento, e' outra ordem de grandeza.
CLASSE_PADRAO = "procedimental"


def classe_de(sigla: str | None) -> str:
    return CLASSE_POR_TIPO.get((sigla or "").strip().upper(), CLASSE_PADRAO)

BASE = "https://legis.senado.leg.br/dadosabertos"

# Quatro conexoes. A API do Senado nao publica limite; quatro mantem a carga
# inteira em torno de vinte minutos sem parecer varredura.
THREADS = 4


def _lista_url(codigo: int) -> str:
    return f"{BASE}/processo?codigoParlamentarAutor={codigo}&v=1"


def _detalhe_url(processo_id: int) -> str:
    return f"{BASE}/processo/{processo_id}?v=1"


def _indice_path(settings) -> Path:
    return settings.download_dir / "senado" / "processos.ndjson.gz"


def carregar_indice(caminho: Path) -> dict[int, dict[str, Any]]:
    """O que ja' foi extraido em cargas anteriores."""
    if not caminho.exists():
        return {}
    indice: dict[int, dict[str, Any]] = {}
    try:
        with gzip.open(caminho, "rt", encoding="utf-8") as fh:
            for linha in fh:
                if linha.strip():
                    reg = json.loads(linha)
                    indice[int(reg["processo_id"])] = reg
    except (OSError, json.JSONDecodeError, KeyError, ValueError) as exc:
        # Indice corrompido nao pode derrubar a carga: no pior caso ele e'
        # reconstruido, que e' lento mas correto.
        log.warning("indice ilegivel (%s) — sera' refeito", str(exc)[:80])
        return {}
    return indice


def gravar_indice(caminho: Path, indice: dict[int, dict[str, Any]]) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tmp = caminho.with_suffix(".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as fh:
        for reg in indice.values():
            fh.write(json.dumps(reg, ensure_ascii=False) + "\n")
    tmp.replace(caminho)


def coletar_listas(codigos: Iterable[int]) -> dict[int, dict[str, Any]]:
    """Uma requisicao por senador. Devolve os processos por id, sem repetir."""
    processos: dict[int, dict[str, Any]] = {}
    codigos = list(codigos)
    for i, cod in enumerate(codigos, 1):
        try:
            itens = get_json(_lista_url(cod))
        except Exception as exc:  # noqa: BLE001 — fonte fora do ar vira aviso (ADR-022)
            log.warning("senador %s: lista indisponivel (%s)", cod, str(exc)[:70])
            continue
        if not isinstance(itens, list):
            continue
        for x in itens:
            pid = x.get("id")
            if pid:
                processos.setdefault(int(pid), x)
        if i % 20 == 0 or i == len(codigos):
            log.info("listas: %d/%d senadores, %d processos unicos",
                     i, len(codigos), len(processos))
    return processos


def extrair_autoria(detalhe: dict[str, Any]) -> list[dict[str, Any]]:
    """Autores estruturados de um processo, com a ordem de assinatura."""
    doc = detalhe.get("documento") or {}
    saida = []
    for a in doc.get("autoria") or []:
        cod = a.get("codigoParlamentar")
        if cod is None:
            # Comissao, Poder Executivo, iniciativa popular. Nao ha' senador a
            # quem atribuir, e inventar um seria pior que a ausencia.
            continue
        saida.append({
            "codigo_parlamentar": int(cod),
            "nome_autor": a.get("autor"),
            "ordem": a.get("ordem"),
            "sigla_partido": a.get("siglaPartido"),
            "sg_uf": a.get("uf"),
        })
    return saida


def coletar_detalhes(ids: list[int], indice: dict[int, dict[str, Any]],
                     *, limite: int | None = None) -> int:
    """Busca o detalhe dos processos que ainda nao estao no indice."""
    faltando = [p for p in ids if p not in indice]
    ja_tinha = len(ids) - len(faltando)
    if limite:
        # A contagem do que o indice JA' tinha e' feita antes do corte: senao o
        # log diz "o indice ja' tinha 405" quando na verdade sao 405 que este
        # comando escolheu nao buscar. Numero certo com rotulo errado e' a
        # familia de erro que este projeto mais evita.
        faltando = faltando[:limite]
    if not faltando:
        log.info("nenhum processo novo — indice ja' cobre os %d", len(ids))
        return 0

    log.info("%d processos a buscar de %d (o indice ja' tinha %d)",
             len(faltando), len(ids), ja_tinha)
    novos = 0

    def buscar(pid: int) -> tuple[int, dict[str, Any] | None]:
        try:
            return pid, get_json(_detalhe_url(pid))
        except Exception as exc:  # noqa: BLE001
            log.warning("processo %s: %s", pid, str(exc)[:60])
            return pid, None

    with ThreadPoolExecutor(max_workers=THREADS) as pool:
        for n, (pid, detalhe) in enumerate(pool.map(buscar, faltando), 1):
            if detalhe is None:
                continue
            doc = detalhe.get("documento") or {}
            indice[pid] = {
                "processo_id": pid,
                "codigo_materia": detalhe.get("codigoMateria"),
                "identificacao": detalhe.get("identificacao"),
                "sigla": detalhe.get("sigla"),
                "descricao_sigla": detalhe.get("descricaoSigla"),
                "ano": detalhe.get("ano"),
                "data_apresentacao": doc.get("dataApresentacao"),
                "tramitando": detalhe.get("tramitando"),
                "autoria": extrair_autoria(detalhe),
            }
            novos += 1
            if n % 500 == 0:
                log.info("detalhes: %d/%d", n, len(faltando))
    return novos


def linhas_para_bq(indice: dict[int, dict[str, Any]],
                   codigos_validos: set[int]) -> Iterator[dict[str, Any]]:
    """Uma linha por (processo, senador autor).

    `autor_principal` e' `ordem = 1` — o equivalente do `proponente = 1` da
    Camara. A tela deve contar SO' as principais; as demais ficam gravadas para
    que a distincao possa ser conferida, nunca somada por engano.
    """
    agora = utc_now()
    for reg in indice.values():
        for a in reg.get("autoria") or []:
            cod = a.get("codigo_parlamentar")
            if cod not in codigos_validos:
                continue
            yield {
                "processo_id": reg["processo_id"],
                "codigo_materia": reg.get("codigo_materia"),
                "identificacao": reg.get("identificacao"),
                "sigla": reg.get("sigla"),
                "descricao_sigla": reg.get("descricao_sigla"),
                "classe_proposicao": classe_de(reg.get("sigla")),
                "ano": reg.get("ano"),
                "data_apresentacao": reg.get("data_apresentacao"),
                "tramitando": reg.get("tramitando"),
                "codigo_parlamentar": cod,
                "nome_autor": a.get("nome_autor"),
                "ordem_assinatura": a.get("ordem"),
                "autor_principal": a.get("ordem") == 1,
                "sigla_partido": a.get("sigla_partido"),
                "sg_uf": a.get("sg_uf"),
                "_extracted_at": agora,
                "_source_url": BASE,
            }


def _schema():
    """Schema explicito, nunca autodetect (convencao do projeto).

    `autor_principal` precisa ser BOOL de verdade: se viajasse como STRING, a
    string "false" seria verdadeira em SQL e a contagem passaria a incluir
    coautoria — exatamente o erro que a L-20 mandava evitar, entrando por uma
    porta de tipagem.
    """
    from google.cloud import bigquery

    from ingest.common.bq import build_schema

    textos = ["identificacao", "sigla", "descricao_sigla", "classe_proposicao",
              "data_apresentacao", "tramitando", "nome_autor",
              "sigla_partido", "sg_uf"]
    schema = build_schema(textos)
    corte = len(textos)
    tipados = [
        bigquery.SchemaField("processo_id", "INT64"),
        bigquery.SchemaField("codigo_materia", "INT64"),
        bigquery.SchemaField("ano", "INT64"),
        bigquery.SchemaField("codigo_parlamentar", "INT64"),
        bigquery.SchemaField("ordem_assinatura", "INT64"),
        bigquery.SchemaField("autor_principal", "BOOL"),
    ]
    return schema[:corte] + tipados + schema[corte:]


def _codigos_de_senador(settings) -> list[int]:
    from google.cloud import bigquery

    cliente = bigquery.Client(project=settings.project, location=settings.location)
    sql = (f"select id_casa from `{settings.project}.marts.dim_parlamentar` "
           "where casa = 'senado' and id_casa is not null")
    return [int(r.id_casa) for r in cliente.query(sql).result()]


def cmd_load(args: argparse.Namespace) -> int:
    settings = get_settings()
    settings.ensure_dirs()

    codigos = args.senador or _codigos_de_senador(settings)
    log.info("%d senadores", len(codigos))

    processos = coletar_listas(codigos)
    if not processos:
        log.error("nenhuma lista veio — nada a fazer")
        return 75  # EX_TEMPFAIL: instabilidade de fonte, nao erro de codigo

    caminho = _indice_path(settings)
    indice = carregar_indice(caminho)
    novos = coletar_detalhes(sorted(processos), indice, limite=args.limite_detalhes)
    if novos:
        gravar_indice(caminho, indice)
        log.info("indice gravado: %d processos", len(indice))

    validos = set(codigos)
    destino = settings.staging_dir / "senado_autoria.ndjson.gz"
    principais = 0
    with NdjsonWriter(destino) as w:
        for linha in linhas_para_bq(indice, validos):
            w.write(linha)
            principais += bool(linha["autor_principal"])
    log.info("%d autorias (%d como autor principal)", w.rows, principais)

    if args.target == "local":
        log.info("NDJSON em %s", destino)
        return 0

    from ingest.common.bq import ensure_datasets, load_ndjson

    ensure_datasets(settings)
    load_ndjson(destino, DATASET_RAW_LEGISLATIVO, "senado_autoria",
                schema=_schema(), clustering=("codigo_parlamentar", "classe_proposicao"),
                settings=settings)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ingest.senado", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    load = sub.add_parser("load", help="coleta autorias do Senado e carrega")
    load.add_argument("--ano", type=int, default=2026,
                      help="aceito por convencao do SPEC 9; a fonte nao filtra por ano")
    load.add_argument("--senador", nargs="*", type=int,
                      help="codigos especificos (default: todos de dim_parlamentar)")
    load.add_argument("--limite-detalhes", type=int,
                      help="busca so' N detalhes novos — para testar rapido")
    load.add_argument("--target", choices=("bigquery", "local"), default="bigquery")
    load.add_argument("--dry-run", action="store_true")
    load.set_defaults(func=cmd_load)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
