"""Trava contra a regressao mais cara do projeto: o historico sumir sem aviso.

    python scripts/verificar_historico.py

O pipeline diario recarrega so' 2026. Se algum dia a carga voltar a substituir a
tabela inteira (ver ADR-009 vs ADR-010), `raw_tse.candidatos` cairia de ~180 mil
para ~20 mil linhas e `fct_mandato` esvaziaria — sem nenhuma etapa falhando, porque
cada carga isolada continuaria "correta".

Este script falha o job quando isso acontece. Os pisos sao propositalmente folgados:
so' disparam em perda de dados, nunca em variacao normal de candidaturas.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingest.common.config import get_settings  # noqa: E402
from ingest.common.log import get_logger  # noqa: E402

log = get_logger("verificar")

# (tabela, minimo esperado, o que o piso protege)
PISOS: tuple[tuple[str, int, str], ...] = (
    ("raw_tse.candidatos", 150_000, "as oito eleicoes gerais de 1998 a 2026"),
    ("raw_tse.bens", 400_000, "os bens declarados de 2006 a 2026"),
    ("marts.fct_candidatura", 150_000, "o mart de candidaturas"),
    ("marts.fct_mandato", 10_000, "os mandatos que alimentam o Durante o Mandato"),
    ("marts.fct_indicador_uf_ano", 3_000, "as series socioeconomicas"),
    ("marts.snap_candidatura_2026", 20_000, "o snapshot diario das candidaturas"),
)

ANOS_ESPERADOS = 8


def main() -> int:
    from google.cloud import bigquery

    settings = get_settings()
    client = bigquery.Client(project=settings.project, location=settings.location)
    problemas = []

    for tabela, piso, protege in PISOS:
        n = list(client.query(f"select count(*) as n from `{settings.project}.{tabela}`"))[0].n
        marca = "ok" if n >= piso else "FALHOU"
        log.info("%-34s %10d  (piso %d)  %s", tabela, n, piso, marca)
        if n < piso:
            problemas.append(f"{tabela} tem {n:,} linhas, esperado ao menos {piso:,} — {protege}")

    anos = list(
        client.query(
            f"select count(distinct ano_eleicao) as n from `{settings.project}.raw_tse.candidatos`"
        )
    )[0].n
    log.info("%-34s %10d  (esperado %d)", "anos de eleicao distintos", anos, ANOS_ESPERADOS)
    if anos < ANOS_ESPERADOS:
        problemas.append(f"raw_tse.candidatos tem {anos} anos, esperado {ANOS_ESPERADOS}")

    if problemas:
        print("\nPERDA DE DADOS DETECTADA:")
        for p in problemas:
            print(f"  - {p}")
        print(
            "\nQuase sempre significa que a carga substituiu a tabela inteira em vez\n"
            "da particao do ano. Ver docs/adr/ADR-010-particao-por-ano.md."
        )
        return 1
    print("\nHistorico intacto.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
