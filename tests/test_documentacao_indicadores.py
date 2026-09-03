"""Todo indicador precisa estar documentado antes de aparecer no site.

Sem esta trava, um indicador novo entra na ficha com o nome cru do catalogo
("Taxa de desocupacao (14 anos ou mais)") e sem nenhuma ressalva — e ressalva e'
justamente onde mora a diferenca entre o numero desta pagina e o numero que a
pessoa viu no jornal.

Foi assim que o PIB ficou meses mostrando "+8,6%" sem dizer que era a precos
correntes, quando o crescimento real do periodo foi 3,2%.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from scripts.render_site import _GLOSSARIO, _NOMINAIS, _NOTAS_INDICADOR

LAYOUT = Path(__file__).resolve().parents[1] / "ingest" / "layouts" / "indicadores.yml"


def catalogo() -> dict:
    dados = yaml.safe_load(LAYOUT.read_text(encoding="utf-8"))
    # O arquivo tem uma chave de topo com o catalogo; aceita as duas formas para
    # nao quebrar se a estrutura ganhar um nivel.
    for valor in (dados, *(v for v in dados.values() if isinstance(v, dict))):
        if any(isinstance(v, dict) and "fonte" in v for v in valor.values()):
            return {k: v for k, v in valor.items() if isinstance(v, dict) and "fonte" in v}
    raise AssertionError("nao achei o catalogo de indicadores no layout")


CODIGOS = sorted(catalogo())


def test_o_catalogo_foi_encontrado():
    assert len(CODIGOS) >= 17, CODIGOS


@pytest.mark.parametrize("cod", CODIGOS)
def test_todo_indicador_tem_nome_curto_e_tooltip(cod):
    # `_GLOSSARIO` alimenta o tooltip da ficha. Sem entrada, o leitor ve' o nome
    # tecnico do catalogo e nenhuma explicacao.
    assert cod in _GLOSSARIO, f"{cod} sem entrada no glossario da ficha"
    nome, ajuda = _GLOSSARIO[cod]
    assert nome and len(nome) <= 40, f"{cod}: nome curto ausente ou longo demais"
    assert ajuda and ajuda.endswith("."), f"{cod}: explicacao ausente ou sem ponto final"


@pytest.mark.parametrize("cod", CODIGOS)
def test_todo_indicador_tem_ficha_na_metodologia(cod):
    # `_NOTAS_INDICADOR` alimenta o glossario completo da pagina de metodologia:
    # o que mede, como o ano e' formado, e a ressalva.
    assert cod in _NOTAS_INDICADOR, f"{cod} sem entrada na pagina de metodologia"
    mede, agrega, ressalva = _NOTAS_INDICADOR[cod]
    assert mede and agrega and ressalva, f"{cod}: documentacao incompleta"


def test_todo_valor_em_reais_correntes_esta_marcado_como_nominal():
    """A marca `nominal` nao pode depender de alguem lembrar de acrescenta-la.

    Qualquer indicador cuja unidade diga "correntes" tem que estar em
    `_NOMINAIS`, senao a ficha mostra a variacao dele como se fosse real.

    `RENDIMENTO_MEDIO` e' a excecao legitima e esta' fora: o IBGE ja' publica em
    valores constantes, e marca-lo como nominal seria o erro oposto.
    """
    cat = catalogo()
    correntes = {c for c, v in cat.items() if "corrente" in str(v.get("unidade", "")).lower()}
    faltando = correntes - _NOMINAIS
    assert not faltando, (
        f"em reais correntes e SEM a marca `nominal`: {sorted(faltando)} — "
        "a variacao deles apareceria como crescimento real")

    constantes = {c for c, v in cat.items() if "constante" in str(v.get("unidade", "")).lower()}
    marcados_errado = constantes & _NOMINAIS
    assert not marcados_errado, (
        f"ja' esta' em valores reais e foi marcado como nominal: {sorted(marcados_errado)}")


def test_indicadores_sem_nivel_estadual_nao_prometem_uf():
    """Serie macroeconomica so' existe para o Brasil, e a nota tem que dizer."""
    cat = catalogo()
    for cod, v in cat.items():
        if v.get("macroeconomica"):
            _, _, ressalva = _NOTAS_INDICADOR[cod]
            assert "Brasil" in ressalva or "brasil" in ressalva.lower(), (
                f"{cod} e' macroeconomica (so' BR) e a ressalva nao diz isso")
