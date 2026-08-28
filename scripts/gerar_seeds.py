"""Gera os seeds do dbt a partir das fontes unicas de verdade em Python/YAML.

    python scripts/gerar_seeds.py [--check]

`--check` nao escreve nada e sai com codigo 1 se um seed estiver desatualizado —
e' isso que o CI e o pytest usam para impedir que `ingest/common/ufs.py` e
`dbt/seeds/dim_uf.csv` (ou o catalogo de indicadores e `dim_indicador.csv`)
divirjam sem ninguem perceber.

Os arquivos sao escritos com `newline=""` e comparados apos normalizar CRLF: o
seed tem de sair byte-identico gerado no Windows ou no Linux, senao o `--check`
acusa diferenca que nao existe. Foi o que fez o primeiro run do CI falhar.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingest.common.indicadores import carregar_catalogo  # noqa: E402
from ingest.common.ufs import UFS  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
SEEDS = RAIZ / "dbt" / "seeds"


def _csv(cabecalho: list[str], linhas: list[list[object]]) -> str:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(cabecalho)
    writer.writerows(linhas)
    return buffer.getvalue()


def seed_dim_uf() -> str:
    linhas: list[list[object]] = [[uf.sg_uf, uf.nome, uf.regiao, uf.cod_ibge] for uf in UFS]
    linhas.append(["BR", "Brasil", "Brasil", "1"])  # comparador nacional (SPEC 5)
    return _csv(["sg_uf", "nome", "regiao", "cod_ibge"], linhas)


def seed_dim_indicador() -> str:
    catalogo = carregar_catalogo()
    linhas: list[list[object]] = [
        [
            ind.cod_indicador,
            ind.nome,
            ind.fonte,
            ind.unidade,
            ind.periodicidade,
            ind.direcao_desejavel,
            ind.provedor,
            str(ind.verificado).lower(),
            ind.conferido_em or "",
            " ".join(ind.notas.split()),
        ]
        for ind in catalogo.values()
    ]
    return _csv(
        [
            "cod_indicador",
            "nome",
            "fonte",
            "unidade",
            "periodicidade",
            "direcao_desejavel",
            "provedor",
            "verificado",
            "conferido_em",
            "notas",
        ],
        linhas,
    )


GERADORES = {
    "dim_uf.csv": seed_dim_uf,
    "dim_indicador.csv": seed_dim_indicador,
}


def _ler(destino: Path) -> str | None:
    if not destino.exists():
        return None
    return destino.read_text(encoding="utf-8").replace("\r\n", "\n")


def _escrever(destino: Path, conteudo: str) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with destino.open("w", encoding="utf-8", newline="") as fh:
        fh.write(conteudo)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="so' confere, nao escreve")
    args = parser.parse_args(argv)

    desatualizados = []
    for nome, gerador in GERADORES.items():
        destino = SEEDS / nome
        novo = gerador()
        if _ler(destino) == novo:
            print(f"ok        {nome}")
            continue
        if args.check:
            desatualizados.append(nome)
            print(f"DESATUAL. {nome}")
            continue
        _escrever(destino, novo)
        print(f"gerado    {nome}")

    if desatualizados:
        print(
            "\nSeeds fora de sincronia: "
            + ", ".join(desatualizados)
            + "\nRode `python scripts/gerar_seeds.py` e commite o resultado."
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
