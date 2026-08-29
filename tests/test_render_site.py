"""Apresentacao do dossie — o que o leitor ve'.

Erro aqui nao quebra a pagina: ele muda o que ela AFIRMA sobre uma pessoa real.
Um arredondamento que escreve "100%" onde ha' 99,67% diz que todo o dinheiro veio
de uma origem; um "0%" onde ha' 0,22% diz que nao veio nada.
"""

from __future__ import annotations

import re

import pytest

from scripts.render_site import _pct


class TestPercentual:
    @pytest.mark.parametrize(("parte", "todo", "esperado"), [
        # Os dois extremos que o `.0f` transformava em mentira.
        (117_671, 35_267_671, "&lt;1%"),     # 0,33% viraria "0%"
        (35_150_000, 35_267_671, "&gt;99%"),  # 99,67% viraria "100%"
        # E os casos em que o numero redondo e' verdade e deve aparecer inteiro.
        (0, 100, "0%"),
        (100, 100, "100%"),
        (150_000, 200_051, "75%"),
    ])
    def test_arredondamento_nao_vira_afirmacao_falsa(self, parte, todo, esperado):
        assert _pct(parte, todo) == esperado

    def test_divisao_por_zero_nao_inventa_numero(self):
        assert _pct(1, 0) == "—"

    @pytest.mark.parametrize(("parte", "todo"), [
        (1, 1_000_000), (999_999, 1_000_000), (1, 2), (0, 5), (5, 5),
    ])
    def test_nunca_devolve_angulo_cru(self, parte, todo):
        # `<1%` cru FECHA a celula da tabela: o navegador le' o `<` como inicio
        # de tag e engole o resto. Aconteceu no ar em 29/08/2026, em 134 paginas
        # — a coluna "Fatia" ficou vazia e comeu a coluna seguinte.
        saida = _pct(parte, todo)
        assert not re.search(r"<(?![a-zA-Z/!])", saida), saida
        assert "<" not in saida.replace("&lt;", "").replace("&gt;", "")
