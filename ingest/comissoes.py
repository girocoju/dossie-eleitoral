"""Comissoes da Camara: onde cada deputado sentou, e com que papel — F-26.

    python -m ingest.comissoes load [--dry-run] [--target local] [--limite N]
    python -m ingest.comissoes verify

A ficha ja' dizia quantas proposicoes o deputado apresentou e quantas vezes
votou. Nao dizia ONDE ele trabalha. Comissao permanente e' onde a maior parte do
trabalho legislativo acontece de verdade, e assento no Conselho de Etica ou na
Mesa Diretora e' fato publico que muda como se le' o resto da ficha.

Alcance medido em 03/09/2026: 892 das 20.838 candidaturas exibidas de 2026 sao
de gente com casamento confiavel na Camara, e por isso podem receber o bloco.

── O ENDPOINT SO' DEVOLVE O PRESENTE, A MENOS QUE SE PECA O PASSADO ──

`/deputados/{id}/orgaos` sem parametro devolve pouca coisa: Arthur Lira, que
PRESIDIU a Camara, volta com UM vinculo — uma bancada de 2023. Com
`dataInicio`/`dataFim` explicitos cobrindo o periodo, volta com 41, de 2011 a
2025.

Nao e' detalhe de performance: sem as datas, a ficha de quem presidiu a Casa
diria que ele participou de um orgao so'. Ausencia virando afirmacao, de novo.

── O TIPO DO ORGAO VEM DO CATALOGO, E O CATALOGO PADRAO E' INCOMPLETO ──

O vinculo traz sigla e nome do orgao, e NAO traz o tipo. Sem o tipo, "Comissao
de Constituicao e Justica" fica indistinguivel de "Partido Politico" e
"Lideranca", que a API tambem chama de orgao — e a ficha diria que o deputado
"participa do orgao PT" como se fosse uma comissao.

`/orgaos` sem parametro devolve 1.649. Parece o catalogo inteiro, e nao e':
medido em 04/09/2026, 370 orgaos citados por apenas 25 deputados nao estavam
nele. Com `dataInicio=2003-01-01` sobe para 2.230, e a falta cai para 5%.

Os 5% que sobram sao justamente os que mais importam:

    4     MESA       Mesa Diretora
    5467  PRESI      Presidencia
    5971  COETICA    Conselho de Etica e Decoro Parlamentar
    6087  CEXSAUDE   Comissao Externa

Orgaos permanentes da Casa, cuja data de inicio a API nao publica de forma que o
filtro alcance. Sem tratar, a ficha de quem PRESIDIU a Camara ou sentou no
Conselho de Etica sairia sem a linha — e o log diria apenas "N orgaos fora do
catalogo", que ninguem le'.

Por isso o resolvedor tem duas etapas: o catalogo com janela (23 requisicoes) e,
para o que sobrar, uma consulta por orgao com CACHE EM DISCO. Orgao nao muda de
tipo; a segunda execucao nao pede nenhum de novo.

── PAGINAR NAO E' OPCIONAL, E O CORTE PEGA JUSTAMENTE OS MAIS ATUANTES ──

`itens=200` parece folgado — a maioria dos deputados tem menos de 50 vinculos.
Nao e': o corte cai em cima de quem mais trabalhou. Medido em 04/09/2026:

    Hugo Leal        pagina 1 = 200   total real = 242   perdia 42
    Erika Kokay      pagina 1 = 200   total real = 224   perdia 24
    Jose Rocha       pagina 1 = 200   total real = 217   perdia 17
    Alice Portugal   pagina 1 = 200   total real = 205   perdia  5

E o que ficava de fora nao era resto: a conferencia pelo OUTRO endpoint
(`/orgaos/{id}/membros`) mostrou que faltavam membros ATUAIS da CCJC, da
Comissao de Saude, da CFT e da CAPADR — quatro comissoes permanentes, cada uma
com exatamente um nome faltando, e todos veteranos.

Truncar em silencio o deputado de vinte anos de Casa e' pior que nao ter o bloco:
a ficha ficaria mais pobre para quem tem mais historia, sem nada indicando isso.

── O NOME DO TIPO 15 MENTE, E POR ISSO ELE NUNCA VAI A' TELA ──

`codTipoOrgao = 15` chama-se oficialmente "COORDENADORIA DA MULHER". Os 13
orgaos que carregam esse codigo sao: CDMULHER, SEMULHER, SECOM, SRI, SEJUVE,
SETRANSP, SEMIDIA, CONMP, **BANEGRA** (Bancada Negra), SEEMPLEG, SEINOLEG,
SEDEFPAR, SESIDH.

Ou seja: o codigo agrupa secretarias, coordenadorias e bancadas da Casa, e o
NOME do bucket e' o da primeira coisa que entrou nele. Renderizar `tipoOrgao`
como veio diria que a Bancada Negra e' a "Coordenadoria da Mulher".

E' o mesmo erro que a L-20 quase publicou (`RQI` parece "Requerimento de
Informacao" e e' "Requerimento da Comissao de Servicos de Infraestrutura",
ADR-034): o CODIGO e' confiavel, o NOME do codigo nao e'. Este modulo classifica
pelo codigo e escreve o rotulo em portugues aqui, uma vez.

── O QUE ESTE MODULO NAO FAZ ──

Nao coleta comissoes do SENADO. A API do Senado tem `/senador/{codigo}/comissoes`
e o dado existe, mas nenhum senador tem `casamento_confiavel` hoje (a Casa nao
publica CPF, ADR-014) — o bloco nao teria em quem aparecer. Fica registrado como
lacuna, e nao como esquecimento.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any

from ingest.common.cli import executar
from ingest.common.config import DATASET_RAW_LEGISLATIVO, get_settings
from ingest.common.http import get_json, utc_now
from ingest.common.log import get_logger
from ingest.common.writer import NdjsonWriter

log = get_logger("comissoes")

API = "https://dadosabertos.camara.leg.br/api/v2"
PAUSA = 0.35

# A janela pedida ao endpoint. Sem ela, a resposta e' quase vazia (ver o
# cabecalho). 2003 e' onde comeca a serie de atividade legislativa do projeto;
# o fim cobre a legislatura atual inteira.
INICIO = "2003-02-01"
FIM = "2027-01-31"

# Quantos vinculos por pagina, e o teto de paginas. Ver "PAGINAR NAO E'
# OPCIONAL" no cabecalho: 200 numa pagina so' truncava justamente os
# deputados de vinte anos de Casa.
POR_PAGINA = 200
MAX_PAGINAS = 10

# ── CLASSES, DERIVADAS DO CODIGO OFICIAL ──────────────────────────────────
#
# A chave e' `codTipoOrgao` da propria Camara. O rotulo em portugues e' escrito
# AQUI porque o nome oficial do tipo nao e' confiavel (ver o cabecalho).
#
# Contagem do catalogo em 03/09/2026, para dar noção de peso:
#     9 Comissao de Medida Provisoria   1.393 orgaos
#    25 Subcomissao                        64
# 12000 Orgao da Camara                    50
#     2 Comissao Permanente                30
#     3 Comissao Especial                  25
CLASSES: dict[int, tuple[str, str]] = {
    1: ("mesa", "Mesa Diretora"),
    2: ("permanente", "Comissão permanente"),
    3: ("temporaria", "Comissão especial"),
    4: ("temporaria", "Comissão parlamentar de inquérito"),
    5: ("temporaria", "Comissão externa"),
    6: ("mista", "Comissão mista permanente"),
    7: ("temporaria", "Comissão de sindicância"),
    8: ("mista", "Comissão representativa do Congresso"),
    9: ("medida_provisoria", "Comissão de medida provisória"),
    10: ("grupo", "Grupo de trabalho"),
    11: ("conselho", "Conselho"),
    12: ("conselho", "Procuradoria parlamentar"),
    13: ("conselho", "Corregedoria"),
    14: ("conselho", "Ouvidoria"),
    15: ("institucional", "Órgão institucional da Câmara"),
    20: ("mista", "Comissão parlamentar mista de inquérito"),
    21: ("mista", "Comissão mista especial"),
    22: ("outro", "Conferência"),
    25: ("temporaria", "Subcomissão"),
    26: ("outro", "Plenário"),
    27: ("outro", "Plenário"),
    28: ("grupo", "Grupo de trabalho de comissões"),
    200: ("temporaria", "Comissão temporária"),
    12000: ("institucional", "Órgão institucional da Câmara"),
    12500: ("institucional", "Órgão legislativo da Câmara"),
    13000: ("temporaria", "Comissão temporária"),
    21000: ("mista", "Comissão do Senado Federal"),
    81001: ("mista", "Órgão do Congresso Nacional"),
    81002: ("mista", "Comissão mista"),
    81003: ("mista", "Comissão permanente do Senado"),
    81004: ("mista", "Comissão temporária do Senado"),
}

# Filiacao a partido, bloco, lideranca e bancada TAMBEM sao "orgao" na API. Nao
# sao comissao, e misturar as duas coisas na mesma lista seria dizer que estar no
# PT e' o mesmo que ter assento na CCJ. Ficam classificadas, nao descartadas: o
# dado continua no lake para quem quiser outra tela depois.
PARTIDARIAS = {101, 102, 103, 104, 105, 106, 121, 122, 123, 124,
               80000, 81000, 81005, 81009}
for _cod in PARTIDARIAS:
    CLASSES.setdefault(_cod, ("partidaria", "Bancada, bloco ou liderança"))

# As classes que a ficha mostra como assento em colegiado. `medida_provisoria`
# fica de fora da LISTA de propósito — sao 1.393 comissoes de MPV no catalogo, e
# participar delas e' rotina; a ficha conta quantas, sem enumerar.
CLASSES_DE_COLEGIADO = frozenset(
    {"mesa", "permanente", "temporaria", "conselho", "mista"})


@dataclass(frozen=True)
class Vinculo:
    id_deputado: int
    id_orgao: int
    sigla_orgao: str
    nome_orgao: str
    cod_tipo_orgao: int | None
    classe_orgao: str
    tipo_orgao: str
    papel: str
    cod_papel: int | None
    data_inicio: str
    data_fim: str


def _json(url: str) -> dict[str, Any]:
    dados = get_json(url, timeout=60, attempts=3)
    time.sleep(PAUSA)
    return dados


def catalogo_de_orgaos() -> dict[int, dict[str, Any]]:
    """Orgaos da Camara com o tipo, pedindo a janela desde 2003.

    Sem `dataInicio` o endpoint devolve 1.649 — o que esta' vigente. Com, 2.230.
    A diferenca sao comissoes encerradas, e um deputado de 2011 sentou nelas.
    """
    orgaos: dict[int, dict[str, Any]] = {}
    pagina = 1
    while True:
        lote = _json(f"{API}/orgaos?itens=100&pagina={pagina}"
                     f"&dataInicio={INICIO}&dataFim={FIM}").get("dados") or []
        if not lote:
            break
        for o in lote:
            orgaos[o["id"]] = o
        if len(lote) < 100:
            break
        pagina += 1
    log.info("catalogo: %d orgaos em %d paginas", len(orgaos), pagina)
    return orgaos


def _cache_path(settings):
    return settings.staging_dir / "camara_orgaos.json"


def carregar_cache(caminho) -> dict[int, dict[str, Any]]:
    if not caminho.exists():
        return {}
    try:
        bruto = json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {int(k): v for k, v in bruto.items()}


def gravar_cache(caminho, orgaos: dict[int, dict[str, Any]]) -> None:
    caminho.write_text(json.dumps({str(k): v for k, v in orgaos.items()},
                                  ensure_ascii=False), encoding="utf-8")


def resolver_faltantes(ids: set[int], cache: dict[int, dict[str, Any]],
                       ) -> dict[int, dict[str, Any]]:
    """Uma consulta por orgao, so' para o que o catalogo nao trouxe.

    Sao ~5% dos citados, e entre eles a MESA, a PRESIDENCIA e o Conselho de
    Etica. Deixar de resolve-los apagaria da ficha exatamente os assentos de
    maior peso publico.

    Orgao nao muda de tipo, entao o resultado fica em disco: a segunda execucao
    nao pede nenhum de novo.
    """
    novos = 0
    for i, id_orgao in enumerate(sorted(ids), 1):
        if id_orgao in cache:
            continue
        try:
            cache[id_orgao] = _json(f"{API}/orgaos/{id_orgao}").get("dados") or {}
            novos += 1
        except Exception as exc:  # noqa: BLE001
            # Fica de fora, e o vinculo vira `desconhecida` — que a ficha nao
            # mostra. Preferir a linha ausente a' linha errada.
            log.warning("orgao %s: %s", id_orgao, str(exc)[:60])
            cache[id_orgao] = {}
        if i % 200 == 0:
            log.info("%d/%d orgaos resolvidos", i, len(ids))
    log.info("%d orgaos resolvidos individualmente (%d ja' estavam em cache)",
             novos, len(ids) - novos)
    return cache


def _classificar(cod: int | None) -> tuple[str, str]:
    if cod is None:
        # Orgao que o catalogo nao conhece. Nao vira comissao por omissao: a
        # ficha so' mostra `CLASSES_DE_COLEGIADO`, e `desconhecida` nao esta' la'.
        return ("desconhecida", "Órgão não classificado")
    return CLASSES.get(cod, ("outro", "Outro órgão"))


def coletar_brutos(ids: list[int]) -> list[tuple[int, dict[str, Any]]]:
    """Um pedido por deputado, com a janela de datas explicita.

    Devolve os vinculos SEM classificar: o tipo do orgao so' e' conhecido depois
    de resolver o catalogo, e resolver orgao a orgao aqui dentro repetiria a
    mesma consulta para cada deputado que sentou na mesma comissao.
    """
    saida: list[tuple[int, dict[str, Any]]] = []
    truncariam = 0
    for i, id_dep in enumerate(ids, 1):
        pagina, do_deputado = 1, 0
        while True:
            url = (f"{API}/deputados/{id_dep}/orgaos?itens={POR_PAGINA}"
                   f"&pagina={pagina}&dataInicio={INICIO}&dataFim={FIM}")
            try:
                vinculos = _json(url).get("dados") or []
            except Exception as exc:  # noqa: BLE001
                # Um deputado que falhe nao pode derrubar os outros 1.990. A
                # carga segue e a contagem final denuncia o buraco.
                log.warning("deputado %s pagina %s: %s", id_dep, pagina, str(exc)[:70])
                break
            saida.extend((id_dep, v) for v in vinculos)
            do_deputado += len(vinculos)
            if len(vinculos) < POR_PAGINA:
                break
            pagina += 1
            if pagina > MAX_PAGINAS:
                # Guarda contra laco infinito se a API parar de encurtar a
                # ultima pagina. 10 x 200 = 2.000 vinculos, dez vezes o recorde.
                log.warning("deputado %s passou de %d paginas — parando",
                            id_dep, MAX_PAGINAS)
                break
        truncariam += do_deputado > POR_PAGINA
        if i % 100 == 0:
            log.info("%d/%d deputados, %d vinculos", i, len(ids), len(saida))
    if truncariam:
        log.info("%d deputados tem mais de %d vinculos — sem paginacao eles "
                 "sairiam truncados", truncariam, POR_PAGINA)
    return saida


def montar(brutos: list[tuple[int, dict[str, Any]]],
           orgaos: dict[int, dict[str, Any]]) -> list[Vinculo]:
    saida: list[Vinculo] = []
    sem_tipo: set[int] = set()
    for id_dep, v in brutos:
        id_orgao = v.get("idOrgao")
        cod = (orgaos.get(id_orgao) or {}).get("codTipoOrgao")
        if cod is None:
            sem_tipo.add(id_orgao)
        classe, tipo = _classificar(cod)
        saida.append(Vinculo(
            id_deputado=id_dep,
            id_orgao=id_orgao,
            sigla_orgao=(v.get("siglaOrgao") or "").strip(),
            nome_orgao=(v.get("nomeOrgao") or "").strip(),
            cod_tipo_orgao=cod,
            classe_orgao=classe,
            tipo_orgao=tipo,
            papel=(v.get("titulo") or "").strip(),
            cod_papel=v.get("codTitulo"),
            data_inicio=(v.get("dataInicio") or "")[:10],
            data_fim=(v.get("dataFim") or "")[:10],
        ))
    if sem_tipo:
        # Nao e' aviso decorativo: cada um destes e' um assento que some da
        # ficha. Se o numero crescer, alguma coisa mudou na fonte.
        log.warning("%d orgaos continuaram sem tipo — os vinculos deles ficam "
                    "como 'desconhecida' e NAO entram na ficha", len(sem_tipo))
    return saida


def _ids_de_deputado(settings, limite: int | None = None) -> list[int]:
    """Quem o projeto ja' conhece com casamento confiavel.

    Nao e' a lista de quem esta' em exercicio: 1.991 deputados de legislaturas
    desde 2003 tem `id_pessoa` resolvido por CPF, e a comissao de um mandato
    antigo continua sendo fato sobre a pessoa que se candidata hoje.
    """
    from google.cloud import bigquery

    cliente = bigquery.Client(project=settings.project, location=settings.location)
    sql = f"""
        select distinct safe_cast(id_casa as int64) as id
        from `{settings.project}.marts.dim_parlamentar`
        where casa = 'camara' and casamento_confiavel
          and safe_cast(id_casa as int64) is not null
        order by id
        {f'limit {limite}' if limite else ''}
    """
    return [r.id for r in cliente.query(sql).result()]


def _schema():
    """Schema explicito, nunca autodetect (convencao do projeto)."""
    from google.cloud import bigquery

    from ingest.common.bq import build_schema

    textos = ["sigla_orgao", "nome_orgao", "classe_orgao", "tipo_orgao",
              "papel", "data_inicio", "data_fim"]
    schema = build_schema(textos)
    corte = len(textos)
    tipados = [
        bigquery.SchemaField("id_deputado", "INT64"),
        bigquery.SchemaField("id_orgao", "INT64"),
        bigquery.SchemaField("cod_tipo_orgao", "INT64"),
        bigquery.SchemaField("cod_papel", "INT64"),
    ]
    return schema[:corte] + tipados + schema[corte:]


def cmd_load(args: argparse.Namespace) -> int:
    settings = get_settings()
    settings.ensure_dirs()

    ids = _ids_de_deputado(settings, args.limite)
    if not ids:
        log.error("nenhum deputado com casamento confiavel — nada a coletar")
        return 1
    log.info("%d deputados", len(ids))

    orgaos = catalogo_de_orgaos()
    if not orgaos:
        # Sem catalogo, TODO vinculo viraria "desconhecida" e a ficha ficaria
        # sem bloco nenhum. Falhar como transitorio e' melhor que carregar
        # 8 mil linhas inuteis por cima das boas.
        log.error("o catalogo de orgaos veio vazio")
        return 75  # EX_TEMPFAIL

    brutos = coletar_brutos(ids)
    if not brutos:
        log.error("nenhum vinculo coletado")
        return 75

    # O catalogo com janela nao cobre a MESA nem o Conselho de Etica. Resolver o
    # que faltou e' o que impede o assento de maior peso de sumir da ficha.
    caminho = _cache_path(settings)
    cache = carregar_cache(caminho)
    faltantes = {v.get("idOrgao") for _, v in brutos} - set(orgaos)
    faltantes.discard(None)
    if faltantes:
        log.info("%d orgaos fora do catalogo — resolvendo um a um", len(faltantes))
        cache = resolver_faltantes(faltantes, cache)
        gravar_cache(caminho, cache)
    orgaos = {**cache, **orgaos}

    vinculos = montar(brutos, orgaos)

    agora = utc_now()
    destino = settings.staging_dir / "camara_comissoes.ndjson.gz"
    colegiados = 0
    with NdjsonWriter(destino) as w:
        for v in vinculos:
            linha = asdict(v)
            linha["_extracted_at"] = agora
            linha["_source_url"] = API
            w.write(linha)
            colegiados += v.classe_orgao in CLASSES_DE_COLEGIADO
    log.info("%d vinculos (%d em colegiado que a ficha mostra)", w.rows, colegiados)

    if args.target == "local":
        log.info("NDJSON em %s", destino)
        return 0

    from ingest.common.bq import ensure_datasets, load_ndjson

    ensure_datasets(settings)
    load_ndjson(destino, DATASET_RAW_LEGISLATIVO, "camara_comissoes",
                schema=_schema(), clustering=("id_deputado", "classe_orgao"),
                settings=settings)
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Confere a coleta contra a fonte, sem gravar nada.

    Regra 6: a classificacao por codigo e' a parte que nenhum teste automatico
    pega sozinho, porque o dado esta' certo e o ROTULO e' que pode estar errado.
    """
    orgaos = catalogo_de_orgaos()
    por_classe: dict[str, int] = {}
    for o in orgaos.values():
        classe, _ = _classificar(o.get("codTipoOrgao"))
        por_classe[classe] = por_classe.get(classe, 0) + 1
    print("\n  orgaos por classe:")
    for classe, n in sorted(por_classe.items(), key=lambda kv: -kv[1]):
        print(f"    {classe:20s} {n:>6}")

    # "outro" e' destino DELIBERADO para o que nao e' colegiado (Plenario,
    # Conferencia). O que precisa de atencao e' tipo que a Camara passou a
    # publicar e que este mapa ainda nao conhece.
    conhecidos = set(CLASSES)
    novos = sorted({o.get("codTipoOrgao") for o in orgaos.values()
                    if o.get("codTipoOrgao") not in conhecidos
                    and o.get("codTipoOrgao") is not None})
    if novos:
        print(f"\n  TIPOS NAO MAPEADOS: {novos} — investigar e acrescentar a CLASSES")
    else:
        print("\n  todos os tipos do catalogo estao mapeados.")

    desconhecidos = [o for o in orgaos.values()
                     if _classificar(o.get("codTipoOrgao"))[0] == "outro"]
    if desconhecidos:
        print(f"\n  {len(desconhecidos)} orgaos classificados como 'outro' "
              "(nao sao colegiado; fora da ficha de proposito):")
        for o in desconhecidos[:12]:
            print(f"    tipo {o.get('codTipoOrgao')}: {o.get('sigla')} — "
                  f"{str(o.get('nome'))[:56]}")
    print("\n  ATENCAO: `tipoOrgao` da API nao e' confiavel como rotulo. O tipo 15 "
          "chama-se\n  'COORDENADORIA DA MULHER' e agrupa a Bancada Negra, a "
          "Secretaria de\n  Comunicacao e mais onze. Este modulo classifica pelo "
          "CODIGO e escreve o\n  rotulo em portugues em `CLASSES`.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ingest.comissoes", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    load = sub.add_parser("load", help="coleta comissoes da Camara e carrega")
    load.add_argument("--ano", type=int, default=2026,
                      help="aceito por convencao do projeto; nao filtra a coleta")
    load.add_argument("--dry-run", action="store_true")
    load.add_argument("--target", choices=("bq", "local"), default="bq")
    load.add_argument("--limite", type=int,
                      help="coleta so' N deputados — para testar rapido")
    load.set_defaults(func=cmd_load)

    ver = sub.add_parser("verify", help="mostra a classificacao dos orgaos")
    ver.add_argument("--dry-run", action="store_true")
    ver.set_defaults(func=cmd_verify)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return executar(args.func, args)


if __name__ == "__main__":
    sys.exit(main())
