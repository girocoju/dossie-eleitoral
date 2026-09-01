# ADR-031 — A ausência de um indicador é dita na ficha, não só respeitada

**Status:** Aceita · **Data:** 2026-09-01 · **Relacionada:** ADR-028, ADR-029, L-06, Regra 5

## Contexto

A Regra 5 do projeto proíbe preencher buraco de dado, e `fct_mandato_indicador`
a cumpre: onde a série não alcança a janela do mandato, o par mandato × indicador
simplesmente não existe. A ficha então **omitia a linha, sem dizer que omitiu**.

Em 01/09/2026 o próprio dono do projeto perguntou por que a ficha do Lula não
mostrava desemprego nos mandatos de 2003–2006 e 2007–2010. A resposta está em
`docs/LACUNAS.md` (L-06): a PNAD Contínua começa em 2012, e emendá-la com a PNAD
antiga criaria uma quebra metodológica que seria lida como fato.

Se quem construiu o projeto precisou perguntar, o leitor também precisaria — e
não tem onde procurar. Diante de uma linha ausente, três leituras são possíveis:
não há dado, o dado foi escondido, ou o site está pela metade. **Duas delas são
falsas e nenhuma é desmentida pela tela.**

Pior: a página de metodologia afirmava que *"onde a série termina, a ficha fica
sem o indicador — e diz isso"*. A ficha não dizia. Era a mesma categoria de
problema do título que nomeava um mandato só (ADR-028): uma afirmação que o
produto não cumpre.

## Decisão

Cada bloco de mandato ganha, ao pé da tabela, a lista do que **não** está lá e
por quê:

> **Sem dado para esta janela:** **Desemprego** e **Rendimento do trabalho** (a
> série começa em 2012) · **IDHM** (a série 1991–2010 não alcança dois anos dentro
> desta janela). Nada foi estimado para cobrir o intervalo.

### Sai do dado, não de texto escrito à mão

O modelo `fct_mandato_indicador_ausente` cruza os indicadores **aplicáveis àquele
cargo** (mesma regra do ADR-029 — não faz sentido dizer a um presidente que falta
o orçamento do estado) com o alcance real de cada série **na unidade daquele
mandato**, e classifica o motivo:

| motivo | quando |
|---|---|
| `serie_comeca_depois` | a série começa depois do fim do mandato |
| `serie_termina_antes` | já tinha terminado antes de o mandato começar |
| `serie_nao_cobre_a_janela` | alcança, mas com menos de dois anos com dado — e dois é o mínimo para haver variação |
| `sem_serie_para_a_unidade` | a fonte não publica aquela série para aquela UF |

Como sai do alcance real, a nota nunca fica desatualizada: quando o IBGE
publicar 2026, a nota some sozinha do bloco que ela cobria.

### A derivação fica no dbt

"Este indicador não existe para este mandato, e o motivo é o alcance da série" é
afirmação sobre o **dado**, não sobre a apresentação — e a convenção do projeto é
nenhum SQL fora do dbt. A tela só formata e nomeia.

### O rótulo segue o ente governado

A nota usa o mesmo resolvedor da tabela (ADR-029): numa ficha presidencial ausente
lê-se "PIB do Brasil", não "PIB do estado". Rótulo falso continua falso quando o
que se descreve é uma ausência.

## Consequências

- A janela de mandato mais antiga passa a ter uma linha a mais de texto. É onde a
  pergunta nasce, e é onde a resposta faz falta.
- Mandatos recentes quase não mostram a nota: as séries alcançam.
- Nenhum mandato fica sem bloco onde a nota não caberia — medido em 01/09/2026:
  dos 198 mandatos com alguma ausência, **zero** estão sem nenhum indicador
  presente.
- A frase de cada motivo é agrupada, não repetida por indicador: "Desemprego e
  Rendimento do trabalho (a série começa em 2012)" se lê; a mesma frase duas
  vezes, não.
