"""Tabela de referencia das 27 unidades da federacao.

Fonte unica de verdade para o `dim_uf` do SPEC 5. O seed do dbt
(`dbt/seeds/dim_uf.csv`) e' GERADO daqui por `scripts/gerar_seeds.py`, e um teste
garante que os dois nao divirjam — assim o codigo de ingestao e o modelo dimensional
nunca discordam sobre o que e' "AC" ou a que regiao pertence.

`cod_ibge` e' o codigo de UF do IBGE (2 digitos), usado para casar a resposta da
API do SIDRA, que devolve codigo e nao sigla.
"""

from __future__ import annotations

from dataclasses import dataclass

BRASIL_SG = "BR"
BRASIL_COD_IBGE = "1"


@dataclass(frozen=True)
class UF:
    sg_uf: str
    nome: str
    regiao: str
    cod_ibge: str


UFS: tuple[UF, ...] = (
    UF("RO", "Rondonia", "Norte", "11"),
    UF("AC", "Acre", "Norte", "12"),
    UF("AM", "Amazonas", "Norte", "13"),
    UF("RR", "Roraima", "Norte", "14"),
    UF("PA", "Para", "Norte", "15"),
    UF("AP", "Amapa", "Norte", "16"),
    UF("TO", "Tocantins", "Norte", "17"),
    UF("MA", "Maranhao", "Nordeste", "21"),
    UF("PI", "Piaui", "Nordeste", "22"),
    UF("CE", "Ceara", "Nordeste", "23"),
    UF("RN", "Rio Grande do Norte", "Nordeste", "24"),
    UF("PB", "Paraiba", "Nordeste", "25"),
    UF("PE", "Pernambuco", "Nordeste", "26"),
    UF("AL", "Alagoas", "Nordeste", "27"),
    UF("SE", "Sergipe", "Nordeste", "28"),
    UF("BA", "Bahia", "Nordeste", "29"),
    UF("MG", "Minas Gerais", "Sudeste", "31"),
    UF("ES", "Espirito Santo", "Sudeste", "32"),
    UF("RJ", "Rio de Janeiro", "Sudeste", "33"),
    UF("SP", "Sao Paulo", "Sudeste", "35"),
    UF("PR", "Parana", "Sul", "41"),
    UF("SC", "Santa Catarina", "Sul", "42"),
    UF("RS", "Rio Grande do Sul", "Sul", "43"),
    UF("MS", "Mato Grosso do Sul", "Centro-Oeste", "50"),
    UF("MT", "Mato Grosso", "Centro-Oeste", "51"),
    UF("GO", "Goias", "Centro-Oeste", "52"),
    UF("DF", "Distrito Federal", "Centro-Oeste", "53"),
)

POR_SIGLA: dict[str, UF] = {uf.sg_uf: uf for uf in UFS}
POR_COD_IBGE: dict[str, UF] = {uf.cod_ibge: uf for uf in UFS}
SIGLAS: tuple[str, ...] = tuple(uf.sg_uf for uf in UFS)


def sigla_por_cod_ibge(cod: str | None) -> str | None:
    """Codigo territorial do IBGE -> sigla. `1` (Brasil) vira `BR`."""
    if not cod:
        return None
    cod = str(cod).strip()
    if cod in {BRASIL_COD_IBGE, "0"}:
        return BRASIL_SG
    uf = POR_COD_IBGE.get(cod[:2])
    return uf.sg_uf if uf else None
