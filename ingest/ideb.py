"""Ingestao do IDEB — S8 / F-04.

    python -m ingest.ideb load   [--dry-run] [--target local]
    python -m ingest.ideb verify

O IDEB e' a serie com MELHOR encaixe em janela de mandato de todo o projeto:
bienal desde 2005, por UF, num tema em que o estado tem competencia direta. Onze
edicoes ate' 2025 — um mandato de governador contem duas ou tres medicoes, contra
uma unica do IDHM em trinta anos.

DUAS COISAS PRECISARAM SER RESOLVIDAS ANTES (ver L-05, ADR-016)

1. TLS. `download.inep.gov.br` serve o certificado da folha SEM o intermediario
   "RNP ICPEdu GR46 OV TLS CA 2025". O navegador busca o elo sozinho pela extensao
   AIA; o Python nao. O intermediario esta' versionado em `certs/` e o
   `ingest/common/http.py` o injeta so' para esse host. Nao e' CA desconhecida —
   a raiz (GlobalSign Root R46) sempre esteve na loja do sistema.

2. URLs. A pagina de resultados do INEP monta os links por JavaScript, e adivinhar
   nome de arquivo nao funcionou (seis padroes, seis 404). Os links reais estao no
   endpoint que a aba carrega, declarado em `data-url` no proprio HTML:
   `.../ideb/resultados/2005-2025`. `verify` refaz essa descoberta, para o dia em
   que o INEP mudar o nome do arquivo.

O QUE E' INGERIDO

Uma linha por (UF, ano) da aba e da rede que o CATALOGO declarar. Hoje o catalogo
pede anos finais do ensino fundamental na rede publica, que e' o que o SPEC 3 (S8)
especifica. As outras duas abas (anos iniciais e ensino medio) sao lidas pelo mesmo
codigo e so' esperam uma entrada no catalogo — em especial o ENSINO MEDIO, que e'
majoritariamente estadual e portanto o mais proximo da responsabilidade de um
governador. Ver SPEC 11.

Conferido em 28/08/2026.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from ingest.common.cli import executar
from ingest.common.config import DATASET_RAW_INEP, get_settings
from ingest.common.http import download, get_texto, utc_now
from ingest.common.indicadores import (
    COLUNAS_NUMERICAS,
    COLUNAS_SAIDA,
    Indicador,
    Observacao,
    por_provedor,
)
from ingest.common.log import get_logger
from ingest.common.planilha import Planilha, abrir
from ingest.common.textnorm import strip_accents
from ingest.common.ufs import UFS
from ingest.common.writer import NdjsonWriter

log = get_logger("ideb")

BASE = "https://download.inep.gov.br/ideb/resultados"

# A pagina de resultados nao tem link nenhum no HTML: o conteudo vem de um
# endpoint declarado em `data-url`. E' de la' que saem os nomes de arquivo.
PAGINA_ABA = (
    "https://www.gov.br/inep/pt-br/areas-de-atuacao/pesquisas-estatisticas-e-"
    "indicadores/ideb/resultados/2005-2025"
)

ARQUIVO_UFS = "divulgacao_regioes_ufs_ideb_2025.zip"
ARQUIVO_BRASIL = "divulgacao_brasil_ideb_2025.zip"

FONTE = "INEP — IDEB (planilhas de divulgacao)"

# A planilha abrevia. "R. G. do Norte" nao casa com "Rio Grande do Norte" por
# normalizacao nenhuma — precisa de tabela. Qualquer territorio que nao resolva
# FALHA ALTO: um estado silenciosamente ausente e' pior que um erro.
APELIDOS = {
    "R. G. DO NORTE": "RN",
    "R. G. DO SUL": "RS",
    "M. G. DO SUL": "MS",
}

# Regioes e cabecalhos aparecem na mesma coluna das UFs e sao descartados: o grao
# do projeto e' UF e Brasil, e `fct_indicador_uf_ano` ja' calcula o comparador
# regional a partir das UFs.
IGNORAR = {
    "NORTE", "NORDESTE", "SUDESTE", "SUL", "CENTRO-OESTE",
    "REGIAO/ UNIDADE DA FEDERACAO", "REGIAO/UNIDADE DA FEDERACAO", "BRASIL",
}

_NOTA = re.compile(r"\s*\(\d+\)")          # "Publica (4)" -> "Publica"
_COL = re.compile(r"([A-Z]+)")
_ANO_OBSERVADO = re.compile(r"^VL_OBSERVADO_(\d{4})$")
# Estreito de proposito: "METAS DO 1O CICLO..." na mesma linha nao pode casar.
_IDEB_HUMANO = re.compile(r"^IDEB (\d{4})1? \(N X P\)$")

_POR_NOME = {strip_accents(u.nome).upper(): u.sg_uf for u in UFS}


def _rotulo(texto: Any) -> str:
    """Sem acento, sem nota de rodape, sem quebra de linha, maiusculo."""
    limpo = _NOTA.sub("", str(texto or "").replace("\n", " "))
    return re.sub(r"\s+", " ", strip_accents(limpo)).strip().upper()


def sigla_de(nome: str) -> str | None:
    rot = _rotulo(nome)
    if rot in IGNORAR:
        return None
    return APELIDOS.get(rot) or _POR_NOME.get(rot)


def _linha_de_codigos(pl: Planilha, origem: str = "") -> tuple[int, dict[str, int]]:
    """Acha a linha com os codigos `VL_OBSERVADO_{ano}` e mapeia coluna -> ano.

    A linha e' PROCURADA, nao fixada num numero: o INEP mexe no cabecalho de
    decoracao entre edicoes, e uma linha hardcoded quebraria em silencio.

    E ha' um defeito na propria fonte que precisa de remendo. Em
    `divulgacao_brasil_ideb_2025.zip`, a coluna do IDEB 2023 ficou SEM o codigo de
    maquina — o dado esta' la' (Brasil, rede publica, 2023 = 4,7), mas a celula de
    codigo veio vazia. So' pelo codigo, o Brasil perderia 2023 e o comparador
    daquele ano sumiria de 27 estados. O arquivo das UFs nao tem o defeito.

    O remendo le' o cabecalho HUMANO ("IDEB 2023 (N x P)") apenas para as colunas
    que ficaram sem codigo, e casa com um padrao estreito de proposito: na mesma
    linha existe "Metas do 1o ciclo do Ideb (2007-2021)", e um padrao frouxo traria
    META como se fosse resultado observado — que e' exatamente o que a Constituicao
    0.1 proibe exibir.
    """
    for n, celulas in sorted(pl.linhas.items()):
        anos = {}
        for coluna, texto in celulas.items():
            m = _ANO_OBSERVADO.match(texto.strip().upper())
            if m:
                anos[coluna] = int(m.group(1))
        if not anos:
            continue
        humanos = pl.linhas.get(n - 3, {})
        for coluna, texto in humanos.items():
            if coluna in anos:
                continue
            m = _IDEB_HUMANO.match(_rotulo(texto))
            if m:
                anos[coluna] = int(m.group(1))
                log.warning(
                    "%s: coluna %s sem VL_OBSERVADO na fonte; ano %s recuperado do "
                    "cabecalho \"%s\" (defeito da planilha do INEP)",
                    origem or "planilha",
                    coluna,
                    m.group(1),
                    _rotulo(texto),
                )
        return n, anos
    raise ValueError("nenhuma coluna VL_OBSERVADO encontrada na aba")


def extrair(
    caminho: Path, ind: Indicador, extraido_em: str, *, so_brasil: bool = False
) -> list[Observacao]:
    chave_aba = "aba_brasil" if so_brasil else "aba"
    aba_pedida = _rotulo(ind.parametros[chave_aba])
    rede_pedida = _rotulo(ind.parametros["rede"])

    abas = abrir(caminho, normalizar=_rotulo)
    if aba_pedida not in abas:
        raise ValueError(
            f"aba {ind.parametros[chave_aba]!r} nao existe em {caminho.name}. "
            f"Abas disponiveis: {sorted(abas)}"
        )
    pl = abas[aba_pedida]
    linha_codigos, anos_por_coluna = _linha_de_codigos(pl, caminho.name)

    obs: list[Observacao] = []
    nao_resolvidos: list[str] = []
    for n, celulas in sorted(pl.linhas.items()):
        if n <= linha_codigos:
            continue
        nome, rede = celulas.get("A", ""), celulas.get("B", "")
        if not nome or not rede:
            continue
        if _rotulo(rede) != rede_pedida:
            continue

        if so_brasil:
            if _rotulo(nome) != "BRASIL":
                continue
            sigla = "BR"
        else:
            sigla = sigla_de(nome)
            if sigla is None:
                if _rotulo(nome) not in IGNORAR:
                    nao_resolvidos.append(nome)
                continue

        for coluna, ano in anos_por_coluna.items():
            bruto = (celulas.get(coluna) or "").strip()
            if not bruto:
                continue
            try:
                valor = float(bruto)
            except ValueError:
                continue  # "-" e afins: edicao sem divulgacao para aquele ente
            obs.append(
                Observacao(
                    cod_indicador=ind.cod_indicador,
                    sg_uf=sigla,
                    ano=ano,
                    valor=valor,
                    unidade=ind.unidade,
                    fonte=FONTE,
                    extracted_at=extraido_em,
                    source_url=f"{BASE}/{caminho.name}",
                )
            )

    if nao_resolvidos:
        # Falha alto: um estado que some sem aviso vira uma ficha de governador
        # sem indicador nenhum, e ninguem repara.
        raise ValueError(
            "territorios nao resolvidos em "
            f"{caminho.name}: {sorted(set(nao_resolvidos))}. "
            "Acrescente o apelido em APELIDOS ou o nome em IGNORAR."
        )
    return obs


def coletar(*, force: bool = False) -> list[Observacao]:
    settings = get_settings()
    destino = settings.download_dir / "inep"
    destino.mkdir(parents=True, exist_ok=True)
    extraido_em = utc_now()

    ufs = download(f"{BASE}/{ARQUIVO_UFS}", destino / ARQUIVO_UFS, force=force).path
    br = download(f"{BASE}/{ARQUIVO_BRASIL}", destino / ARQUIVO_BRASIL, force=force).path

    obs: list[Observacao] = []
    for ind in por_provedor("inep"):
        se_uf = extrair(Path(ufs), ind, extraido_em)
        se_br = extrair(Path(br), ind, extraido_em, so_brasil=True)
        log.info(
            "%s: %d observacoes de UF + %d do Brasil",
            ind.cod_indicador,
            len(se_uf),
            len(se_br),
        )
        obs.extend(se_uf)
        obs.extend(se_br)
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
        for nome in (ARQUIVO_UFS, ARQUIVO_BRASIL):
            log.info("[dry-run] baixaria %s/%s", BASE, nome)
        return 0

    obs = coletar(force=args.force)
    if not obs:
        log.error("nenhuma observacao coletada — a carga nao substitui a tabela por vazio")
        return 1

    destino = settings.staging_dir / "indicadores" / "inep.ndjson.gz"
    with NdjsonWriter(destino) as writer:
        for o in obs:
            writer.write(o.to_row())

    anos = sorted({o.ano for o in obs})
    log.info(
        "%d observacoes | %d..%d | %d unidades",
        len(obs),
        anos[0],
        anos[-1],
        len({o.sg_uf for o in obs}),
    )

    if args.target == "local":
        log.info("NDJSON em %s", destino)
        return 0

    from ingest.common.bq import ensure_datasets, load_ndjson

    ensure_datasets()
    load_ndjson(
        destino,
        DATASET_RAW_INEP,
        "indicadores",
        schema=_schema(),
        particionar_por="ano",
        clustering=("cod_indicador", "sg_uf"),
    )
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Refaz a descoberta das URLs e mostra o que sai da planilha.

    A descoberta esta' aqui, e nao na carga, de proposito: a carga usa nomes de
    arquivo fixos, porque baixar um arquivo diferente a cada execucao silenciosa
    seria pior que falhar. Quando o INEP publicar a edicao de 2027, este comando
    mostra o nome novo e o catalogo e' atualizado a mao.
    """
    print(f"descobrindo links em {PAGINA_ABA}\n")
    html = get_texto(PAGINA_ABA, timeout=90)
    links = sorted(set(re.findall(r"https?://download\.inep\.gov\.br[^\s\"<>)]+", html)))
    print(f"{len(links)} links no endpoint da aba:")
    for x in links:
        marca = "  <= em uso" if x.rsplit("/", 1)[-1] in (ARQUIVO_UFS, ARQUIVO_BRASIL) else ""
        print(f"   {x}{marca}")

    faltando = [n for n in (ARQUIVO_UFS, ARQUIVO_BRASIL) if not any(x.endswith(n) for x in links)]
    if faltando:
        print(f"\nATENCAO: {faltando} nao aparece mais na pagina — o INEP renomeou.")
        return 1

    obs = coletar()
    print(f"\n{len(obs)} observacoes\n")
    por_ind: dict[str, list[Observacao]] = {}
    for o in obs:
        por_ind.setdefault(o.cod_indicador, []).append(o)
    for cod, lista in sorted(por_ind.items()):
        anos = sorted({o.ano for o in lista})
        print(f"{cod}: {len(lista)} obs | {len(anos)} edicoes {anos[0]}..{anos[-1]} "
              f"| {len({o.sg_uf for o in lista})} unidades")
        amostra = {(o.sg_uf, o.ano): o.valor for o in lista}
        for uf in ("BR", "SP", "CE", "MA"):
            serie = [f"{a}:{amostra[(uf, a)]:.1f}" for a in anos if (uf, a) in amostra]
            print(f"   {uf}: {' '.join(serie)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ingest.ideb", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_load = sub.add_parser("load", help="baixa as planilhas do IDEB e carrega")
    p_load.add_argument("--ano", type=int, help="aceito por convencao do SPEC 9; nao filtra")
    p_load.add_argument("--force", action="store_true", help="rebaixa mesmo com cache valido")
    p_load.add_argument("--dry-run", action="store_true")
    p_load.add_argument("--target", choices=("bigquery", "local"), default="bigquery")
    p_load.set_defaults(func=cmd_load)

    p_ver = sub.add_parser("verify", help="redescobre as URLs e mostra a serie")
    p_ver.set_defaults(func=cmd_verify)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return executar(args.func, args)


if __name__ == "__main__":
    sys.exit(main())
