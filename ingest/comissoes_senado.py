"""Comissoes do Senado: onde cada senador sentou, e com que papel — F-29.

    python -m ingest.comissoes_senado load [--dry-run] [--target local]
    python -m ingest.comissoes_senado verify

Fecha a L-28. Espelha `ingest/comissoes.py`, da Camara, e o que muda entre os
dois nao e' capricho da API: e' o que cada Casa publica.

── POR QUE ISTO NAO EXISTIA ──

A L-28 dizia que o bloco "nao teria em quem aparecer", porque nenhum senador tem
`casamento_confiavel` — o Senado nao publica CPF (ADR-014), e a identidade e'
deduzida de nome completo + data de nascimento.

Isso estava errado, e o erro era meu. O projeto JA' exibe atividade legislativa
do Senado com essa mesma identidade deduzida, em 50 fichas de 2026, com a
ressalva escrita na tela. Ao construir as comissoes da Camara eu exigi
`casamento_confiavel` e nunca reconciliei a regua com a que o proprio projeto
usava ao lado.

A regra passa a ser a mesma dos dois lados: entra quem tem `id_pessoa`, e a marca
de COMO a identidade foi resolvida viaja com o dado ate' a tela.

── O TIPO VEM DO CATALOGO OFICIAL, NAO DA SIGLA ──

`/comissao/lista/colegiados` publica 219 colegiados em atividade com
`CodigoTipoColegiado`. E' o equivalente da tabela de tipos da Camara, e vale pelo
mesmo motivo (ADR-034): a sigla engana.

Medido em 05/09/2026, e a distribuicao explica por que classificar importa:

    129 GPAR         Grupo Parlamentar                50   <- NAO e' comissao
    130 FPAR         Frente Parlamentar               47   <- NAO e' comissao
    110 CONS         Conselho                         33
     42 MPV          Comissao de Medida Provisoria    25
     21 PERMANENTE   Comissao Permanente              16
     66 SUBPECOPE    Subcomissao Permanente           13

Quase metade do catalogo e' grupo de amizade parlamentar ("Brasil - Venezuela")
ou frente tematica, a que qualquer parlamentar adere assinando uma lista. Contar
isso como assento em colegiado inflaria a ficha de todo mundo com a mesma coisa,
e a informacao viraria ruido.

── O CATALOGO SO' COBRE O PRESENTE, E O QUE FALTA E' O QUE MAIS IMPORTA ──

O catalogo lista apenas colegiados EM ATIVIDADE. Medido em 05/09/2026: 292
colegiados citados pelos senadores nao estavam nele, e os vinculos deles — 1.483,
21% do total — ficariam sem tipo.

O que ficava de fora era justamente o de maior peso publico:

    CPMI - INSS                      173 vinculos
    Comissao Representativa do CN    110
    CPI do Crime Organizado           40
    CPMI - Fake News                  35
    CPMI - 8 de Janeiro               35
    CPI da Pandemia                   29

E' o mesmo padrao da Camara, onde o catalogo omitia a Mesa, a Presidencia e o
Conselho de Etica (ADR-044). Aceitar a perda apagaria da ficha o assento que mais
diz sobre um mandato.

── E NAO HA' ROTA QUE RESOLVA O PASSADO ──

Ao contrario da Camara, o Senado nao tem detalhe por colegiado que devolva o
tipo: `/comissao/{codigo}` responde vazio, e os parametros de "inativos" da
listagem sao ignorados — a resposta e' byte a byte igual a' dos ativos.

Sobra o NOME OFICIAL, e so' ele. `_classe_por_nome` classifica a partir da forma
oficial completa — "Comissao Parlamentar Mista de Inquerito", "Comissao
Representativa do Congresso Nacional" — e NAO pela sigla, que e' onde mora a
armadilha do ADR-034 (`RQI` parece uma coisa e e' outra).

A distincao viaja com o dado: `origem_da_classe` diz `catalogo` quando o tipo veio
da fonte e `nome` quando foi deduzido daqui. Nome que nao case com nenhuma forma
oficial continua `desconhecida` e NAO entra na ficha — preferir a linha ausente
a' linha errada.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import asdict, dataclass
from typing import Any

from ingest.common.cli import executar
from ingest.common.config import DATASET_RAW_LEGISLATIVO, get_settings
from ingest.common.http import get_json, utc_now
from ingest.common.log import get_logger
from ingest.common.textnorm import strip_accents
from ingest.common.writer import NdjsonWriter

log = get_logger("comissoes_senado")

API = "https://legis.senado.leg.br/dadosabertos"
PAUSA = 0.35

# ── CLASSES, derivadas do `CodigoTipoColegiado` oficial ───────────────────
#
# O rotulo em portugues e' escrito AQUI, uma vez, pelo mesmo motivo do ADR-034:
# o codigo e' confiavel, o texto que vem junto nem sempre.
CLASSES: dict[int, tuple[str, str]] = {
    21: ("permanente", "Comissão permanente"),
    41: ("permanente", "Comissão permanente"),
    22: ("temporaria", "Comissão parlamentar de inquérito"),
    24: ("temporaria", "Comissão temporária interna"),
    121: ("temporaria", "Comissão temporária externa"),
    65: ("temporaria", "Subcomissão temporária"),
    66: ("permanente", "Subcomissão permanente"),
    42: ("medida_provisoria", "Comissão de medida provisória"),
    106: ("conselho", "Órgão da Casa"),
    107: ("conselho", "Conselho"),
    110: ("conselho", "Conselho"),
    109: ("mesa", "Mesa"),
    111: ("mesa", "Mesa"),
    124: ("mista", "Comitê da Comissão Mista de Orçamento"),
    125: ("mista", "Relatoria setorial do Orçamento"),
    # Nao sao assento em colegiado deliberativo.
    129: ("grupo_amizade", "Grupo parlamentar"),
    130: ("frente", "Frente parlamentar"),
    131: ("grupo_amizade", "Órgão de representação internacional"),
    127: ("outro", "Plenário"),
    128: ("outro", "Plenário"),
}

# O que a ficha mostra. `medida_provisoria`, `frente` e `grupo_amizade` ficam de
# fora — ver o cabecalho.
CLASSES_DE_COLEGIADO = frozenset(
    {"permanente", "temporaria", "conselho", "mesa", "mista"})


@dataclass(frozen=True)
class Vinculo:
    codigo_parlamentar: int
    codigo_colegiado: int | None
    sigla_colegiado: str
    nome_colegiado: str
    casa_colegiado: str
    cod_tipo_colegiado: int | None
    classe_colegiado: str
    tipo_colegiado: str
    origem_da_classe: str
    papel: str
    data_inicio: str
    data_fim: str


def _json(url: str) -> dict[str, Any]:
    dados = get_json(url, timeout=60, attempts=3)
    time.sleep(PAUSA)
    return dados


def _lista(no: Any, chave: str) -> list[dict]:
    """A API do Senado devolve dict quando ha' UM item e list quando ha' varios.

    Tratar o dict como lista produz iteracao sobre as CHAVES do dicionario, em
    silencio — o senador com um unico vinculo viraria varias linhas de lixo.
    """
    v = no.get(chave) if isinstance(no, dict) else None
    while isinstance(v, dict) and len(v) == 1:
        v = next(iter(v.values()))
    if isinstance(v, dict):
        return [v]
    return v if isinstance(v, list) else []


def catalogo_de_colegiados() -> dict[int, dict[str, Any]]:
    """Colegiados em atividade, com o tipo oficial. Uma requisicao."""
    d = _json(f"{API}/comissao/lista/colegiados.json")
    col = _lista(d.get("ListaColegiados", {}).get("Colegiados", {}), "Colegiado")
    saida: dict[int, dict[str, Any]] = {}
    for c in col:
        try:
            saida[int(c["Codigo"])] = c
        except (KeyError, TypeError, ValueError):
            continue
    log.info("catalogo: %d colegiados em atividade", len(saida))
    return saida


# Formas OFICIAIS completas, na ordem em que sao testadas. A primeira que casar
# vence, e por isso a ordem importa: "Comissao Parlamentar Mista de Inquerito"
# precisa ser testada antes de "Comissao Mista".
#
# So' entram formas que a propria Casa usa por extenso. Sigla NAO e' usada — e'
# ali que mora a armadilha do ADR-034.
POR_NOME: tuple[tuple[str, tuple[str, str]], ...] = (
    ("COMISSAO PARLAMENTAR MISTA DE INQUERITO",
     ("temporaria", "Comissão parlamentar mista de inquérito")),
    ("COMISSAO PARLAMENTAR DE INQUERITO",
     ("temporaria", "Comissão parlamentar de inquérito")),
    ("COMISSAO REPRESENTATIVA DO CONGRESSO",
     ("mista", "Comissão representativa do Congresso")),
    ("COMISSAO DE MEDIDA PROVISORIA",
     ("medida_provisoria", "Comissão de medida provisória")),
    ("COMISSAO MISTA", ("mista", "Comissão mista")),
    ("SUBCOMISSAO PERMANENTE", ("permanente", "Subcomissão permanente")),
    ("SUBCOMISSAO", ("temporaria", "Subcomissão temporária")),
    ("COMISSAO TEMPORARIA", ("temporaria", "Comissão temporária")),
    ("COMISSAO ESPECIAL", ("temporaria", "Comissão especial")),
    ("COMISSAO PERMANENTE", ("permanente", "Comissão permanente")),
    ("CONSELHO", ("conselho", "Conselho")),
    ("CORREGEDORIA", ("conselho", "Corregedoria")),
    ("OUVIDORIA", ("conselho", "Ouvidoria")),
    ("PROCURADORIA", ("conselho", "Procuradoria")),
    ("GRUPO PARLAMENTAR", ("grupo_amizade", "Grupo parlamentar")),
    ("FRENTE PARLAMENTAR", ("frente", "Frente parlamentar")),
    ("MESA DO CONGRESSO", ("mesa", "Mesa")),
    ("MESA DIRETORA", ("mesa", "Mesa")),
)


# A API usa ora a forma extensa ("Comissao Parlamentar Mista de Inquerito - Fake
# News"), ora a abreviada ("CPI da Pandemia"). Estas sao testadas no INICIO do
# nome, onde a abreviacao oficial nao e' ambigua — diferente de procurar a sigla
# solta em qualquer posicao, que e' o que o ADR-034 proibe.
POR_PREFIXO: tuple[tuple[str, tuple[str, str]], ...] = (
    ("CPMI", ("temporaria", "Comissão parlamentar mista de inquérito")),
    ("CPI", ("temporaria", "Comissão parlamentar de inquérito")),
)


def _classe_por_nome(nome: str | None) -> tuple[str, str] | None:
    """Ultimo recurso para colegiado que o catalogo nao conhece.

    Trabalha sobre o nome OFICIAL por extenso, nunca sobre a sigla. Nome que nao
    case com nenhuma forma oficial devolve None, e o vinculo fica `desconhecida`.
    """
    if not nome:
        return None
    alvo = strip_accents(nome).upper().strip()
    for forma, classe in POR_NOME:
        if forma in alvo:
            return classe
    for prefixo, classe in POR_PREFIXO:
        # `startswith` e nao `in`: "CPI" solto no meio de um nome nao diz nada,
        # mas um nome que COMECA com "CPI " e' inequivoco.
        if alvo.startswith(prefixo + " ") or alvo.startswith(prefixo + "-"):
            return classe
    return None


def _classificar(cod: int | None, nome: str | None = None) -> tuple[str, str, str]:
    """Devolve (classe, rotulo, origem). `origem` distingue fonte de deducao."""
    if cod is not None:
        classe, rotulo = CLASSES.get(cod, ("outro", "Outro colegiado"))
        return (classe, rotulo, "catalogo")
    deduzido = _classe_por_nome(nome)
    if deduzido:
        return (*deduzido, "nome")
    return ("desconhecida", "Colegiado não classificado", "nenhuma")


def codigos_de_senador(settings) -> list[int]:
    """Quem o projeto conhece — os senadores em exercicio ja' resolvidos."""
    from google.cloud import bigquery

    cliente = bigquery.Client(project=settings.project, location=settings.location)
    sql = f"""
        select distinct safe_cast(id_casa as int64) as id
        from `{settings.project}.marts.dim_parlamentar`
        where casa = 'senado' and safe_cast(id_casa as int64) is not null
        order by id
    """
    return [r.id for r in cliente.query(sql).result()]


def coletar(codigos: list[int], colegiados: dict[int, dict]) -> list[Vinculo]:
    saida: list[Vinculo] = []
    sem_tipo: set[int] = set()
    por_nome = 0
    for i, cod in enumerate(codigos, 1):
        try:
            d = _json(f"{API}/senador/{cod}/comissoes.json")
        except Exception as exc:  # noqa: BLE001
            log.warning("senador %s: %s", cod, str(exc)[:70])
            continue
        par = d.get("MembroComissaoParlamentar", {}).get("Parlamentar", {})
        for v in _lista(par, "MembroComissoes"):
            ident = v.get("IdentificacaoComissao") or {}
            try:
                id_col = int(ident.get("CodigoComissao"))
            except (TypeError, ValueError):
                id_col = None
            tipo = (colegiados.get(id_col) or {}).get("CodigoTipoColegiado")
            try:
                tipo = int(tipo) if tipo is not None else None
            except (TypeError, ValueError):
                tipo = None
            nome = (ident.get("NomeComissao") or "").strip()
            classe, rotulo, origem = _classificar(tipo, nome)
            if tipo is None:
                sem_tipo.add(id_col)
                if origem == "nome":
                    por_nome += 1
            saida.append(Vinculo(
                codigo_parlamentar=cod,
                codigo_colegiado=id_col,
                sigla_colegiado=(ident.get("SiglaComissao") or "").strip(),
                nome_colegiado=nome,
                casa_colegiado=(ident.get("SiglaCasaComissao") or "").strip(),
                cod_tipo_colegiado=tipo,
                classe_colegiado=classe,
                tipo_colegiado=rotulo,
                origem_da_classe=origem,
                papel=(v.get("DescricaoParticipacao") or "").strip(),
                data_inicio=(v.get("DataInicio") or "")[:10],
                data_fim=(v.get("DataFim") or "")[:10],
            ))
        if i % 20 == 0:
            log.info("%d/%d senadores, %d vinculos", i, len(codigos), len(saida))
    if sem_tipo:
        log.info("%d colegiados fora do catalogo; %d vinculos deles foram "
                 "classificados pelo NOME oficial", len(sem_tipo), por_nome)
    restam = sum(1 for v in saida if v.classe_colegiado == "desconhecida")
    if restam:
        # Cada um destes e' um assento que NAO aparece na ficha.
        log.warning("%d vinculos continuaram sem classe e NAO entram na ficha",
                    restam)
    return saida


def _schema():
    """Schema explicito, nunca autodetect (convencao do projeto)."""
    from google.cloud import bigquery

    from ingest.common.bq import build_schema

    textos = ["sigla_colegiado", "nome_colegiado", "casa_colegiado",
              "classe_colegiado", "tipo_colegiado", "origem_da_classe", "papel",
              "data_inicio", "data_fim"]
    schema = build_schema(textos)
    corte = len(textos)
    tipados = [
        bigquery.SchemaField("codigo_parlamentar", "INT64"),
        bigquery.SchemaField("codigo_colegiado", "INT64"),
        bigquery.SchemaField("cod_tipo_colegiado", "INT64"),
    ]
    return schema[:corte] + tipados + schema[corte:]


def cmd_load(args: argparse.Namespace) -> int:
    settings = get_settings()
    settings.ensure_dirs()

    codigos = codigos_de_senador(settings)
    if not codigos:
        log.error("nenhum senador em dim_parlamentar — rode ingest.legislativo antes")
        return 1
    log.info("%d senadores", len(codigos))

    colegiados = catalogo_de_colegiados()
    if not colegiados:
        # Sem catalogo TODO vinculo vira 'desconhecida' e a ficha sai sem bloco.
        log.error("o catalogo de colegiados veio vazio")
        return 75  # EX_TEMPFAIL

    vinculos = coletar(codigos, colegiados)
    if not vinculos:
        log.error("nenhum vinculo coletado")
        return 75

    agora = utc_now()
    destino = settings.staging_dir / "senado_comissoes.ndjson.gz"
    colegiado = 0
    with NdjsonWriter(destino) as w:
        for v in vinculos:
            linha = asdict(v)
            linha["_extracted_at"] = agora
            linha["_source_url"] = API
            w.write(linha)
            colegiado += v.classe_colegiado in CLASSES_DE_COLEGIADO
    log.info("%d vinculos (%d em colegiado que a ficha mostra)", w.rows, colegiado)

    if args.target == "local":
        log.info("NDJSON em %s", destino)
        return 0

    from ingest.common.bq import ensure_datasets, load_ndjson

    ensure_datasets(settings)
    load_ndjson(destino, DATASET_RAW_LEGISLATIVO, "senado_comissoes",
                schema=_schema(),
                clustering=("codigo_parlamentar", "classe_colegiado"),
                settings=settings)
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Mostra a classificacao do catalogo, sem gravar nada (Regra 6)."""
    col = catalogo_de_colegiados()
    por_classe: dict[str, int] = {}
    for c in col.values():
        try:
            cod = int(c.get("CodigoTipoColegiado"))
        except (TypeError, ValueError):
            cod = None
        classe, _, _ = _classificar(cod)
        por_classe[classe] = por_classe.get(classe, 0) + 1

    print("\n  colegiados por classe:")
    for classe, n in sorted(por_classe.items(), key=lambda kv: -kv[1]):
        marca = "  (na ficha)" if classe in CLASSES_DE_COLEGIADO else ""
        print(f"    {classe:20s} {n:>5}{marca}")

    novos = sorted({int(c["CodigoTipoColegiado"]) for c in col.values()
                    if str(c.get("CodigoTipoColegiado", "")).isdigit()
                    and int(c["CodigoTipoColegiado"]) not in CLASSES})
    if novos:
        print(f"\n  TIPOS NAO MAPEADOS: {novos} — investigar e acrescentar a CLASSES")
    else:
        print("\n  todos os tipos do catalogo estao mapeados.")

    print("\n  ATENCAO: quase metade do catalogo e' grupo de amizade parlamentar "
          "ou frente\n  tematica. Nenhum dos dois e' assento em colegiado "
          "deliberativo, e contar\n  os dois inflaria a ficha de todo mundo com a "
          "mesma coisa.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ingest.comissoes_senado", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    load = sub.add_parser("load", help="coleta comissoes do Senado e carrega")
    load.add_argument("--ano", type=int, default=2026,
                      help="aceito por convencao do projeto; nao filtra a coleta")
    load.add_argument("--dry-run", action="store_true")
    load.add_argument("--target", choices=("bq", "local"), default="bq")
    load.set_defaults(func=cmd_load)

    ver = sub.add_parser("verify", help="mostra a classificacao dos colegiados")
    ver.add_argument("--dry-run", action="store_true")
    ver.set_defaults(func=cmd_verify)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return executar(args.func, args)


if __name__ == "__main__":
    sys.exit(main())
