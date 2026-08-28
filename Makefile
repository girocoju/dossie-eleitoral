# Radar Brasil — Raio-X Eleitoral 2026
# Constituicao §4: `make bootstrap && make run` recria tudo a partir das fontes originais.

SHELL := /bin/bash
PY    ?= python
VENV  ?= .venv
ANO   ?= 2026
ANOS_HISTORICO ?= 1998 2002 2006 2010 2014 2018 2022

ifeq ($(OS),Windows_NT)
  BIN := $(VENV)/Scripts
else
  BIN := $(VENV)/bin
endif

.DEFAULT_GOAL := help

.PHONY: help bootstrap ingest ingest-historico ingest-socio dbt-deps dbt-seed dbt-run dbt-test dbt-build test lint fmt run clean verify-layout docs-status

help:  ## mostra esta ajuda
	@grep -hE '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

bootstrap:  ## cria venv e instala dependencias (uv se existir, senao pip)
	@if command -v uv >/dev/null 2>&1; then \
	  uv venv $(VENV) && uv pip install --python $(BIN)/python -e ".[dbt,dev]"; \
	else \
	  $(PY) -m venv $(VENV) && $(BIN)/python -m pip install -q --upgrade pip && $(BIN)/python -m pip install -e ".[dbt,dev]"; \
	fi
	@$(MAKE) dbt-deps

ingest:  ## baixa e carrega TSE do ano ANO=2026
	$(BIN)/python -m ingest.tse load --ano $(ANO)

ingest-historico:  ## baixa e carrega TSE 1998-2022
	@for a in $(ANOS_HISTORICO); do $(BIN)/python -m ingest.tse load --ano $$a || exit 1; done

ingest-socio:  ## baixa e carrega indicadores socioeconomicos (IBGE/SIDRA + Ipeadata)
	$(BIN)/python -m ingest.ibge_sidra load
	$(BIN)/python -m ingest.ipeadata load
	$(BIN)/python -m ingest.siconfi load
	$(BIN)/python -m ingest.ideb load

ingest-fotos:  ## baixa as fotos de urna, envia ao bucket e registra as URLs (F-13)
	$(BIN)/python -m ingest.fotos load --ano $(ANO)

ingest-propostas:  ## consulta a proposta de governo dos majoritarios (F-14)
	$(BIN)/python -m ingest.propostas load --ano $(ANO)

ingest-legislativo:  ## parlamentares em exercicio e atividade legislativa (F-15, F-16)
	$(BIN)/python -m ingest.legislativo load
	$(BIN)/python -m ingest.proposicoes load

verify-layout:  ## confere o header real do TSE contra ingest/layouts/tse_$(ANO).yml
	$(BIN)/python -m ingest.tse verify-layout --ano $(ANO)

dbt-deps:  ## instala pacotes dbt
	cd dbt && $(abspath $(BIN))/dbt deps

dbt-seed:  ## carrega seeds (dim_uf, dim_cargo, dim_indicador)
	cd dbt && $(abspath $(BIN))/dbt seed

dbt-run:  ## roda os modelos
	cd dbt && $(abspath $(BIN))/dbt run

dbt-test:  ## roda os testes dbt
	cd dbt && $(abspath $(BIN))/dbt test

dbt-build: dbt-deps dbt-seed dbt-run dbt-test  ## seed + run + test

test:  ## pytest (offline) + dbt test
	$(BIN)/python -m pytest -m "not network and not bigquery"
	@$(MAKE) dbt-test || echo ">> dbt test pulado (sem credenciais BigQuery)"

lint:  ## ruff check
	$(BIN)/python -m ruff check ingest tests

fmt:  ## ruff format
	$(BIN)/python -m ruff format ingest tests

run: ingest ingest-historico ingest-socio ingest-fotos ingest-propostas ingest-legislativo dbt-build  ## pipeline completo

docs-status:  ## imprime o estado das Tasks
	@cat docs/STATUS.md

clean:  ## limpa artefatos locais (nao apaga o cache de download)
	rm -rf dbt/target dbt/logs .pytest_cache .ruff_cache data/staging
