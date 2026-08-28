# ADR-018 — Site estático gerado do lake, em vez de ferramenta de BI

**Status:** Aceita · **Data:** 2026-08-28 · **Supersede:** ADR-001 · **Feature:** F-07 (reescrita)

## Contexto

A ADR-001 escolheu Power BI sobre Looker Studio em 27/08/2026, quando o projeto
ainda não tinha camada de dados pronta nem definição de distribuição. A pergunta
daquele momento era "qual ferramenta de BI". Um dia depois, com o lake fechado e o
produto batizado — **Dossiê Eleitoral** —, a pergunta virou outra: **como isto
chega às pessoas.**

Duas coisas mudaram o quadro.

### O que a apuração sobre *Publish to web* mostrou

| Limite | Consequência para um produto público |
|---|---|
| Layout mobile **não é suportado** | A maior parte do acesso no Brasil é por celular |
| Não há URL por candidato | Ninguém consegue mandar "a ficha do fulano" no WhatsApp |
| Conteúdo em iframe | O Google não indexa; quem busca o nome do candidato nunca chega |
| Exige licença **Pro** paga e liberação por **admin de tenant** | Fricção e custo recorrente |
| O modelo inteiro fica acessível a quem souber pedir | Aceitável aqui (dado público, sem CPF), mas é um fato |

O Looker Studio não resolve nada disso: tem as mesmas limitações de iframe, link e
indexação, com modelagem mais fraca. **A escolha nunca foi entre as duas
ferramentas de BI** — era entre publicar dentro de um iframe ou publicar na web.

Há ainda uma fricção específica: o e-mail de `datadubaintel.com` está no Google
Workspace. Cadastrar-se em serviços Microsoft com esse domínio cria um *tenant não
gerenciado*, e habilitar a publicação exigiria um **admin takeover com verificação
por DNS** — trabalho de infraestrutura que não entrega nada ao leitor final.

### O formato do nosso dado

Este é o argumento decisivo, e ele não é sobre ferramenta:

> **20.765 candidatos. Muda uma vez por dia.**

Esse é exatamente o perfil de **geração estática**, não de consulta ao vivo. Um
aplicativo consultando o BigQuery a cada visita pagaria query por pageview, o que
contraria a Constituição §5 (custo próximo de zero). Um site gerado uma vez por
dia e servido por CDN custa praticamente nada e escala sem teto.

## Decisão

O Dossiê Eleitoral público passa a ser um **site estático gerado a partir dos
marts**, na mesma esteira diária que já roda.

- Um gerador em Python — o stack que o projeto já tem — lê `marts` e escreve HTML
  e JSON estáticos. Sem servidor, sem cold start, sem superfície de ataque.
- Uma URL por candidato, compartilhável e indexável.
- As fotos já estão num bucket público; metade do caminho estava feita.
- Hospedagem estática com CDN.

**Nada de Flask ou framework de servidor.** Servidor só se justificaria se o dado
mudasse a cada requisição — e ele muda uma vez por dia.

## O que isto custa

Uma decisão que só tem vantagens costuma estar mal examinada. O que se perde:

- **A demonstração no stack corporativo.** Power BI é o que cliente corporativo
  compra. Um site próprio não substitui isso numa conversa comercial.
- **Interatividade de graça.** Filtro cruzado, segmentação e drill-through vêm
  prontos numa ferramenta de BI. Aqui é código nosso.
- **Iteração visual rápida.** Ajustar um visual no Power BI Desktop leva segundos.
- **Manutenção passa a ser nossa.** O frontend vira parte do repositório, com o
  custo de sempre.

A troca se sustenta porque o objetivo declarado é **alcance público**, e é
exatamente nisso que o iframe entrega menos.

## O que acontece com o que já existe

**`bi/` fica no repositório, marcado como arquivado.** São 34 arquivos, e o modelo
semântico em TMDL é um registro legível do modelo estrela — documentação
aproveitável. Apagar seria perda sem ganho; deixar sem aviso sugeriria que está
vivo. Fica com um README dizendo o que é e por que parou.

**A ADR-002 (Import mode) não é revogada — é levada ao extremo.** O raciocínio
dela era não pagar query por interação do usuário. A geração estática é a forma
mais completa disso: paga-se uma leitura por dia, e zero por visita.

**A F-07 do SPEC é reescrita**, de "hub e páginas no Power BI" para "gerador do
site estático". As sete páginas por cargo, o layout de dossiê e a regra do
comparador permanecem — mudou o meio, não o produto.

## Consequência

O que se ganha, em uma linha: o Dossiê Eleitoral passa a ser **encontrável pelo
Google e compartilhável por link** — as duas únicas formas pelas quais um produto
público de fato circula, e as duas que o iframe impedia.
