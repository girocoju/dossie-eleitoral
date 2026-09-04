"""Emendas parlamentares: quanto cada autor moveu, e para onde — F-27.

    python -m ingest.emendas load [--ano 2025] [--dry-run] [--target local]
    python -m ingest.emendas verify

Fonte: Portal da Transparencia (CGU), download em lote. NAO e' a API — a API
exige chave cadastrada; o arquivo em bloco nao exige nada.

    https://portaldatransparencia.gov.br/download-de-dados/emendas-parlamentares/{ano}

Cuidado com o endereco: `download-de-dados/emendas` (sem o `-parlamentares`)
existe, responde HTTP 500 e nao e' isto.

── O ANO NA URL E' IGNORADO PELO PORTAL. E' UM ARQUIVO SO'. ──

`/emendas-parlamentares/2014` e `/emendas-parlamentares/2026` devolvem o MESMO
arquivo, byte a byte. Conferido em 04/09/2026, baixando os treze anos:

    13 downloads · 32.328.954 bytes cada · 1 sha256 distinto

A primeira versao deste modulo baixava um por ano e carregava os treze. Como
cada um tinha 94.463 linhas, o resultado era 1.228.019 — treze copias da mesma
coisa. Nenhum erro apareceria: a carga terminaria verde, e toda soma por autor
sairia multiplicada por treze.

O que denunciou foi a contagem IDENTICA em todos os anos. Numero que se repete
exato treze vezes nao e' coincidencia.

O arquivo e' CUMULATIVO: 94.463 linhas, uma por (emenda, destino), cobrindo
emendas de 2014 a 2026, com o valor JA' acumulado de empenho, liquidacao e
pagamento. O ano de verdade e' a coluna `Ano da Emenda`:

    2014  11.155 linhas   R$  0,13 bi pagos
    2020   8.621 linhas   R$ 17,63 bi pagos
    2025   6.311 linhas   R$ 32,48 bi pagos
    2026   5.469 linhas   R$ 25,69 bi pagos

Isso ELIMINA o risco de dupla contagem que existiria se fossem arquivos por
exercicio: nao ha' o que somar entre arquivos, porque ha' um arquivo so'.

A tela mostra empenhado E pago, separados, porque a diferenca e' o fato.

── 17% DAS LINHAS NAO TEM AUTOR, E ISSO E' A NOTICIA ──

Medido em 04/09/2026 sobre as 94.463 linhas do arquivo de 2025:

    Sem informacao                15.962 linhas   (17%)
    RELATOR GERAL                  2.179 linhas
    BANCADA DO <ESTADO>, comissoes  2.466 linhas
    autores individuais           73.856 linhas   (78%)

As 15.962 sem autor sao o orcamento cuja autoria o proprio Portal nao publica.
Nao e' falha do pipeline e nao pode ser preenchida — vira a L-29, e a tela diz
que existe. Um bloco de emendas que nao diga isso sugere que a lista esta'
completa.

── O CASAMENTO E' POR NOME PARLAMENTAR, E O NOME AMBIGUO FICA DE FORA ──

O Portal publica `Nome do Autor da Emenda` no mesmo formato de `nome_parlamentar`
("ACIR GURGACZ", "JANDIRA FEGHALI") e um `Codigo do Autor` que e' do sistema
dele, sem relacao com o id da Camara nem com CPF.

Medido sobre os 1.544 autores individuais de 2025:

    nome unico            1.302 autores ·  68.366 linhas   (93%)
    nome AMBIGUO              7 autores ·     369 linhas   ( 0%)
    sem correspondencia     235 autores ·   5.121 linhas

Os sete ambiguos sao homonimia de verdade — RICARDO IZAR (pai e filho, os dois
deputados), ATILA LIRA, JOAO CARLOS BACELAR, BEBETO. Atribuir milhoes de reais a
pessoa errada e' o pior erro possivel nesta tela, entao nome ambiguo NAO entra em
ficha nenhuma.

O casamento sai deste modulo com a marca: `casamento` diz se foi `nome_unico` ou
`ambiguo`, e o mart so' promove o primeiro.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import zipfile
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path

from ingest.common.cli import executar
from ingest.common.config import DATASET_RAW_TESOURO, get_settings
from ingest.common.http import download, utc_now
from ingest.common.log import get_logger
from ingest.common.textnorm import strip_accents
from ingest.common.writer import NdjsonWriter

log = get_logger("emendas")

BASE = "https://portaldatransparencia.gov.br/download-de-dados/emendas-parlamentares"

# O ano no endereco NAO filtra nada — ver o cabecalho. Qualquer um serve, e o
# arquivo que volta e' o mesmo. Fica 2025 por ser um ano que existe; usar o ano
# corrente faria o nome do arquivo em disco mudar todo 1o de janeiro sem que o
# conteudo mudasse.
ANO_NA_URL = 2025

# Autor que nao e' pessoa. A comparacao e' feita no nome JA' normalizado.
COLETIVOS = ("RELATOR", "COMISSAO", "BANCADA", "SEM INFORMA", "MESA DIRETORA")

# Colunas do CSV que interessam. Declaradas para falhar alto se o Portal mudar o
# cabecalho, em vez de gravar coluna vazia em silencio.
COLUNAS = {
    "codigo": "Código da Emenda",
    "ano": "Ano da Emenda",
    "tipo": "Tipo de Emenda",
    "cod_autor": "Código do Autor da Emenda",
    "autor": "Nome do Autor da Emenda",
    "numero": "Número da emenda",
    "municipio": "Município",
    "cod_municipio": "Código Município IBGE",
    "uf": "UF",
    "funcao": "Nome Função",
    "subfuncao": "Nome Subfunção",
    "programa": "Nome Programa",
    "acao": "Nome Ação",
    "empenhado": "Valor Empenhado",
    "liquidado": "Valor Liquidado",
    "pago": "Valor Pago",
    "restos_pagos": "Valor Restos A Pagar Pagos",
}


@dataclass(frozen=True)
class Emenda:
    ano_emenda: int | None
    codigo: str
    numero: str
    tipo: str
    autor: str
    autor_normalizado: str
    autor_e_pessoa: bool
    cod_autor: str
    uf: str
    municipio: str
    cod_municipio: str
    funcao: str
    subfuncao: str
    programa: str
    acao: str
    vl_empenhado: float
    vl_liquidado: float
    vl_pago: float
    vl_restos_pagos: float


def normalizar(valor: object) -> str:
    return " ".join(strip_accents(str(valor or "")).upper().split())


def e_pessoa(nome_normalizado: str) -> bool:
    """Autor coletivo ou institucional nao e' pessoa.

    `RELATOR GERAL` move bilhoes e nao e' de ninguem em particular; bancada e
    comissao sao assinatura de grupo. Nenhum dos tres pode ir para a ficha de um
    candidato — seria atribuir a uma pessoa o que a fonte atribui a um colegiado.
    """
    if not nome_normalizado:
        return False
    return not any(p in nome_normalizado for p in COLETIVOS)


def numero(valor: object) -> float:
    """`1.234.567,89` -> 1234567.89. Vazio e lixo viram 0,0."""
    texto = str(valor or "").strip()
    if not texto:
        return 0.0
    try:
        return float(texto.replace(".", "").replace(",", "."))
    except ValueError:
        return 0.0


def inteiro(valor: object) -> int | None:
    texto = str(valor or "").strip()
    return int(texto) if texto.isdigit() else None


def baixar(settings, *, force: bool = False, dry_run: bool = False) -> Path:
    """O arquivo unico. Nome sem ano no disco, porque ele nao tem ano."""
    destino = settings.download_dir / "emendas"
    art = download(f"{BASE}/{ANO_NA_URL}", destino / "emendas.zip",
                   force=force, dry_run=dry_run)
    return Path(art.path)


def ler(caminho: Path) -> list[Emenda]:
    z = zipfile.ZipFile(caminho)
    nome = next((n for n in z.namelist() if n.lower().endswith(".csv")), None)
    if nome is None:
        raise ValueError(f"{caminho} nao tem CSV dentro")

    # `latin-1` e' o que o Portal publica. Ler como UTF-8 estoura em "Função".
    bruto = z.read(nome).decode("latin-1")
    leitor = csv.DictReader(io.StringIO(bruto), delimiter=";")
    faltando = [c for c in COLUNAS.values() if c not in (leitor.fieldnames or [])]
    if faltando:
        # Falhar alto. Coluna que sumiu e vira campo vazio produz uma tela que
        # diz "R$ 0" para quem moveu milhoes.
        raise ValueError(
            f"o arquivo de emendas nao tem as colunas {faltando}. "
            f"O Portal mudou o layout — confira antes de carregar.")

    saida: list[Emenda] = []
    for linha in leitor:
        autor = (linha[COLUNAS["autor"]] or "").strip()
        norm = normalizar(autor)
        saida.append(Emenda(
            ano_emenda=inteiro(linha[COLUNAS["ano"]]),
            codigo=(linha[COLUNAS["codigo"]] or "").strip(),
            numero=(linha[COLUNAS["numero"]] or "").strip(),
            tipo=(linha[COLUNAS["tipo"]] or "").strip(),
            autor=autor,
            autor_normalizado=norm,
            autor_e_pessoa=e_pessoa(norm),
            cod_autor=(linha[COLUNAS["cod_autor"]] or "").strip(),
            uf=(linha[COLUNAS["uf"]] or "").strip(),
            municipio=(linha[COLUNAS["municipio"]] or "").strip(),
            cod_municipio=(linha[COLUNAS["cod_municipio"]] or "").strip(),
            funcao=(linha[COLUNAS["funcao"]] or "").strip(),
            subfuncao=(linha[COLUNAS["subfuncao"]] or "").strip(),
            programa=(linha[COLUNAS["programa"]] or "").strip(),
            acao=(linha[COLUNAS["acao"]] or "").strip(),
            vl_empenhado=numero(linha[COLUNAS["empenhado"]]),
            vl_liquidado=numero(linha[COLUNAS["liquidado"]]),
            vl_pago=numero(linha[COLUNAS["pago"]]),
            vl_restos_pagos=numero(linha[COLUNAS["restos_pagos"]]),
        ))
    return saida


def _schema():
    """Schema explicito, nunca autodetect (convencao do projeto)."""
    from google.cloud import bigquery

    from ingest.common.bq import build_schema

    textos = ["codigo", "numero", "tipo", "autor", "autor_normalizado",
              "cod_autor", "uf", "municipio", "cod_municipio",
              "funcao", "subfuncao", "programa", "acao"]
    schema = build_schema(textos)
    corte = len(textos)
    tipados = [
        bigquery.SchemaField("ano_emenda", "INT64"),
        # BOOL de verdade: como STRING, "false" seria verdadeiro em SQL e autor
        # coletivo entraria na ficha de gente.
        bigquery.SchemaField("autor_e_pessoa", "BOOL"),
        bigquery.SchemaField("vl_empenhado", "FLOAT64"),
        bigquery.SchemaField("vl_liquidado", "FLOAT64"),
        bigquery.SchemaField("vl_pago", "FLOAT64"),
        bigquery.SchemaField("vl_restos_pagos", "FLOAT64"),
    ]
    return schema[:corte] + tipados + schema[corte:]


def cmd_load(args: argparse.Namespace) -> int:
    settings = get_settings()
    settings.ensure_dirs()

    caminho = baixar(settings, force=args.force, dry_run=args.dry_run)
    if args.dry_run:
        log.info("[dry-run] baixaria %s/%s", BASE, ANO_NA_URL)
        return 0

    todas = ler(caminho)
    if not todas:
        log.error("nenhuma linha lida")
        return 75  # EX_TEMPFAIL

    anos = {e.ano_emenda for e in todas if e.ano_emenda}
    log.info("%d linhas · emendas de %s a %s", len(todas), min(anos), max(anos))

    pessoas = sum(1 for e in todas if e.autor_e_pessoa)
    sem_autor = sum(1 for e in todas if not e.autor_normalizado
                    or "SEM INFORMA" in e.autor_normalizado)
    log.info("%d linhas · %d de autor pessoal (%.0f%%) · %d sem autor (%.0f%%)",
             len(todas), pessoas, 100 * pessoas / len(todas),
             sem_autor, 100 * sem_autor / len(todas))

    agora = utc_now()
    destino = settings.staging_dir / "emendas.ndjson.gz"
    with NdjsonWriter(destino) as w:
        for emenda in todas:
            linha = asdict(emenda)
            linha["_extracted_at"] = agora
            linha["_source_url"] = BASE
            w.write(linha)
    log.info("%d linhas gravadas", w.rows)

    if args.target == "local":
        log.info("NDJSON em %s", destino)
        return 0

    from ingest.common.bq import ensure_datasets, load_ndjson

    ensure_datasets(settings)
    load_ndjson(destino, DATASET_RAW_TESOURO, "emendas",
                schema=_schema(), clustering=("autor_normalizado", "tipo"),
                settings=settings)
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Le' um ano e mostra a composicao, sem gravar nada.

    Regra 6: a parte que nenhum teste automatico pega e' a autoria. O numero
    esta' certo e o NOME e' que pode estar errado — e aqui o nome vale milhoes.
    """
    settings = get_settings()
    settings.ensure_dirs()
    linhas = ler(baixar(settings))
    anos = sorted({x.ano_emenda for x in linhas if x.ano_emenda})
    print(f"\n  {len(linhas):,} linhas · emendas de {anos[0]} a {anos[-1]}\n")

    print("  ── por ano da emenda ──")
    for a in anos:
        do_ano = [x for x in linhas if x.ano_emenda == a]
        pago = sum(x.vl_pago for x in do_ano)
        print(f"    {a}  {len(do_ano):>7,} linhas   R$ {pago / 1e9:>6.2f} bi pagos")


    print("  ── por tipo de emenda ──")
    for tipo, n in Counter(x.tipo for x in linhas).most_common():
        pago = sum(x.vl_pago for x in linhas if x.tipo == tipo)
        print(f"    {tipo[:52]:54s} {n:>7,}  R$ {pago / 1e9:>6.1f} bi pagos")

    pessoais = [x for x in linhas if x.autor_e_pessoa]
    sem = [x for x in linhas if "SEM INFORMA" in x.autor_normalizado]
    print("\n  ── autoria ──")
    print(f"    autor pessoal      {len(pessoais):>7,} ({100 * len(pessoais) / len(linhas):.0f}%)")
    print(f"    SEM AUTOR          {len(sem):>7,} ({100 * len(sem) / len(linhas):.0f}%)"
          "   <- L-29: o Portal nao publica")
    print(f"    coletivo/relator   {len(linhas) - len(pessoais) - len(sem):>7,}")

    por_autor: dict[str, float] = defaultdict(float)
    for x in pessoais:
        por_autor[x.autor_normalizado] += x.vl_pago
    print(f"\n  {len(por_autor):,} autores individuais distintos")
    print("\n  ATENCAO: este comando NAO ordena autor por valor de proposito. "
          "Ranking de\n  politico por dinheiro e' placar, e a Constituicao 0.1 "
          "proibe.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ingest.emendas", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    load = sub.add_parser("load", help="baixa e carrega as emendas")
    load.add_argument("--force", action="store_true", help="rebaixa mesmo em cache")
    load.add_argument("--dry-run", action="store_true")
    load.add_argument("--target", choices=("bq", "local"), default="bq")
    load.set_defaults(func=cmd_load)

    ver = sub.add_parser("verify", help="mostra a composicao de um ano")
    ver.add_argument("--dry-run", action="store_true")
    ver.set_defaults(func=cmd_verify)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return executar(args.func, args)


if __name__ == "__main__":
    sys.exit(main())
