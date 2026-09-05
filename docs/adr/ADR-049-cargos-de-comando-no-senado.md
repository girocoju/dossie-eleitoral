# ADR-049 — Presidência e Mesa no Senado saem de outra rota

**Data:** 05/09/2026
**Situação:** aceito
**Fecha:** L-30 · **Feature:** F-31

## Contexto

A L-30, aberta um dia antes (ADR-048), dizia que o Senado não publica papel de
comando. A medição sustentava: em 7.226 vínculos de
`/senador/{codigo}/comissoes`, **zero** presidências, zero relatorias e nenhuma
Mesa Diretora. A conclusão foi que a ficha de senador não poderia dizer quem
presidiu um colegiado, e que fechar a lacuna exigiria raspar HTML renderizado
por JavaScript — fora do custo quase-zero do projeto.

**A medição estava certa e a conclusão estava errada.** O dado existe, em outra
rota da mesma API:

```
/senador/{codigo}/cargos.json
```

Ela devolve PRESIDENTE, VICE-PRESIDENTE (com ordinal), RELATOR, SECRETÁRIO,
CORREGEDOR e COORDENADOR, com colegiado, data de início e data de fim. E devolve,
junto, **colegiados que a outra rota não conhece** — entre eles a Mesa Diretora
do Congresso Nacional e a Comissão Diretora do Senado Federal.

O erro foi de método, não de leitura: procurei a Mesa por rotas plausíveis
(`composicao/mesa`, `plenario/lista/mesa`, `composicaoMesa`, `senador/lista/mesa`
— todas vazias) e não pelo caminho que a própria API já usava para tudo o mais,
que é pendurar o recurso no parlamentar.

## Decisão

**Coletar as duas rotas e uni-las na ingestão**, com `origem_do_vinculo` dizendo
de qual cada linha veio:

| origem | o que traz |
|---|---|
| `comissoes` | quem **sentou** — Titular, Suplente, Nato |
| `cargos` | quem **comandou** — Presidente, Vice, Relator, Secretário |

**União, e não cruzamento.** Juntar por chave manteria só o que a primeira rota
conhece e perderia exatamente o assento mais visível do país: Davi Alcolumbre
preside o Senado, e a Mesa não existe na lista de comissões.

Resultado: **804 cargos de comando**, 61 vínculos de Mesa onde havia zero, e os
colegiados exibíveis subiram de 5.514 para 5.960.

## O erro que a primeira versão do modelo publicou

Com as duas rotas unidas, `papel_principal` (o de maior peso da trajetória) e
`em_curso` (algum período aberto) passaram a se combinar de um jeito falso.

Um senador que presidiu a CDH em 2015 e segue titular dela hoje tem os dois
fatos: presidência encerrada, titularidade aberta. `logical_or(em_curso)` é
verdadeiro, `papel_principal` é PRESIDENTE — e a ficha diria **"Presidente da
CDH, em curso"**.

A conferência pegou: a CDH apareceu com **cinco presidentes simultâneos**, a CAE
com quatro, a CE com cinco.

São agora dois campos:

```
papel_atual       o de maior peso entre os períodos ABERTOS; NULO se nenhum está
papel_principal   o de maior peso de toda a trajetória ali
```

A tela mostra `papel_atual` ao lado de "em curso". É o nulo que impede a
afirmação falsa.

Mesma disciplina nas contagens: `qt_periodos` conta apenas **designações**, e o
comando tem contador próprio (`qt_cargos`). Somar as duas produziria "designado
4 vezes" onde houve duas designações e duas presidências.

## Duas armadilhas menores da fonte

**A comissão de medida provisória.** A rota de cargos escreve "Comissão Mista da
Medida Provisória nº 1154", que contém "Comissão Mista". Sem uma regra da MPV
testada antes, toda comissão de MPV viraria mista comum — 154 vínculos afogando
a ficha com o que na Câmara já é excluído por ser rotina (ADR-044).

**A caixa alta.** `/comissoes` escreve "Titular"; `/cargos` escreve "PRESIDENTE".
Na mesma coluna da ficha, a caixa alta é lida como ênfase — que não existe no
dado. O papel é normalizado na tela, e só o que veio todo em maiúscula: o que a
fonte escreveu bem ("Relator da Receita") passa intacto.

## Conferência (Regra 6)

A invariante mais forte que este dado admite: **em cada colegiado, num dado
momento, há exatamente uma presidência**. Se a coleta duplicasse linhas ou
arrastasse mandato encerrado como vigente, o número passaria de um.

Medido em 05/09/2026 sobre `papel_atual = 'PRESIDENTE'`: **18 colegiados
permanentes e a Mesa, um presidente cada, zero duplicados.** E os nomes são
públicos e conferíveis — Davi Alcolumbre na Mesa e na Comissão Diretora, Otto
Alencar na CCJ, Damares Alves na CDH, Renan Calheiros na CAE, Flávio Bolsonaro
na CSP.

Cinco colegiados não têm presidência atual publicada (CMO, CCDD, CDD, CMCVM), e
um a tem sem que possamos exibi-la: a presidência aberta da CRA é de Zequinha
Marinho, cuja identidade casa de forma **ambígua** com o cadastro eleitoral. Ele
não entra — que é o comportamento correto, e é o resíduo honesto da L-28.

## Consequências

- A ficha de senador passou a dizer quem presidiu, e quem preside.
- A Mesa Diretora entrou no dado.
- Fica o precedente: **medir a ausência numa rota não prova a ausência na
  fonte.** A L-30 nasceu de uma medição correta sobre o endpoint errado, e
  sobreviveu um dia porque a medição parecia conclusiva demais para ser
  questionada.
- A L-28 e a L-30 fecharam pelo mesmo tipo de motivo: não porque a fonte
  melhorou, mas porque a premissa da lacuna não se sustentava.
