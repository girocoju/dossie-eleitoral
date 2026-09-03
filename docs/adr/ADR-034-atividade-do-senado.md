# ADR-034 — Atividade legislativa do Senado, com o mesmo rigor da Câmara

**Status:** Aceita · **Data:** 2026-09-02 · **Relacionada:** L-20 (fechada), L-25 (nova), F-16, ADR-015, ADR-031

## Contexto

A F-16 cobria só a Câmara. Os 81 senadores tinham a ponte de identidade e
apareciam em `dim_parlamentar`, mas nenhuma proposição deles existia no projeto —
e **42 deles são candidatos em 2026**, um deles a presidente.

A L-20 recusava fechar isso mal, e a razão dela era correta: sem equivalente ao
filtro `proponente` da Câmara, um senador com 200 assinaturas de apoio apareceria
ao lado de um deputado com 200 projetos próprios, na mesma coluna e com o mesmo
rótulo.

## A sondagem derrubou três atalhos

**1. O endpoint que traz a resposta pronta está morto.**
`/senador/{cod}/autorias` devolve `IndicadorAutorPrincipal` numa chamada por
senador — oito vezes mais barato. Seus próprios metadados trazem
`DataDesativacaoCompleta: 2026-02-01`, data já vencida. Ele ainda responde, e é
exatamente por isso que é perigoso: a seção apodreceria em silêncio no dia em que
saísse do ar.

**2. Ler o primeiro nome da string erra 1,6%.** O substituto traz a autoria como
texto corrido. Nas 445 autorias de Flávio Bolsonaro: 438 acertos e 7 erros, todos
`"Líder do PL Flávio Bolsonaro"` — título que não é "Senador". Remendar o regex
convida "Líder do Governo", "Presidente da Comissão" e o que mais vier.

**3. `RQI` não é "Requerimento de Informação".** Classificar pelo formato da sigla
o poria em fiscalização. A lista oficial diz **"Requerimento da Comissão de
Serviços de Infraestrutura"** — rito de comissão. O mapeamento das classes saiu
das 184 siglas oficiais, com descrição, e não do palpite.

## Decisão

Usar `documento.autoria[].ordem` do endpoint suportado. **`ordem = 1` é o autor
principal**, validado contra a flag oficial do endpoint antigo:

| amostra | resultado |
|---|---|
| 25 primeiras autorias | 24 concordam, 0 divergem, 1 sem par |
| 12 "Sim" + 12 "Não", sorteadas | 24 concordam, 0 divergem |

48 comparações nas duas direções, nenhuma divergência.

### O custo, e o índice que o torna pago uma vez

A autoria estruturada só existe no **detalhe** de cada processo. São 57.156
autorias entre os 81 senadores, mas apenas **30.234 processos únicos** — o mesmo
processo aparece na lista de cada coautor, e um detalhe resolve todos (reuso de
1,89×).

Um índice em disco guarda o que já foi extraído. A primeira carga levou ~28
minutos; a seguinte foi instantânea. Sem ele, a atualização diária refaria tudo.

### As mesmas quatro classes, e nenhum total

Espelha `fct_atividade_legislativa` até na quebra por legislatura — que é de
quatro anos e vale para as duas casas, já que senador serve duas seguidas.

**Não existe linha "total"**, pelo mesmo motivo da Câmara: numa amostra de quatro
senadores havia 1.445 requerimentos para 242 projetos de lei. Somar compara
volume de rito com produção normativa.

### Os dois blocos nunca se comparam

Ficam lado a lado na ficha, e a tela diz que não se comparam. Deputado e senador
não propõem as mesmas coisas nem no mesmo volume; qualquer soma ou placar entre
as casas seria invenção.

## Uma lacuna nova, dita na tela

**Relatoria vem sempre vazia** — zero linhas em 57.170. No Senado o parecer é
documento dentro da tramitação, não matéria com autoria própria:
`/processo?sigla=PAR&ano=2025` devolve zero. Na Câmara o parecer é proposição e
por isso aparece lá.

Um senador relata constantemente, e concluir que ele não relatou seria falso. O
bloco **diz que a ausência é da fonte, não da pessoa** (ADR-031). Registrado como
L-25.

## Consequências

- 80 senadores com atividade, **28.600 proposições como autor principal**.
- 42 candidatos de 2026 ganham o bloco, incluindo um a presidente.
- A ingestão entra na atualização diária custando poucas requisições, graças ao
  índice.
