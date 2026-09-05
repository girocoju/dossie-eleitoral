"""Consultas que alimentam o relatorio analitico em PDF (F-28).

Escreve `data/relatorio/dados.json`. Roda contra os MESMOS marts que alimentam o
site — nao ha' caminho paralelo, e e' isso que garante que um numero do relatorio
e um numero da ficha nao possam divergir.

    python -m scripts.dados_relatorio

Este modulo nao formata nada. Ele so' pergunta e grava; quem le' e' o
`scripts.gerar_relatorio`. A separacao existe porque a coleta custa alguns
minutos de BigQuery e a formatacao muda dez vezes por revisao.
"""

from __future__ import annotations

import json
from pathlib import Path

from ingest.common.log import get_logger
from scripts.gerar_site import _cliente

log = get_logger("relatorio")

SAIDA = Path(__file__).resolve().parents[1] / "data" / "relatorio" / "dados.json"


def coletar() -> dict[str, list[dict]]:
    cl = _cliente()
    p = cl.project
    dados: dict[str, list[dict]] = {}

    def q(nome: str, sql: str) -> None:
        dados[nome] = [dict(r) for r in cl.query(sql).result()]
        log.info("%-22s %d linhas", nome, len(dados[nome]))

    BASE = f"""
      from `{p}.marts.dim_candidato` d
      join `{p}.marts.fct_candidatura` f using (sk_candidatura)
      where d.ano_eleicao = 2026 and f.e_registro_exibido
    """

    # `e_registro_exibido` e' o filtro do site: candidatura que o TSE tirou do ar
    # nao entra em contagem nenhuma. Sem ele, o relatorio contaria mais gente que
    # a home mostra, e ninguem saberia por que.
    EXIB = f"join `{p}.marts.fct_candidatura` f using (sk_candidatura)"

    q("total", f"select count(*) n, count(distinct d.id_pessoa) pessoas {BASE}")

    q("por_cargo", f"""
      select g.descricao cargo, d.cod_cargo, count(*) n
      from `{p}.marts.dim_candidato` d
      join `{p}.marts.fct_candidatura` f using (sk_candidatura)
      join `{p}.marts.dim_cargo` g on g.cod_cargo = d.cod_cargo
      where d.ano_eleicao = 2026 and f.e_registro_exibido
      group by 1,2 order by d.cod_cargo""")

    q("por_uf", f"""
      select d.sg_uf, count(*) n,
             countif(d.genero = 'FEMININO') mulheres,
             countif(d.cor_raca in ('PRETA','PARDA')) negros
      {BASE} group by 1 order by n desc""")

    # Deputado federal por estado: a competicao nao e' distribuida por igual, e
    # o numero de vagas por UF e' fixado pela Constituicao.
    q("dep_federal_uf", f"""
      select d.sg_uf, count(*) n
      {BASE} and d.cod_cargo = 6
      group by 1 order by n desc""")

    q("genero_cargo", f"""
      select d.cod_cargo, d.genero, count(*) n
      {BASE} and d.genero is not null group by 1,2 order by 1,2""")

    q("raca_cargo", f"""
      select d.cod_cargo, d.cor_raca, count(*) n
      {BASE} and d.cor_raca is not null group by 1,2 order by 1,2""")

    q("instrucao", f"""
      select d.grau_instrucao, count(*) n
      {BASE} and d.grau_instrucao is not null group by 1 order by n desc""")

    q("ocupacao", f"""
      select d.ocupacao, count(*) n
      {BASE} and d.ocupacao is not null group by 1 order by n desc limit 25""")

    q("idade", f"""
      select d.cod_cargo,
             approx_quantiles(d.idade_na_posse_valida, 100)[offset(10)] p10,
             approx_quantiles(d.idade_na_posse_valida, 100)[offset(50)] mediana,
             approx_quantiles(d.idade_na_posse_valida, 100)[offset(90)] p90,
             min(d.idade_na_posse_valida) menor, max(d.idade_na_posse_valida) maior,
             count(*) n
      {BASE} and d.idade_na_posse_valida is not null group by 1 order by 1""")

    q("partidos", f"""
      select d.sigla_partido, count(*) n,
             countif(d.genero = 'FEMININO') mulheres,
             countif(d.cor_raca in ('PRETA','PARDA')) negros
      {BASE} and d.sigla_partido is not null group by 1 order by n desc""")

    q("situacao", f"""
      select f.situacao_julgamento s, count(*) n
      {BASE} group by 1 order by n desc""")

    q("reeleicao", f"""
      select d.cod_cargo, countif(f.is_reeleicao) reeleicao, count(*) n
      {BASE} group by 1 order by 1""")

    q("financiamento_origem", f"""
      select fi.origem_recurso origem, count(distinct fi.sk_candidatura) cands,
             sum(fi.vl_receita) total
      from `{p}.marts.fct_financiamento_candidatura` fi
      join `{p}.marts.dim_candidato` d using (sk_candidatura)
      {EXIB}
      where d.ano_eleicao = 2026 and f.e_registro_exibido
      group by 1 order by total desc""")

    q("financiamento_cargo", f"""
      with t as (
        select d.cod_cargo, fi.sk_candidatura, sum(fi.vl_receita) total
        from `{p}.marts.fct_financiamento_candidatura` fi
        join `{p}.marts.dim_candidato` d using (sk_candidatura)
        {EXIB}
        where d.ano_eleicao = 2026 and f.e_registro_exibido
        group by 1,2)
      select cod_cargo, count(*) cands,
             approx_quantiles(total,100)[offset(50)] mediana,
             approx_quantiles(total,100)[offset(90)] p90,
             max(total) maximo, sum(total) soma
      from t group by 1 order by 1""")

    q("cobertura_prestacao", f"""
      select d.cod_cargo, count(*) n,
             countif(fi.sk_candidatura is not null) com_prestacao
      from `{p}.marts.dim_candidato` d
      {EXIB}
      left join (select distinct sk_candidatura from
                 `{p}.marts.fct_financiamento_candidatura`) fi using (sk_candidatura)
      where d.ano_eleicao = 2026 and f.e_registro_exibido
      group by 1 order by 1""")

    q("doadores_tipo", f"""
      select dc.doador_tipo tipo, count(*) linhas,
             count(distinct dc.nome_doador) doadores, sum(dc.vl_doado) total
      from `{p}.marts.fct_doador_candidatura` dc
      join `{p}.marts.dim_candidato` d using (sk_candidatura)
      {EXIB}
      where d.ano_eleicao = 2026 and f.e_registro_exibido
      group by 1 order by total desc""")

    q("doadores_ramo", f"""
      select dc.doador_ramo ramo, count(distinct dc.nome_doador) doadores,
             sum(dc.vl_doado) total
      from `{p}.marts.fct_doador_candidatura` dc
      join `{p}.marts.dim_candidato` d using (sk_candidatura)
      {EXIB}
      where d.ano_eleicao = 2026 and f.e_registro_exibido
        and dc.doador_tipo = 'J' and dc.doador_ramo is not null
      group by 1 order by total desc limit 15""")

    # ── patrimonio ───────────────────────────────────────────────────────────
    q("patrimonio_cargo", f"""
      with t as (
        select d.cod_cargo, x.id_pessoa, x.vl_total_declarado v
        from `{p}.marts.fct_patrimonio_declarado` x
        join `{p}.marts.dim_candidato` d
          on d.id_pessoa = x.id_pessoa and d.ano_eleicao = x.ano_eleicao
        {EXIB}
        where x.ano_eleicao = 2026 and f.e_registro_exibido)
      select cod_cargo, count(*) n,
             approx_quantiles(v,100)[offset(25)] p25,
             approx_quantiles(v,100)[offset(50)] mediana,
             approx_quantiles(v,100)[offset(90)] p90,
             max(v) maximo
      from t group by 1 order by 1""")

    q("patrimonio_grupo", f"""
      select b.grupo_bem grupo, count(distinct b.sk_candidatura) cands,
             sum(b.qt_itens) itens, sum(b.vl_total) total
      from `{p}.marts.fct_bem_candidatura` b
      join `{p}.marts.dim_candidato` d using (sk_candidatura)
      {EXIB}
      where b.ano_eleicao = 2026 and f.e_registro_exibido
      group by 1 order by total desc""")

    q("declarou_bem", f"""
      select d.cod_cargo, count(*) n, countif(f.declarou_algum_bem) com_bem
      from `{p}.marts.dim_candidato` d {EXIB}
      where d.ano_eleicao = 2026 and f.e_registro_exibido
      group by 1 order by 1""")

    # ── trajetoria e experiencia ─────────────────────────────────────────────
    q("trajetoria_dist", f"""
      with t as (
        select d.id_pessoa, count(*) anteriores
        from `{p}.marts.dim_candidato` d
        join `{p}.marts.fct_candidatura` f2 using (sk_candidatura)
        where d.ano_eleicao < 2026 and f2.e_registro_exibido
          and d.id_pessoa in (
            select d2.id_pessoa from `{p}.marts.dim_candidato` d2
            join `{p}.marts.fct_candidatura` f3 on f3.sk_candidatura = d2.sk_candidatura
            where d2.ano_eleicao = 2026 and f3.e_registro_exibido)
        group by 1)
      select least(anteriores, 8) faixa, count(*) pessoas
      from t group by 1 order by 1""")

    q("estreantes", f"""
      select d.cod_cargo, count(*) n,
             countif(d.id_pessoa not in (
               select distinct id_pessoa from `{p}.marts.dim_candidato`
               where ano_eleicao < 2026 and id_pessoa is not null)) estreantes
      from `{p}.marts.dim_candidato` d {EXIB}
      where d.ano_eleicao = 2026 and f.e_registro_exibido and d.id_pessoa is not null
      group by 1 order by 1""")

    # ── emendas ──────────────────────────────────────────────────────────────
    q("emendas_ano", f"""
      select ano_emenda ano, count(distinct id_pessoa) parlamentares,
             sum(qt_emendas) emendas, sum(vl_empenhado) empenhado, sum(vl_pago) pago
      from `{p}.marts.fct_emenda_autor`
      where ano_emenda between 2015 and 2026
      group by 1 order by 1""")

    q("emendas_funcao", f"""
      select funcao, count(*) linhas, sum(vl_pago) pago
      from `{p}.stg.stg_transparencia__emendas`
      where autor_e_pessoa and funcao is not null
      group by 1 order by pago desc limit 12""")

    q("emendas_tipo", f"""
      select tipo, count(*) linhas, sum(vl_empenhado) empenhado, sum(vl_pago) pago
      from `{p}.stg.stg_transparencia__emendas`
      group by 1 order by empenhado desc""")

    # ── atividade legislativa ────────────────────────────────────────────────
    q("atividade_classe", f"""
      select classe_proposicao classe, count(distinct id_pessoa) pessoas,
             sum(qt_proposicoes) total
      from `{p}.marts.fct_atividade_legislativa`
      where ligado_ao_tse and ano >= 2023
      group by 1 order by total desc""")

    q("comissoes_classe", f"""
      select classe_orgao classe, count(*) assentos, count(distinct id_pessoa) pessoas
      from `{p}.marts.fct_comissao_deputado`
      group by 1 order by assentos desc""")

    q("patrimonio_mm", f"""
      with t as (
        select d.cod_cargo c, f.total_bens_declarados v
        from `{p}.marts.dim_candidato` d
        join `{p}.marts.fct_candidatura` f using (sk_candidatura)
        where d.ano_eleicao = 2026 and f.e_registro_exibido
          and f.declarou_algum_bem and d.cod_cargo in (1,3,5,6,7,8))
      select c cod_cargo, count(*) n, avg(v) media,
             approx_quantiles(v,100)[offset(50)] mediana,
             countif(v > (select avg(v) from t t2 where t2.c = t.c)) acima
      from t group by c order by c""")

    q("financiamento_mm", f"""
      with t as (
        select d.cod_cargo c, sum(fi.vl_receita) v
        from `{p}.marts.fct_financiamento_candidatura` fi
        join `{p}.marts.dim_candidato` d using (sk_candidatura)
        join `{p}.marts.fct_candidatura` f using (sk_candidatura)
        where d.ano_eleicao = 2026 and f.e_registro_exibido and d.cod_cargo in (1,3,5,6,7,8)
        group by 1, fi.sk_candidatura)
      select c cod_cargo, count(*) n, avg(v) media,
             approx_quantiles(v,100)[offset(50)] mediana,
             countif(v > (select avg(v) from t t2 where t2.c = t.c)) acima
      from t group by c order by c""")

    q("idade_mm", f"""
      select d.cod_cargo, count(*) n, avg(d.idade_na_posse_valida) media,
             approx_quantiles(d.idade_na_posse_valida,100)[offset(50)] mediana
      from `{p}.marts.dim_candidato` d
      join `{p}.marts.fct_candidatura` f using (sk_candidatura)
      where d.ano_eleicao = 2026 and f.e_registro_exibido
        and d.idade_na_posse_valida is not null and d.cod_cargo in (1,3,5,6,7,8)
      group by 1 order by 1""")

    q("emendas_mm", f"""
      with t as (
        select ano_emenda a, id_pessoa, sum(vl_empenhado) v
        from `{p}.marts.fct_emenda_autor`
        where starts_with(tipo, 'Emenda Individual') and ano_emenda between 2019 and 2026
        group by 1,2)
      select a ano, count(*) n, avg(v) media,
             approx_quantiles(v,100)[offset(50)] mediana,
             countif(v > (select avg(v) from t t2 where t2.a = t.a)) acima
      from t group by a order by a""")

    q("efeito_outlier", f"""
      with t as (
        select f.total_bens_declarados v
        from `{p}.marts.dim_candidato` d
        join `{p}.marts.fct_candidatura` f using (sk_candidatura)
        where d.ano_eleicao = 2026 and f.e_registro_exibido
          and d.cod_cargo = 7 and f.declarou_algum_bem)
      select avg(v) com, (select avg(v) from t where v < 1e9) sem,
             approx_quantiles(v,100)[offset(50)] mediana, count(*) n from t""")
    # ── comissoes, nas DUAS casas (F-29 / ADR-048) ───────────────────────
    q("comissoes_senado_classe", f"""
      select classe_colegiado classe, count(*) assentos,
             count(distinct id_pessoa) pessoas
      from `{p}.marts.fct_comissao_senador`
      group by 1 order by assentos desc""")

    # De onde veio a natureza do colegiado: do catalogo da fonte ou do nome
    # oficial por extenso. E' a medida do buraco descrito no ADR-048.
    q("comissoes_senado_origem", f"""
      select origem_da_classe origem, count(*) assentos
      from `{p}.marts.fct_comissao_senador`
      group by 1 order by assentos desc""")

    q("comissoes_senado_papel", f"""
      select papel, origem_do_vinculo origem, count(*) vinculos
      from `{p}.stg.stg_senado__comissoes`
      group by 1, 2 order by vinculos desc""")

    # Quantas fichas de 2026 recebem cada bloco legislativo. Sem isto o leitor
    # nao sabe se "892 candidaturas" e "51 candidaturas" sao o mesmo universo.
    q("alcance_blocos", f"""
      with c26 as (
        select distinct d.id_pessoa
        from `{p}.marts.dim_candidato` d
        join `{p}.marts.fct_candidatura` f using (sk_candidatura)
        where d.ano_eleicao = 2026 and f.e_registro_exibido
          and d.id_pessoa is not null)
      select 'comissao_camara' bloco,
             (select count(*) from c26 where id_pessoa in (
                select id_pessoa from `{p}.marts.fct_comissao_deputado`)) fichas
      union all
      select 'comissao_senado',
             (select count(*) from c26 where id_pessoa in (
                select id_pessoa from `{p}.marts.fct_comissao_senador`))
      union all
      select 'atividade_senado',
             (select count(*) from c26 where id_pessoa in (
                select id_pessoa from `{p}.marts.fct_atividade_senado`
                where id_pessoa is not null))""")

    # ── retratos individuais e extremos ──────────────────────────────────
    # Este alias carrega o WHERE junto: as consultas abaixo o encaixam depois do
    # alias `d`, e o `and ...` que vem a seguir e' continuacao dele.
    EXIB26 = f"""
      join `{p}.marts.fct_candidatura` f using (sk_candidatura)
      where d.ano_eleicao = 2026 and f.e_registro_exibido
    """

    # 1. Pessoa com mais de uma candidatura exibida em 2026
    q("multipla_candidatura", f"""
      select d.id_pessoa, count(*) n,
             string_agg(concat(d.nome_urna, ' (', cast(d.cod_cargo as string),
                               '/', d.sg_uf, ')'), ' | ') quais
      from `{p}.marts.dim_candidato` d {EXIB26} and d.id_pessoa is not null
      group by 1 having n > 1 order by n desc limit 10""")

    # 2. Maiores patrimonios declarados, por cargo majoritario
    q("maiores_patrimonios", f"""
      select d.nome_urna, d.cod_cargo, d.sg_uf, d.sigla_partido,
             f.total_bens_declarados v, f.n_bens
      from `{p}.marts.dim_candidato` d {EXIB26} and d.cod_cargo in (1,2,3,5)
      order by f.total_bens_declarados desc limit 10""")

    # 3. Maiores patrimonios entre proporcionais
    q("maiores_patrimonios_prop", f"""
      select d.nome_urna, d.cod_cargo, d.sg_uf, d.sigla_partido,
             f.total_bens_declarados v, f.n_bens
      from `{p}.marts.dim_candidato` d {EXIB26} and d.cod_cargo in (6,7,8)
      order by f.total_bens_declarados desc limit 10""")

    # 4. Candidatos mais velhos e mais novos
    q("extremos_idade", f"""
      (select d.nome_urna, d.cod_cargo, d.sg_uf, d.sigla_partido,
              d.idade_na_posse_valida idade, 'mais velho' tipo
       from `{p}.marts.dim_candidato` d {EXIB26} and d.idade_na_posse_valida is not null
       order by d.idade_na_posse_valida desc limit 5)
      union all
      (select d.nome_urna, d.cod_cargo, d.sg_uf, d.sigla_partido,
              d.idade_na_posse_valida, 'mais novo'
       from `{p}.marts.dim_candidato` d {EXIB26} and d.idade_na_posse_valida is not null
       order by d.idade_na_posse_valida limit 5)""")

    # 5. Quem mais tentou: mais candidaturas anteriores
    q("mais_tentativas", f"""
      with alvo as (
        select distinct d.id_pessoa, d.nome_urna, d.cod_cargo, d.sg_uf
        from `{p}.marts.dim_candidato` d {EXIB26} and d.id_pessoa is not null),
      hist as (
        select d.id_pessoa, count(*) anteriores,
               countif(f2.resultado_final) eleito_antes,
               min(d.ano_eleicao) primeira
        from `{p}.marts.dim_candidato` d
        join `{p}.marts.fct_candidatura` f2 using (sk_candidatura)
        where d.ano_eleicao < 2026 and f2.e_registro_exibido
        group by 1)
      select a.nome_urna, a.cod_cargo, a.sg_uf, h.anteriores, h.eleito_antes, h.primeira
      from alvo a join hist h using (id_pessoa)
      order by h.anteriores desc limit 10""")

    # 6. O salto das emendas em 2023 — pergunta em aberto do SPEC 11
    q("emendas_salto", f"""
      select ano_emenda ano, tipo, sum(vl_empenhado) empenhado
      from `{p}.marts.fct_emenda_autor`
      where ano_emenda between 2021 and 2025
      group by 1,2 order by 1,3 desc""")

    # 7. Partidos: concentracao de candidaturas
    q("partido_uf", f"""
      select d.sigla_partido, count(distinct d.sg_uf) ufs, count(*) n
      from `{p}.marts.dim_candidato` d {EXIB26} and d.sigla_partido is not null
      group by 1 order by n desc limit 8""")

    # 8. Federacoes
    q("federacoes", f"""
      select f.sg_federacao, count(*) n, count(distinct d.sigla_partido) partidos
      from `{p}.marts.dim_candidato` d {EXIB26} and f.sg_federacao is not null
      group by 1 order by n desc""")

    # 9. Candidatos sem bem declarado, por cargo majoritario
    q("sem_bem_majoritario", f"""
      select d.nome_urna, d.cod_cargo, d.sg_uf, d.sigla_partido
      from `{p}.marts.dim_candidato` d {EXIB26}
        and d.cod_cargo in (1,3,5) and not f.declarou_algum_bem
      order by d.cod_cargo limit 12""")

    # 10. Maior arrecadacao de campanha
    q("maior_arrecadacao", f"""
      with t as (
        select fi.sk_candidatura, sum(fi.vl_receita) total
        from `{p}.marts.fct_financiamento_candidatura` fi group by 1)
      select d.nome_urna, d.cod_cargo, d.sg_uf, d.sigla_partido, t.total
      from t join `{p}.marts.dim_candidato` d using (sk_candidatura) {EXIB26}
      order by t.total desc limit 10""")

    # ── a mesma pessoa com duas candidaturas em 2026 ─────────────────────
    # Nao e' irregularidade: o TSE publica o pedido, e um deles costuma cair no
    # julgamento. O relatorio explica isso — e para explicar precisa contar.
    DUP = f"""
      select d.id_pessoa
      from `{p}.marts.dim_candidato` d
      join `{p}.marts.fct_candidatura` f using (sk_candidatura)
      where d.ano_eleicao = 2026 and f.e_registro_exibido and d.id_pessoa is not null
      group by 1 having count(*) > 1
    """

    q("dupla_combinacao", f"""
      with dup as ({DUP}),
      cargos as (
        select d.id_pessoa pid, d.cod_cargo
        from `{p}.marts.dim_candidato` d
        join `{p}.marts.fct_candidatura` f using (sk_candidatura)
        join dup on dup.id_pessoa = d.id_pessoa
        where d.ano_eleicao = 2026 and f.e_registro_exibido)
      select combinacao, count(*) pessoas
      from (select string_agg(cast(cod_cargo as string), '+' order by cod_cargo) combinacao
            from cargos group by pid)
      group by 1 order by pessoas desc""")

    q("dupla_situacao", f"""
      with dup as ({DUP})
      select f.situacao_julgamento sit, count(*) n
      from `{p}.marts.dim_candidato` d
      join `{p}.marts.fct_candidatura` f using (sk_candidatura)
      join dup on dup.id_pessoa = d.id_pessoa
      where d.ano_eleicao = 2026 and f.e_registro_exibido
      group by 1 order by n desc""")

    q("dupla_ambas_deferidas", f"""
      with dup as ({DUP}),
      det as (
        select d.id_pessoa, d.nome_urna, d.cod_cargo, d.sg_uf, d.sigla_partido,
               f.situacao_julgamento sit
        from `{p}.marts.dim_candidato` d
        join `{p}.marts.fct_candidatura` f using (sk_candidatura)
        join dup on dup.id_pessoa = d.id_pessoa
        where d.ano_eleicao = 2026 and f.e_registro_exibido)
      select id_pessoa,
             string_agg(concat(nome_urna, ' [', cast(cod_cargo as string), '] ', sit),
                        '  ||  ' order by cod_cargo) detalhe,
             countif(sit = 'DEFERIDO') deferidas, count(*) n
      from det group by 1 having deferidas >= 2 order by n desc limit 12""")

    q("dupla_resumo", f"""
      with dup as ({DUP}),
      det as (
        select d.id_pessoa, countif(f.situacao_julgamento = 'DEFERIDO') def, count(*) n
        from `{p}.marts.dim_candidato` d
        join `{p}.marts.fct_candidatura` f using (sk_candidatura)
        join dup on dup.id_pessoa = d.id_pessoa
        where d.ano_eleicao = 2026 and f.e_registro_exibido
        group by 1)
      select countif(def >= 2) ambas_deferidas, countif(def = 1) uma_deferida,
             countif(def = 0) nenhuma, count(*) total
      from det""")

    # ── escala do patrimonio e o salto das emendas ───────────────────────
    q("escala_patrimonio", f"""
      select countif(f.total_bens_declarados >= 1e9) bi,
             countif(f.total_bens_declarados >= 1e8) c100mi,
             countif(f.total_bens_declarados >= 1e7) c10mi,
             countif(f.total_bens_declarados >= 1e6) c1mi,
             countif(f.declarou_algum_bem) com_bem, count(*) total
      from `{p}.marts.dim_candidato` d
      join `{p}.marts.fct_candidatura` f using (sk_candidatura)
      where d.ano_eleicao = 2026 and f.e_registro_exibido""")

    # ── as declaracoes que se descolam por ordem de grandeza ─────────────
    # Eram uma quando o relatorio foi escrito pela primeira vez, e o TSE seguiu
    # publicando. O corte fica no dado, e nao no texto, para que a proxima nao
    # dependa de alguem lembrar de reescrever a secao.
    q("bilionarios", f"""
      select d.sq_candidato, d.nome_urna, d.cod_cargo, d.sg_uf, d.sigla_partido,
             f.total_bens_declarados v, f.n_bens, f.situacao_julgamento situacao,
             (select count(*) from `{p}.marts.dim_candidato` h
              join `{p}.marts.fct_candidatura` hf using (sk_candidatura)
              where h.id_pessoa = d.id_pessoa and h.ano_eleicao < 2026
                and hf.e_registro_exibido) anteriores,
             (select max(hf.total_bens_declarados) from `{p}.marts.dim_candidato` h
              join `{p}.marts.fct_candidatura` hf using (sk_candidatura)
              where h.id_pessoa = d.id_pessoa and h.ano_eleicao < 2026
                and hf.e_registro_exibido) v_anterior
      from `{p}.marts.dim_candidato` d
      join `{p}.marts.fct_candidatura` f using (sk_candidatura)
      where d.ano_eleicao = 2026 and f.e_registro_exibido
        and f.total_bens_declarados >= 1e9
      order by v desc""")

    # Composicao dos bens desses casos, por TIPO. `descricao_bem` nao entra em
    # lugar nenhum: e' texto livre e carrega endereco residencial (ADR-041).
    q("bilionarios_bens", f"""
      select d.sq_candidato, b.tipo_bem, b.qt_itens, b.vl_total
      from `{p}.marts.fct_bem_candidatura` b
      join `{p}.marts.dim_candidato` d using (sk_candidatura)
      join `{p}.marts.fct_candidatura` f using (sk_candidatura)
      where d.ano_eleicao = 2026 and f.e_registro_exibido
        and f.total_bens_declarados >= 1e9
      order by d.sq_candidato, b.vl_total desc""")

    # O maior item isolado de cada um. Um valor redondo — R$ 3.000.000.000,00
    # exatos — diz mais sobre a natureza do numero que o total.
    q("bilionarios_item", f"""
      select d.sq_candidato, b.tipo_bem, b.valor_bem
      from `{p}.stg.stg_tse__bens` b
      join `{p}.marts.dim_candidato` d
        on d.sq_candidato = b.sq_candidato and d.ano_eleicao = b.ano_eleicao
      join `{p}.marts.fct_candidatura` f on f.sk_candidatura = d.sk_candidatura
      where d.ano_eleicao = 2026 and f.e_registro_exibido
        and f.total_bens_declarados >= 1e9
      qualify row_number() over (
        partition by d.sq_candidato order by b.valor_bem desc) <= 2""")

    q("emendas_salto_tipo", f"""
      select ano_emenda ano, tipo, sum(vl_empenhado) emp
      from `{p}.marts.fct_emenda_autor`
      where ano_emenda between 2020 and 2026
      group by 1,2 order by 1""")

    return dados


def main() -> None:
    dados = coletar()
    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(json.dumps(dados, ensure_ascii=False, default=str),
                     encoding="utf-8")
    log.info("gravado %s (%d blocos)", SAIDA, len(dados))


if __name__ == "__main__":
    main()
