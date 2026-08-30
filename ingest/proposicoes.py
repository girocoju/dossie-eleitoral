"""Atividade legislativa na Camara — F-16 (S17).

    python -m ingest.proposicoes load   [--ano-inicio 2023] [--dry-run] [--target local]
    python -m ingest.proposicoes verify [--ano 2025]

NAO CONFUNDA com `ingest/propostas.py`. Os nomes sao quase iguais em portugues e
as duas coisas nao tem relacao:

    propostas.py    plano de governo registrado no TSE por candidato majoritario
    proposicoes.py  projetos, requerimentos e emendas apresentados na Camara

O QUE ESTE MODULO SE RECUSA A PRODUZIR
--------------------------------------
Uma contagem unica de "proposicoes do deputado X". Esse numero circula muito e e'
enganoso por tres motivos distintos, e cada um deles virou um filtro aqui:

1. AUTORIA x ASSINATURA. A Camara registra como "autor" todo mundo que assina.
   Medido nesta base: o maior requerimento de 2025 tem 264 assinaturas, das quais 263 sao apoio.
   Em 2025, das 139.413 linhas de autoria com deputado identificado, 78,6%
   sao proponente e 21,4% sao apoio. Contar apoio como autoria infla quem
   assina tudo. Ficamos so' com `proponente = 1`.

2. TIPO. Um PL que altera o Codigo Penal e um requerimento de voto de pesar
   entram na mesma contagem bruta. Em 2025: 7.695 projetos de lei para 32 mil
   requerimentos e 15.501 pareceres de relator. Somar tudo premia volume, nao
   trabalho. Separamos em `classe_proposicao`.

3. DESTINO. Apresentar e' barato; virar lei nao e'. Uma contagem sem desfecho
   sugere resultado onde ha' so' protocolo. Carregamos `situacao`, `arquivada` e
   `virou_norma`.

E o que este modulo tambem NAO calcula: taxa de aprovacao. Aprovacao depende de o
deputado estar na base do governo, nao do merito do texto — uma taxa puniria a
oposicao por ser oposicao, em qualquer governo. Isso e' placar, e o projeto e'
apartidario (Constituicao 0.1).

FONTE
-----
Arquivos em bloco, nao a API. A API exigiria uma chamada a
`/proposicoes/{id}/autores` por proposicao para descobrir quem e' proponente —
dezenas de milhares de requisicoes por ano. Os arquivos anuais trazem a mesma
informacao em dois downloads:

    proposicoesAutores-{ano}.csv   idDeputadoAutor, ordemAssinatura, proponente
    proposicoes-{ano}.csv          siglaTipo, ementa, ultimoStatus_*

Conferido em 28/08/2026.
"""

from __future__ import annotations

import argparse
import csv
import sys
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from ingest.common.cli import executar
from ingest.common.config import DATASET_RAW_LEGISLATIVO, get_settings
from ingest.common.http import download, utc_now
from ingest.common.log import get_logger
from ingest.common.writer import NdjsonWriter

log = get_logger("proposicoes")

BASE = "https://dadosabertos.camara.leg.br/arquivos"

# Legislatura atual: 2023-2026. E' o mandato que se pode mostrar na ficha de um
# deputado que disputa a reeleicao em 2026.
ANO_INICIO = 2023
ANO_FIM = 2026

# Classificacao por tipo. E' a defesa contra o problema 2 do cabecalho: sem ela,
# 400 requerimentos de um deputado e 12 projetos de lei de outro viram o mesmo
# numero, e o segundo parece ter trabalhado 33x menos.
CLASSES = {
    # Cria ou altera norma. Custo alto: exige texto, relatoria e votacao.
    "normativa": {
        "PL", "PLP", "PEC", "PLV", "MPV", "PDL", "PDC", "PRC", "PLN", "PDS", "PLC",
    },
    # Pede contas ao Executivo. Protocolo barato, mas e' fiscalizacao de verdade —
    # funcao constitucional do Legislativo, nao enfeite.
    "fiscalizacao": {"RIC", "PFC", "RCP"},
    # Parecer de relator, parecer de comissao, substitutivo. NAO e' autoria: o
    # deputado nao propos nada, ele analisou a proposta de outro. E' trabalho de
    # peso — 15.501 pareceres em 2025 — mas responde a outra pergunta, e somar com
    # projeto de lei confunde quem escreveu com quem relatou.
    "relatoria": {"PRL", "PRLP", "PAR", "SBT", "CVO"},
    # Rito: retirada de pauta, inversao de pauta, adiamento, audiencia publica,
    # voto de louvor, emenda, indicacao. Volume alto e custo baixo. Nao e'
    # desmerecimento — e' outra ordem de grandeza, e por isso nao soma junto.
    "procedimental": {
        "REQ", "RQE", "RQP", "RQN", "RPD", "DTQ", "RDF", "INC", "REC",
        "EMP", "EMC", "EMR", "EMS", "EML", "ERD",
    },
}
CLASSE_POR_TIPO = {tipo: classe for classe, tipos in CLASSES.items() for tipo in tipos}

# A Camara escreve a situacao com o genero do TIPO da proposicao: "Transformado
# em Norma Juridica" para um projeto de lei, "Transformada" para uma emenda. Casar
# com a string exata no feminino devolvia ZERO em 2025 — e um painel que diz que
# nenhum projeto virou lei e' pior do que um painel sem o campo. Casamos por
# trecho, sem o genero.
TRECHO_VIROU_NORMA = "norma juridica"

# Situacoes que significam "acabou sem virar norma", nos dois generos.
SITUACOES_ARQUIVADAS = {
    "arquivada", "arquivado",
    "declarada prejudicada", "declarado prejudicado",
    "retirada pelo autor", "retirado pelo autor",
    "devolvida ao autor", "devolvido ao autor",
}

COLUNAS_TEXTO = (
    "id_proposicao",
    "sigla_tipo",
    "descricao_tipo",
    "classe_proposicao",
    "numero",
    "ementa",
    "data_apresentacao",
    "situacao",
    "tramitacao",
    "sigla_orgao",
    "url_inteiro_teor",
    "id_deputado",
    "nome_autor",
    "sigla_partido_autor",
    "sigla_uf_autor",
    "ordem_assinatura",
)


def _sem_acento(texto: Any) -> str:
    bruto = unicodedata.normalize("NFD", str(texto or ""))
    return bruto.encode("ascii", "ignore").decode().strip().lower()


def _url(nome: str, ano: int) -> str:
    return f"{BASE}/{nome}/csv/{nome}-{ano}.csv"


def _ler_csv(caminho: Path | str) -> Iterator[dict[str, str]]:
    """Le em streaming: o arquivo de proposicoes passa de 90 MB por ano."""
    with Path(caminho).open("r", encoding="utf-8-sig", newline="") as fh:
        yield from csv.DictReader(fh, delimiter=";")


def coletar_ano(ano: int, destino_dir: Path, *, force: bool = False) -> list[dict[str, Any]]:
    autores_csv = download(
        _url("proposicoesAutores", ano),
        destino_dir / f"proposicoesAutores-{ano}.csv",
        force=force,
    ).path
    props_csv = download(
        _url("proposicoes", ano), destino_dir / f"proposicoes-{ano}.csv", force=force
    ).path

    # Passo 1: quem propos de fato. Guarda tambem quantas assinaturas a proposicao
    # tem no total — e' o que deixa a diferenca entre autoria e apoio visivel na
    # propria linha, e nao so' neste comentario.
    proponentes: dict[str, list[dict[str, str]]] = defaultdict(list)
    assinantes: Counter[str] = Counter()
    linhas_autor = 0
    for linha in _ler_csv(autores_csv):
        id_prop = linha.get("idProposicao") or ""
        assinantes[id_prop] += 1
        linhas_autor += 1
        # `idDeputadoAutor` vazio = autoria de orgao, Senado, Executivo ou bancada.
        # Nao ha' pessoa para ligar a' ficha de um candidato.
        if not (linha.get("idDeputadoAutor") or "").strip():
            continue
        if (linha.get("proponente") or "").strip() != "1":
            continue
        proponentes[id_prop].append(linha)

    log.info(
        "%d: %d linhas de autoria, %d proposicoes com deputado proponente",
        ano,
        linhas_autor,
        len(proponentes),
    )

    # Passo 2: os atributos da proposicao, so' das que interessam.
    saida: list[dict[str, Any]] = []
    for prop in _ler_csv(props_csv):
        id_prop = prop.get("id") or ""
        autores = proponentes.get(id_prop)
        if not autores:
            continue
        sigla = (prop.get("siglaTipo") or "").strip().upper()
        situacao = (prop.get("ultimoStatus_descricaoSituacao") or "").strip()
        situacao_norm = _sem_acento(situacao)
        virou_norma = TRECHO_VIROU_NORMA in situacao_norm
        for autor in autores:
            saida.append(
                {
                    "ano": ano,
                    "id_proposicao": id_prop,
                    "sigla_tipo": sigla,
                    "descricao_tipo": (prop.get("descricaoTipo") or "").strip(),
                    "classe_proposicao": CLASSE_POR_TIPO.get(sigla, "outra"),
                    "numero": (prop.get("numero") or "").strip(),
                    "ementa": (prop.get("ementa") or "").strip()[:1000],
                    "data_apresentacao": (prop.get("dataApresentacao") or "").strip()[:10],
                    "situacao": situacao,
                    "tramitacao": (prop.get("ultimoStatus_descricaoTramitacao") or "").strip(),
                    "sigla_orgao": (prop.get("ultimoStatus_siglaOrgao") or "").strip(),
                    "arquivada": situacao_norm in SITUACOES_ARQUIVADAS,
                    "virou_norma": virou_norma,
                    # Mais da metade das proposicoes vem com situacao em branco na
                    # fonte. Isso NAO e' "em tramitacao" — e' desconhecido. Sem
                    # esta marca, a tela contaria ausencia como andamento.
                    "situacao_conhecida": bool(situacao),
                    "url_inteiro_teor": (prop.get("urlInteiroTeor") or "").strip(),
                    "id_deputado": (autor.get("idDeputadoAutor") or "").strip(),
                    "nome_autor": (autor.get("nomeAutor") or "").strip(),
                    "sigla_partido_autor": (autor.get("siglaPartidoAutor") or "").strip(),
                    "sigla_uf_autor": (autor.get("siglaUFAutor") or "").strip(),
                    "ordem_assinatura": (autor.get("ordemAssinatura") or "").strip(),
                    "total_assinantes": assinantes.get(id_prop, 0),
                }
            )
    return saida


def _schema():
    from google.cloud import bigquery

    from ingest.common.bq import build_schema

    schema = build_schema(list(COLUNAS_TEXTO))
    corte = len(COLUNAS_TEXTO)
    tipados = [
        bigquery.SchemaField("ano", "INT64"),
        bigquery.SchemaField("arquivada", "BOOL"),
        bigquery.SchemaField("virou_norma", "BOOL"),
        bigquery.SchemaField("situacao_conhecida", "BOOL"),
        bigquery.SchemaField("total_assinantes", "INT64"),
    ]
    return schema[:corte] + tipados + schema[corte:]


def cmd_load(args: argparse.Namespace) -> int:
    settings = get_settings()
    settings.ensure_dirs()
    anos = [args.ano] if args.ano else list(range(args.ano_inicio, args.ano_fim + 1))

    if args.dry_run:
        for ano in anos:
            log.info("[dry-run] baixaria %s", _url("proposicoesAutores", ano))
            log.info("[dry-run] baixaria %s", _url("proposicoes", ano))
        return 0

    bruto = settings.download_dir / "camara"
    bruto.mkdir(parents=True, exist_ok=True)

    # UM NDJSON POR ANO, e uma carga por particao.
    #
    # A versao anterior juntava tudo e chamava `load_ndjson`, que SUBSTITUI a
    # tabela inteira. Funcionava enquanto so' havia 2023-2026, e passou a ser um
    # problema quando os anos historicos entraram: a carga diaria, que so' olha
    # os anos recentes, apagaria 2003-2022 todo dia (ADR-024).
    #
    # `load_ano` troca APENAS a particao daquele ano (ADR-010), entao carregar
    # 2026 nao encosta em 2011.
    extraido_em = utc_now()
    total = 0
    por_classe: Counter[str] = Counter()
    deputados: set[str] = set()
    carregados: list[int] = []
    indisponiveis: list[int] = []

    for ano in anos:
        try:
            linhas = coletar_ano(ano, bruto, force=args.force)
        except Exception as exc:  # noqa: BLE001
            # O arquivo do ano corrente so' existe depois da primeira publicacao.
            log.warning("%d indisponivel: %s", ano, str(exc)[:120])
            indisponiveis.append(ano)
            continue

        if not linhas:
            log.warning("%d veio vazio — particao preservada como estava", ano)
            indisponiveis.append(ano)
            continue

        destino = settings.staging_dir / "legislativo" / f"proposicoes-{ano}.ndjson.gz"
        with NdjsonWriter(destino) as writer:
            for linha in linhas:
                writer.write({
                    **linha,
                    "_extracted_at": extraido_em,
                    "_source_url": BASE,
                    "_source_file": f"proposicoes-{ano}.csv",
                    "_source_sha256": "",
                })

        total += len(linhas)
        por_classe.update(x["classe_proposicao"] for x in linhas)
        deputados.update(x["id_deputado"] for x in linhas)

        if args.target != "local":
            from ingest.common.bq import ensure_datasets, load_intervalo  # noqa: PLC0415

            ensure_datasets()
            load_intervalo(destino, DATASET_RAW_LEGISLATIVO, "proposicoes",
                           schema=_schema(), coluna="ano", valor=ano,
                           clustering=("id_deputado", "classe_proposicao"))
        carregados.append(ano)

    if not carregados:
        log.error("nenhum ano carregado — a carga nao substitui a tabela por vazio")
        return 1

    log.info("%d proposicoes de %d deputados em %d anos (%s) | %s",
             total, len(deputados), len(carregados),
             f"{min(carregados)}-{max(carregados)}",
             " ".join(f"{c}={n}" for c, n in por_classe.most_common()))
    if indisponiveis:
        log.warning("anos sem dado nesta execucao: %s — particoes preservadas",
                    indisponiveis)
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Mede o tamanho de cada filtro. E' a prova de que eles nao sao cosmeticos."""
    settings = get_settings()
    settings.ensure_dirs()
    bruto = settings.download_dir / "camara"
    bruto.mkdir(parents=True, exist_ok=True)
    ano = args.ano

    autores_csv = download(
        _url("proposicoesAutores", ano), bruto / f"proposicoesAutores-{ano}.csv"
    ).path

    total = com_deputado = proponente = 0
    maior = ("", 0)
    assinantes: Counter[str] = Counter()
    for linha in _ler_csv(autores_csv):
        total += 1
        id_prop = linha.get("idProposicao") or ""
        assinantes[id_prop] += 1
        if assinantes[id_prop] > maior[1]:
            maior = (id_prop, assinantes[id_prop])
        if (linha.get("idDeputadoAutor") or "").strip():
            com_deputado += 1
            if (linha.get("proponente") or "").strip() == "1":
                proponente += 1

    pct = proponente / max(com_deputado, 1)
    print(f"\n=== autoria em {ano}")
    print(f"  linhas de autoria no arquivo : {total:>9,}")
    print(f"  com deputado identificado    : {com_deputado:>9,}")
    print(f"  DESSAS, proponente de fato   : {proponente:>9,}  ({pct:.1%})")
    print(f"  maior lista de assinaturas   : {maior[1]:>9,} na proposicao {maior[0]}")

    linhas = coletar_ano(ano, bruto)
    print(f"\n=== {len(linhas):,} proposicoes com proponente deputado, por classe")
    for classe, n in Counter(x["classe_proposicao"] for x in linhas).most_common():
        print(f"  {classe:<16}{n:>8,}")
    print("\n=== destino")
    print(f"  virou norma juridica         : {sum(1 for x in linhas if x['virou_norma']):>9,}")
    print(f"  arquivada/prejudicada        : {sum(1 for x in linhas if x['arquivada']):>9,}")
    sem_situacao = sum(1 for x in linhas if not x["situacao_conhecida"])
    print(f"  situacao em branco na fonte  : {sem_situacao:>9,}")
    print("\n=== o que sobrou em 'outra'")
    residuo = Counter(x["sigla_tipo"] for x in linhas if x["classe_proposicao"] == "outra")
    for tipo, n in residuo.most_common(5):
        print(f"  {tipo:<6}{n:>8,}")
    print("\n=== tipos mais frequentes")
    for tipo, n in Counter(x["sigla_tipo"] for x in linhas).most_common(8):
        print(f"  {tipo:<6}{CLASSE_POR_TIPO.get(tipo, 'outra'):<16}{n:>8,}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ingest.proposicoes", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_load = sub.add_parser("load", help="baixa a atividade legislativa e carrega")
    p_load.add_argument("--ano", type=int)
    p_load.add_argument("--ano-inicio", type=int, default=ANO_INICIO)
    p_load.add_argument("--ano-fim", type=int, default=ANO_FIM)
    p_load.add_argument("--force", action="store_true", help="rebaixa mesmo com cache valido")
    p_load.add_argument("--dry-run", action="store_true")
    p_load.add_argument("--target", choices=("bigquery", "local"), default="bigquery")
    p_load.set_defaults(func=cmd_load)

    p_ver = sub.add_parser("verify", help="mede o tamanho de cada filtro")
    p_ver.add_argument("--ano", type=int, default=2025)
    p_ver.set_defaults(func=cmd_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return executar(args.func, args)


if __name__ == "__main__":
    sys.exit(main())
