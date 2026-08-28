# CLAUDE.md — Radar Brasil

**Leia [SPEC.md](SPEC.md) antes de qualquer tarefa.**

## Regras inegociáveis de trabalho neste repo

1. **Nunca implemente algo que não esteja em uma Feature (`F-xx`) ou Task (`T-xx`) do SPEC.**
   Se precisar de algo fora do spec, proponha primeiro uma alteração no SPEC (seção 6 ou 7)
   e registre a decisão em `docs/adr/`.
2. **Trabalhe por fase.** Execute as Tasks de uma fase, rode os critérios de aceite da fase,
   e só então avance. O estado atual de cada Task está em [docs/STATUS.md](docs/STATUS.md).
3. **Toda decisão nova vira um ADR** em `docs/adr/ADR-0xx-*.md` e uma linha na tabela do SPEC §10.
4. **Toda dúvida vira uma linha** em SPEC §11 (*Perguntas em aberto*).
5. **Todo dado ausente vira uma linha** em [docs/LACUNAS.md](docs/LACUNAS.md) — nunca preencha buraco de dado.
6. **Confira todo indicador novo contra um valor conhecido de fora do pipeline**
   antes de dar por pronto. Ao menos um ano, contra um número publicado.
   Nenhum teste automático pega o erro em que o dado é extraído corretamente e o
   **rótulo** é que está errado — foi assim que o orçamento federal passou meses
   mostrando superávit onde havia déficit (L-22 / ADR-017). `dbt build` verde,
   205 testes e uma revisão de código não pegaram; conferir um número pegou.

## Convenções (SPEC §9)

- Colunas em `snake_case` pt-BR **sem acento**: `grau_instrucao`, nunca `grauInstrução`.
- Todo script de ingestão aceita `--ano` e `--dry-run`.
- **Nenhum SQL fora do dbt.** **Nenhum pandas em `marts`** — transformação acontece no BigQuery.
- Commits em pt-BR com prefixo `feat:`, `fix:`, `data:`, `docs:`, `test:`, `chore:`.
- Antes de marcar uma Task como concluída: `make test` verde **e** o critério de aceite da Feature checado.

## Layouts do TSE — a regra mais importante

O layout do `consulta_cand` **muda entre anos**. O código **não adivinha**:
`ingest/layouts/tse_{ano}.yml` declara, para cada campo canônico, a lista de nomes de coluna
aceitos naquele ano. O loader resolve contra o cabeçalho real do CSV e **falha alto** se um campo
obrigatório não resolver, apontando o `leiame.pdf` do ano.

Ao encontrar coluna inesperada:
```bash
python -m ingest.tse verify-layout --ano 2026     # mostra header real vs. layout declarado
```
Depois atualize o YAML do ano. Nunca hardcode nome de coluna em `.py`.

## Comandos

| Comando | O que faz |
|---|---|
| `make bootstrap` | cria venv, instala deps, instala pacotes dbt |
| `make ingest ANO=2026` | baixa TSE 2026 e carrega em `raw_tse` |
| `make ingest-socio` | baixa IBGE/SIDRA + Ipeadata e carrega em `raw_ibge` / `raw_ipea` |
| `make dbt-build` | `dbt seed && dbt run && dbt test` |
| `make test` | pytest + `dbt test` |
| `make run` | pipeline completo (bootstrap → ingest → dbt) |

## O que este projeto NÃO faz

Nunca escreva código, texto de tela ou comentário que:
- ranqueie políticos como "melhor/pior";
- atribua um indicador socioeconômico ao **efeito** de um mandato (só ao **período** dele);
- exponha CPF, título de eleitor ou endereço de candidato;
- use cor de partido como padrão visual (só sob toggle explícito do usuário).

Ver SPEC §0 (Constituição) e `docs/METODOLOGIA.md`.
