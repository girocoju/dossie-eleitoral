"""Gera o esqueleto do projeto Power BI (`bi/RadarBrasil.pbip`) em formato de texto.

    python scripts/gerar_modelo_bi.py [--check]

Por que gerar em vez de escrever a mao: o modelo semantico tem de refletir
exatamente as tabelas de `marts`. Gerando daqui, uma coluna que nasce no dbt nao
fica esquecida no Power BI — e um `--check` no CI acusa a divergencia.

Isto e' um GERADOR DE ESQUELETO, nao um substituto do Power BI Desktop. Depois de
abrir o `.pbip` no Desktop e salvar, o arquivo passa a ser mantido pelo Desktop:
rodar este script de novo sobrescreveria o trabalho manual. Ele existe para (1) a
primeira criacao e (2) reconstruir o modelo do zero se preciso.

Formato: PBIP com modelo semantico em TMDL (texto, versionavel — ADR-001).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
BI = RAIZ / "bi"
NOME = "RadarBrasil"
MODELO = BI / f"{NOME}.SemanticModel"
RELATORIO = BI / f"{NOME}.Report"

TAB = "\t"


def lineage(*partes: str) -> str:
    """GUID deterministico: reexecutar o gerador nao troca os identificadores."""
    digest = hashlib.sha1("|".join(partes).encode("utf-8")).hexdigest()
    return f"{digest[0:8]}-{digest[8:12]}-{digest[12:16]}-{digest[16:20]}-{digest[20:32]}"


@dataclass
class Coluna:
    nome: str
    tipo: str = "string"
    resumo: str = "none"
    formato: str | None = None
    descricao: str = ""
    oculta: bool = False
    ordenar_por: str | None = None
    # `ImageUrl` faz o Power BI renderizar a URL como imagem em vez de texto.
    # Sem isto a ficha do candidato mostra um link, nao a foto.
    categoria: str | None = None


@dataclass
class Medida:
    nome: str
    expressao: str
    formato: str | None = None
    descricao: str = ""
    pasta: str | None = None


@dataclass
class Tabela:
    nome: str
    descricao: str
    colunas: list[Coluna]
    medidas: list[Medida] = field(default_factory=list)
    oculta: bool = False


# ───────────────────────── modelo ─────────────────────────

TABELAS: list[Tabela] = [
    Tabela(
        "dim_uf",
        "27 unidades da federacao mais a linha BR, o comparador nacional.",
        [
            Coluna("sg_uf", descricao="Sigla da UF. `BR` guarda o agregado nacional."),
            Coluna("nome"),
            Coluna("regiao"),
            Coluna("cod_ibge", oculta=True),
        ],
    ),
    Tabela(
        "dim_cargo",
        "Cargos do TSE com esfera, duracao de mandato e vagas em 2026.",
        [
            Coluna("cod_cargo", "int64", oculta=True),
            Coluna("descricao"),
            Coluna("esfera"),
            Coluna("duracao_mandato_anos", "int64"),
            Coluna("titular", "boolean"),
            Coluna("no_escopo_mvp", "boolean"),
            Coluna(
                "modulo_durante_mandato",
                "boolean",
                descricao="TRUE so' para Presidente e Governador (SPEC 2.2).",
            ),
            Coluna("vagas_2026", "int64", resumo="sum", formato="#,0"),
        ],
        [
            Medida(
                "Vagas em disputa",
                "SUM(dim_cargo[vagas_2026])",
                "#,0",
                "Soma das vagas publicadas pelo TSE em consulta_vagas 2026.",
            )
        ],
    ),
    Tabela(
        "dim_tempo",
        "Calendario anual de 1980 ao ano corrente.",
        [
            Coluna("ano", "int64"),
            Coluna("data_inicio_ano", "dateTime", formato="yyyy", oculta=True),
            Coluna("is_ano_eleicao", "boolean"),
            Coluna("ano_eleicao_anterior", "int64"),
            Coluna("decada", "int64"),
        ],
    ),
    Tabela(
        "dim_indicador",
        "Catalogo de indicadores com fonte, unidade e data de conferencia.",
        [
            Coluna("cod_indicador", oculta=True),
            Coluna("nome"),
            Coluna(
                "fonte",
                descricao="Vai para o rodape de toda visualizacao (Constituicao 0.3).",
            ),
            Coluna("unidade"),
            Coluna("periodicidade"),
            Coluna(
                "direcao_desejavel",
                descricao=(
                    "Usado SO' para escolher a cor neutra de tendencia. "
                    "Nao e' juizo sobre gestao (Constituicao 0.1)."
                ),
            ),
            Coluna("provedor", oculta=True),
            Coluna("verificado", "boolean"),
            Coluna("notas"),
        ],
    ),
    Tabela(
        "dim_partido",
        "Estado do partido em cada eleicao. Sem cor partidaria por padrao.",
        [
            Coluna("sk_partido", oculta=True),
            Coluna("ano_eleicao", "int64", oculta=True),
            Coluna("sigla_partido"),
            Coluna("nome_partido"),
            Coluna("nr_partido", "int64"),
            Coluna("sg_federacao"),
            Coluna("em_federacao", "boolean"),
        ],
    ),
    Tabela(
        "dim_candidato",
        "Retrato da pessoa na eleicao em que concorreu. Chave: sk_candidatura.",
        [
            Coluna(
                "sk_candidatura",
                oculta=True,
                descricao=(
                    "(ano_eleicao, sg_ue, sq_candidato). `sq_candidato` sozinho nao "
                    "serve: so' e' global a partir de 2010."
                ),
            ),
            Coluna("sq_candidato", oculta=True),
            Coluna("ano_eleicao", "int64", oculta=True),
            Coluna("id_pessoa", oculta=True),
            Coluna(
                "link_confiavel",
                "boolean",
                descricao="FALSE quando a identidade veio do fallback nome+nascimento.",
            ),
            Coluna("nome_urna"),
            Coluna("nome_completo"),
            Coluna("nome_social"),
            Coluna(
                "idade_na_posse",
                "int64",
                resumo="none",
                descricao="Como a fonte publica — pode ser impossivel. Ver idade_na_posse_valida.",
                oculta=True,
            ),
            Coluna("idade_na_posse_valida", "int64", resumo="none"),
            Coluna("idade_plausivel", "boolean", oculta=True),
            Coluna("genero"),
            Coluna("cor_raca"),
            Coluna("grau_instrucao"),
            Coluna("estado_civil"),
            Coluna("ocupacao"),
            Coluna("sg_uf_nascimento"),
            Coluna(
                "url_foto",
                categoria="ImageUrl",
                descricao=(
                    "Foto oficial de urna, servida do bucket publico. NULL quando a "
                    "fonte nao publica foto para a candidatura (F-13 / ADR-012)."
                ),
            ),
            Coluna("tem_foto", "boolean"),
            Coluna("cod_cargo", "int64", oculta=True),
            Coluna("sg_uf", oculta=True),
        ],
        [
            Medida(
                "Idade mediana",
                "MEDIAN(dim_candidato[idade_na_posse_valida])",
                "#,0",
                "Mediana, nao media: a distribuicao de idade e' assimetrica.",
                "Perfil",
            ),
            Medida(
                "% com foto",
                "DIVIDE(CALCULATE(COUNTROWS(dim_candidato),"
                " dim_candidato[tem_foto] = TRUE), COUNTROWS(dim_candidato))",
                "0.0%",
                "Cobertura da foto oficial. Abaixo de 95% o pipeline falha (F-13).",
                "Qualidade",
            ),
            Medida(
                "% com identidade confirmada por CPF",
                "DIVIDE(CALCULATE(COUNTROWS(dim_candidato),"
                " dim_candidato[link_confiavel] = TRUE), COUNTROWS(dim_candidato))",
                "0.0%",
                "Quanto da trajetoria exibida nao depende do fallback nome+nascimento.",
                "Qualidade",
            ),
        ],
    ),
    Tabela(
        "fct_candidatura",
        "Uma candidatura por linha. Grao: sk_candidatura.",
        [
            Coluna("sk_candidatura", oculta=True),
            Coluna("sq_candidato", oculta=True),
            Coluna("ano_eleicao", "int64"),
            Coluna("id_pessoa", oculta=True),
            Coluna("cod_cargo", "int64", oculta=True),
            Coluna("sg_uf", oculta=True),
            Coluna("nm_ue"),
            Coluna("sigla_partido", oculta=True),
            Coluna("sg_federacao"),
            Coluna("nome_coligacao"),
            Coluna("situacao_candidatura"),
            Coluna(
                "situacao_julgamento",
                descricao=(
                    "Antes da eleicao e' este o campo util: situacao_candidatura "
                    "vem `#NE` enquanto o registro esta' sub judice."
                ),
            ),
            Coluna("turnos_disputados", "int64"),
            Coluna("situacao_turno"),
            Coluna("foi_eleito", "boolean"),
            Coluna(
                "is_reeleicao",
                "boolean",
                descricao="Derivada do historico de mandatos; o TSE nao publica antes da apuracao.",
            ),
            Coluna("reeleicao_declarada", "boolean", oculta=True),
            Coluna("total_bens_declarados", "double", resumo="sum", formato="#,0"),
            Coluna("n_bens", "int64", resumo="sum"),
            Coluna("declarou_algum_bem", "boolean"),
            Coluna(
                "proposta_obrigatoria",
                "boolean",
                descricao="TRUE para Presidente, Governador e Senador. Vem da lei, nao do dado.",
            ),
            Coluna("tem_proposta_governo", "boolean"),
            Coluna("nome_arquivo_proposta"),
            Coluna(
                "url_proposta_oficial",
                categoria="WebUrl",
                descricao=(
                    "Link para a pagina do candidato no DivulgaCandContas. O projeto "
                    "nao hospeda o PDF (ADR-013) — o leitor confere na fonte."
                ),
            ),
            Coluna("votos_nominais", "int64", resumo="sum", oculta=True),
            Coluna("_extracted_at", "dateTime", oculta=True),
        ],
        [
            Medida("Candidaturas", "COUNTROWS(fct_candidatura)", "#,0", pasta="Contagem"),
            Medida(
                "Candidaturas por vaga",
                "DIVIDE([Candidaturas], [Vagas em disputa])",
                "#,0.0",
                "Concorrencia por vaga. Descritivo, nao avaliativo.",
                "Contagem",
            ),
            Medida(
                "% de mulheres",
                'DIVIDE(CALCULATE([Candidaturas],'
                ' dim_candidato[genero] = "FEMININO"), [Candidaturas])',
                "0.0%",
                "Sobre o genero autodeclarado ao TSE.",
                "Perfil",
            ),
            Medida(
                "% de reeleicao",
                "DIVIDE(CALCULATE([Candidaturas],"
                " fct_candidatura[is_reeleicao] = TRUE), [Candidaturas])",
                "0.0%",
                pasta="Perfil",
            ),
            Medida(
                "Bens declarados (mediana)",
                "MEDIAN(fct_candidatura[total_bens_declarados])",
                "#,0",
                "Mediana e quartis; a media e' dominada por poucos casos extremos.",
                "Bens",
            ),
            Medida(
                "Bens declarados (3o quartil)",
                "PERCENTILE.INC(fct_candidatura[total_bens_declarados], 0.75)",
                "#,0",
                pasta="Bens",
            ),
            Medida(
                "Proposta de governo",
                'IF(SELECTEDVALUE(fct_candidatura[proposta_obrigatoria]) = FALSE,'
                ' "Nao se aplica a este cargo",'
                ' IF(SELECTEDVALUE(fct_candidatura[tem_proposta_governo]) = TRUE,'
                ' "Proposta apresentada ao TSE", "Nao consta proposta no TSE"))',
                descricao=(
                    "Tres estados, nunca vazio: campo em branco se le como omissao do "
                    "candidato, e 93% deles nao tem essa obrigacao (F-14)."
                ),
                pasta="Proposta",
            ),
            Medida(
                "% dos majoritarios com proposta",
                "DIVIDE(CALCULATE([Candidaturas],"
                " fct_candidatura[tem_proposta_governo] = TRUE),"
                " CALCULATE([Candidaturas], fct_candidatura[proposta_obrigatoria] = TRUE))",
                "0.0%",
                "Denominador e' quem tem a obrigacao legal, nao o total de candidatos.",
                "Proposta",
            ),
            Medida(
                "Extraido em",
                'FORMAT(MAX(fct_candidatura[_extracted_at]), "dd/MM/yyyy HH:mm") & " UTC"',
                descricao="Rodape obrigatorio de toda pagina (Constituicao 0.3).",
                pasta="Rodape",
            ),
        ],
    ),
    Tabela(
        "fct_mandato",
        "Um mandato exercido por linha.",
        [
            Coluna("sk_mandato", oculta=True),
            Coluna("id_pessoa", oculta=True),
            Coluna("sk_candidatura", oculta=True),
            Coluna("sq_candidato", oculta=True),
            Coluna("nome_urna"),
            Coluna("cod_cargo", "int64", oculta=True),
            Coluna("sg_uf", oculta=True),
            Coluna("nm_ue"),
            Coluna("sigla_partido"),
            Coluna("ano_eleicao", "int64"),
            Coluna("ano_inicio", "int64"),
            Coluna("ano_fim", "int64"),
            Coluna("motivo_fim"),
            Coluna("em_curso", "boolean"),
            Coluna("link_confiavel", "boolean"),
        ],
        [Medida("Mandatos", "COUNTROWS(fct_mandato)", "#,0", pasta="Contagem")],
    ),
    Tabela(
        "fct_indicador_uf_ano",
        "Indicador x UF x ano, com o comparador nacional e regional na mesma linha.",
        [
            Coluna("cod_indicador", oculta=True),
            Coluna("sg_uf", oculta=True),
            Coluna("regiao", oculta=True),
            Coluna("ano", "int64", oculta=True),
            Coluna("valor", "double", resumo="none"),
            Coluna("valor_brasil", "double", resumo="none"),
            Coluna("valor_regiao", "double", resumo="none"),
            Coluna("n_periodos", "int64", oculta=True),
            Coluna("_extracted_at", "dateTime", oculta=True),
        ],
        [
            Medida(
                "Valor na UF",
                "AVERAGE(fct_indicador_uf_ano[valor])",
                "#,0.00",
                pasta="Indicador",
            ),
            Medida(
                "Valor no Brasil",
                "AVERAGE(fct_indicador_uf_ano[valor_brasil])",
                "#,0.00",
                "Comparador obrigatorio: nunca exibir a UF sozinha (Constituicao 0.2).",
                "Indicador",
            ),
            Medida(
                "Valor na regiao",
                "AVERAGE(fct_indicador_uf_ano[valor_regiao])",
                "#,0.00",
                "Media simples entre as UFs da regiao — comparador de contexto,"
                " nao agregado ponderado.",
                "Indicador",
            ),
        ],
    ),
    Tabela(
        "fct_mandato_indicador",
        (
            "O que aconteceu com o indicador durante a janela do mandato. "
            "NAO mede efeito de gestao."
        ),
        [
            Coluna("sk_mandato", oculta=True),
            Coluna("sk_candidatura", oculta=True),
            Coluna("cod_indicador", oculta=True),
            Coluna("nome_urna"),
            Coluna("sigla_partido"),
            Coluna("nm_ue"),
            Coluna("ano_eleicao", "int64", oculta=True),
            Coluna("ano_inicio", "int64"),
            Coluna("ano_fim", "int64"),
            Coluna("ano_referencia_inicio", "int64"),
            Coluna("ano_referencia_fim", "int64"),
            Coluna("valor_inicio", "double", resumo="none", formato="#,0.00"),
            Coluna("valor_fim", "double", resumo="none", formato="#,0.00"),
            Coluna("variacao_pct", "double", resumo="none", formato="#,0.0"),
            Coluna("variacao_brasil_pct", "double", resumo="none", formato="#,0.0"),
            Coluna("variacao_regiao_pct", "double", resumo="none", formato="#,0.0"),
            Coluna(
                "delta_vs_brasil",
                "double",
                resumo="none",
                formato="#,0.0",
                descricao=(
                    "Diferenca entre duas variacoes observadas no mesmo periodo. "
                    "Descritivo. Nunca rotular como resultado, desempenho ou nota."
                ),
            ),
            Coluna("delta_vs_regiao", "double", resumo="none", formato="#,0.0"),
            Coluna(
                "janela_incompleta",
                "boolean",
                descricao="TRUE quando a serie termina antes do fim do mandato.",
            ),
            Coluna("base_e_heranca", "boolean"),
            Coluna("anos_com_dado", "int64"),
            Coluna("aviso_metodologico", oculta=True),
            Coluna("_extracted_at", "dateTime", oculta=True),
        ],
        [
            Medida(
                "Variacao no periodo (%)",
                "AVERAGE(fct_mandato_indicador[variacao_pct])",
                "#,0.0",
                "Variacao do indicador na UF entre as pontas da janela do mandato.",
                "Durante o mandato",
            ),
            Medida(
                "Variacao no Brasil (%)",
                "AVERAGE(fct_mandato_indicador[variacao_brasil_pct])",
                "#,0.0",
                pasta="Durante o mandato",
            ),
            Medida(
                "Diferenca vs. Brasil (p.p.)",
                "AVERAGE(fct_mandato_indicador[delta_vs_brasil])",
                "#,0.0",
                "Contraste descritivo entre duas variacoes. Nao e' placar.",
                "Durante o mandato",
            ),
            Medida(
                "Aviso metodologico",
                (
                    '"Indicadores refletem o periodo; nao medem o efeito do mandato." & '
                    'IF(SELECTEDVALUE(fct_mandato_indicador[janela_incompleta]) = TRUE, '
                    '" Serie termina antes do fim do mandato.", "")'
                ),
                descricao="Texto obrigatorio da pagina Durante o Mandato (F-06).",
                pasta="Rodape",
            ),
            Medida(
                "Fontes",
                'CONCATENATEX(VALUES(dim_indicador[fonte]), dim_indicador[fonte], " · ")',
                descricao="Rodape obrigatorio (Constituicao 0.3).",
                pasta="Rodape",
            ),
        ],
    ),
]

RELACIONAMENTOS = [
    ("fct_candidatura", "sk_candidatura", "dim_candidato", "sk_candidatura", "oneToOne"),
    ("fct_candidatura", "cod_cargo", "dim_cargo", "cod_cargo", "manyToOne"),
    ("fct_candidatura", "sg_uf", "dim_uf", "sg_uf", "manyToOne"),
    ("fct_candidatura", "ano_eleicao", "dim_tempo", "ano", "manyToOne"),
    ("fct_mandato", "cod_cargo", "dim_cargo", "cod_cargo", "manyToOne"),
    ("fct_mandato", "sg_uf", "dim_uf", "sg_uf", "manyToOne"),
    ("fct_indicador_uf_ano", "cod_indicador", "dim_indicador", "cod_indicador", "manyToOne"),
    ("fct_indicador_uf_ano", "sg_uf", "dim_uf", "sg_uf", "manyToOne"),
    ("fct_indicador_uf_ano", "ano", "dim_tempo", "ano", "manyToOne"),
    ("fct_mandato_indicador", "sk_mandato", "fct_mandato", "sk_mandato", "manyToOne"),
    ("fct_mandato_indicador", "cod_indicador", "dim_indicador", "cod_indicador", "manyToOne"),
]

PAGINAS = [
    ("visao-geral", "Visao Geral"),
    ("candidatos", "Candidatos"),
    ("presidencia", "Presidencia"),
    ("governadores", "Governadores"),
    ("senado", "Senado"),
    ("camara", "Camara dos Deputados"),
    ("assembleias", "Assembleias Legislativas"),
    ("contexto-socioeconomico", "Contexto Socioeconomico"),
    ("durante-o-mandato", "Durante o Mandato"),
    ("metodologia", "Metodologia e Fontes"),
]


# ───────────────────────── geracao ─────────────────────────


def _particao_m(tabela: str) -> str:
    linhas = [
        "let",
        "    Fonte = GoogleBigQuery.Database([BillingProject = ProjetoGCP]),",
        "    Projeto = Fonte{[Name = ProjetoGCP]}[Data],",
        "    Dataset = Projeto{[Name = DatasetMarts]}[Data],",
        f'    Tabela = Dataset{{[Name = "{tabela}"]}}[Data]',
        "in",
        "    Tabela",
    ]
    return "\n".join(f"{TAB * 4}{linha}" for linha in linhas)


def tmdl_tabela(t: Tabela) -> str:
    out = [f"table {t.nome}", f"{TAB}lineageTag: {lineage('table', t.nome)}"]
    if t.descricao:
        out.insert(1, f"{TAB}/// {t.descricao}")
    if t.oculta:
        out.append(f"{TAB}isHidden")
    out.append("")

    for m in t.medidas:
        if m.descricao:
            out.append(f"{TAB}/// {m.descricao}")
        out.append(f"{TAB}measure '{m.nome}' = {m.expressao}")
        if m.formato:
            out.append(f"{TAB}{TAB}formatString: {m.formato}")
        out.append(f"{TAB}{TAB}lineageTag: {lineage('measure', t.nome, m.nome)}")
        if m.pasta:
            out.append(f"{TAB}{TAB}displayFolder: {m.pasta}")
        out.append("")

    for c in t.colunas:
        if c.descricao:
            out.append(f"{TAB}/// {c.descricao}")
        out.append(f"{TAB}column {c.nome}")
        out.append(f"{TAB}{TAB}dataType: {c.tipo}")
        if c.formato:
            out.append(f"{TAB}{TAB}formatString: {c.formato}")
        if c.categoria:
            out.append(f"{TAB}{TAB}dataCategory: {c.categoria}")
        if c.oculta:
            out.append(f"{TAB}{TAB}isHidden")
        out.append(f"{TAB}{TAB}lineageTag: {lineage('column', t.nome, c.nome)}")
        out.append(f"{TAB}{TAB}summarizeBy: {c.resumo}")
        out.append(f"{TAB}{TAB}sourceColumn: {c.nome}")
        if c.ordenar_por:
            out.append(f"{TAB}{TAB}sortByColumn: {c.ordenar_por}")
        out.append("")
        out.append(f"{TAB}{TAB}annotation SummarizationSetBy = Automatic")
        out.append("")

    out.append(f"{TAB}partition {t.nome} = m")
    out.append(f"{TAB}{TAB}mode: import")
    out.append(f"{TAB}{TAB}source =")
    out.append(_particao_m(t.nome))
    out.append("")
    out.append(f"{TAB}annotation PBI_ResultType = Table")
    out.append("")
    return "\n".join(out)


def tmdl_relacionamentos() -> str:
    out = []
    for de_t, de_c, para_t, para_c, cardinalidade in RELACIONAMENTOS:
        nome = lineage("rel", de_t, de_c, para_t, para_c)
        out.append(f"relationship {nome}")
        if cardinalidade == "oneToOne":
            out.append(f"{TAB}cardinality: oneToOne")
        out.append(f"{TAB}fromColumn: {de_t}.{de_c}")
        out.append(f"{TAB}toColumn: {para_t}.{para_c}")
        out.append("")
    return "\n".join(out)


def tmdl_expressoes() -> str:
    return "\n".join(
        [
            "/// Projeto GCP que hospeda os datasets. Trocar aqui muda todas as tabelas.",
            'expression ProjetoGCP = "radar-brasil" meta '
            '[IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
            f"{TAB}lineageTag: {lineage('expr', 'ProjetoGCP')}",
            f"{TAB}annotation PBI_NavigationStepName = Navigation",
            "",
            "/// Dataset com as tabelas de marts materializadas pelo dbt.",
            'expression DatasetMarts = "marts" meta '
            '[IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]',
            f"{TAB}lineageTag: {lineage('expr', 'DatasetMarts')}",
            f"{TAB}annotation PBI_NavigationStepName = Navigation",
            "",
        ]
    )


def tmdl_modelo() -> str:
    refs = "\n".join(f"ref table {t.nome}" for t in TABELAS)
    return "\n".join(
        [
            "model Model",
            f"{TAB}culture: pt-BR",
            f"{TAB}defaultPowerBIDataSourceVersion: powerBI_V3",
            f"{TAB}discourageImplicitMeasures",
            f"{TAB}sourceQueryCulture: pt-BR",
            f"{TAB}dataAccessOptions",
            f"{TAB}{TAB}legacyRedirects",
            f"{TAB}{TAB}returnErrorValuesAsNull",
            "",
            f"{TAB}annotation PBI_QueryOrder = "
            + json.dumps([t.nome for t in TABELAS], ensure_ascii=False),
            "",
            refs,
            "",
            "ref cultureInfo pt-BR",
            "",
        ]
    )


def arquivos() -> dict[str, str]:
    saida: dict[str, str] = {}

    # ── .pbip ──
    saida[f"{NOME}.pbip"] = json.dumps(
        {
            "version": "1.0",
            "artifacts": [{"report": {"path": f"{NOME}.Report"}}],
            "settings": {"enableAutoRecovery": True},
        },
        indent=2,
    )

    # ── modelo semantico ──
    saida[f"{NOME}.SemanticModel/.platform"] = json.dumps(
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {"type": "SemanticModel", "displayName": NOME},
            "config": {"version": "2.0", "logicalId": lineage("logical", "semanticmodel")},
        },
        indent=2,
    )
    saida[f"{NOME}.SemanticModel/definition.pbism"] = json.dumps(
        {"version": "4.2", "settings": {"qnaEnabled": False}}, indent=2
    )
    saida[f"{NOME}.SemanticModel/definition/database.tmdl"] = (
        "database\n"
        f"{TAB}compatibilityLevel: 1567\n"
    )
    saida[f"{NOME}.SemanticModel/definition/model.tmdl"] = tmdl_modelo()
    saida[f"{NOME}.SemanticModel/definition/expressions.tmdl"] = tmdl_expressoes()
    saida[f"{NOME}.SemanticModel/definition/relationships.tmdl"] = tmdl_relacionamentos()
    saida[f"{NOME}.SemanticModel/definition/cultures/pt-BR.tmdl"] = (
        "cultureInfo pt-BR\n"
        f"{TAB}linguisticMetadata =\n"
        f"{TAB}{TAB}{{\n"
        f'{TAB}{TAB}  "Version": "1.0.0",\n'
        f'{TAB}{TAB}  "Language": "pt-BR"\n'
        f"{TAB}{TAB}}}\n"
        f"{TAB}{TAB}contentType: json\n"
    )
    for t in TABELAS:
        saida[f"{NOME}.SemanticModel/definition/tables/{t.nome}.tmdl"] = tmdl_tabela(t)

    # ── relatorio ──
    saida[f"{NOME}.Report/.platform"] = json.dumps(
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
            "metadata": {"type": "Report", "displayName": f"{NOME} — Raio-X Eleitoral 2026"},
            "config": {"version": "2.0", "logicalId": lineage("logical", "report")},
        },
        indent=2,
    )
    saida[f"{NOME}.Report/definition.pbir"] = json.dumps(
        {
            "version": "4.0",
            "datasetReference": {"byPath": {"path": f"../{NOME}.SemanticModel"}},
        },
        indent=2,
    )
    saida[f"{NOME}.Report/definition/pages/pages.json"] = json.dumps(
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.0.0/schema.json",
            "pageOrder": [slug for slug, _ in PAGINAS],
            "activePageName": PAGINAS[0][0],
        },
        indent=2,
        ensure_ascii=False,
    )
    for ordem, (slug, titulo) in enumerate(PAGINAS):
        saida[f"{NOME}.Report/definition/pages/{slug}/page.json"] = json.dumps(
            {
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/1.0.0/schema.json",
                "name": slug,
                "displayName": titulo,
                "displayOption": "FitToPage",
                "height": 720,
                "width": 1280,
                "ordinal": ordem,
            },
            indent=2,
            ensure_ascii=False,
        )
    saida[f"{NOME}.Report/definition/report.json"] = json.dumps(
        {
            "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/report/definition/report/1.0.0/schema.json",
            "themeCollection": {
                "customTheme": {"name": "RadarBrasilNeutro", "type": "RegisteredResources"}
            },
            "resourcePackages": [
                {
                    "name": "RegisteredResources",
                    "type": "RegisteredResources",
                    "items": [
                        {
                            "name": "RadarBrasilNeutro",
                            "path": "RadarBrasilNeutro.json",
                            "type": "CustomTheme",
                        }
                    ],
                }
            ],
        },
        indent=2,
        ensure_ascii=False,
    )
    saida[f"{NOME}.Report/StaticResources/RegisteredResources/RadarBrasilNeutro.json"] = (
        json.dumps(
            {
                "name": "RadarBrasilNeutro",
                "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/reportTheme/1.0.0/schema.json",
                # Paleta neutra e' obrigacao da Constituicao 0.1: nenhuma cor de
                # partido por padrao, nenhum verde/vermelho de aprovacao.
                "dataColors": [
                    "#33455B",
                    "#7A8CA6",
                    "#B0BAC7",
                    "#4E6E5D",
                    "#8FA89B",
                    "#8A7B6B",
                    "#B9AC9B",
                    "#5C5470",
                ],
                "background": "#FFFFFF",
                "foreground": "#33455B",
                "tableAccent": "#33455B",
                "textClasses": {
                    "title": {"fontFace": "Segoe UI Semibold", "fontSize": 16},
                    "label": {"fontFace": "Segoe UI", "fontSize": 10},
                },
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return saida


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="so' confere, nao escreve")
    args = parser.parse_args(argv)

    divergentes = []
    for relativo, conteudo in arquivos().items():
        destino = BI / relativo
        atual = destino.read_text(encoding="utf-8") if destino.exists() else None
        if atual == conteudo:
            continue
        if args.check:
            divergentes.append(relativo)
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(conteudo, encoding="utf-8")
        print(f"gerado    {relativo}")

    if divergentes:
        print("Arquivos do .pbip fora de sincronia com o gerador:")
        for nome in divergentes:
            print(f"  {nome}")
        print(
            "\nSe voce editou o relatorio no Power BI Desktop, isso e' ESPERADO — "
            "o Desktop passa a ser o dono do arquivo. Se nao editou, rode "
            "`python scripts/gerar_modelo_bi.py`."
        )
        return 1
    if not args.check:
        print(f"\n{len(arquivos())} arquivos em bi/ — abra bi/{NOME}.pbip no Power BI Desktop.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
