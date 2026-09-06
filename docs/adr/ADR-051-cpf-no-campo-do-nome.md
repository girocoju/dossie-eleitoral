# ADR-051 — CPF digitado no campo do nome do doador

**Data:** 06/09/2026
**Situação:** aceito
**Origem:** falha do teste `assert_cpf_de_doador_nunca_em_claro` na carga de 06/09/2026

## O que aconteceu

A atualização do lake parou no `dbt build`. Um teste falhou:

```
assert_cpf_de_doador_nunca_em_claro ... FAIL 1
```

O teste procura texto com a forma de CPF — onze dígitos — nas colunas de texto
do financiamento de campanha. Achou **uma ocorrência, no campo `nome_doador`**.

Conferido sem exibir o valor: é **CPF válido pelo dígito verificador**, de
doador pessoa física, entre 82.710 lançamentos do arquivo novo de prestação de
contas.

Não é a coluna de CPF vazando — essa a ingestão já hasheia desde a ADR-020. É
alguém que, ao preencher a prestação de contas, escreveu o CPF onde vai o nome.
O TSE publica o arquivo como recebeu.

## O que NÃO aconteceu

**Nada foi exposto.** O `dbt build` é etapa fatal do `atualizar.bat`: ele
interrompeu a atualização antes do `gerar_site`, e o site no ar seguiu com os
dados da carga anterior. Conferido no `doadores.json` publicado: 31.799 linhas,
zero campos com onze dígitos.

Este é o teste fazendo exatamente o que foi escrito para fazer. O comentário no
próprio arquivo já dizia: *"é a única falha deste projeto que fere alguém que não
se candidatou a nada"*.

## Decisão

Em `stg_tse__financiamento`, nome com a forma exata de CPF vira **NULL**, e uma
coluna nova, `nome_era_cpf`, registra que isso aconteceu.

**A doação não é descartada.** Valor, data, candidatura e a chave do doador
continuam — são fato de interesse público, e `sk_doador` vem do CNPJ ou do hash
do CPF, nunca do nome, então a agregação não muda. O que sai é apenas o
identificador da pessoa física.

**Não há validação de dígito verificador na regra**, de propósito. Onze dígitos
no lugar do nome já bastam para não publicar: se for CPF, é dado pessoal; se não
for, é lixo que não ajuda ninguém a identificar o doador. Nos dois casos a
resposta certa é a mesma, e uma regra que depende do dígito verificador falharia
justamente no CPF digitado errado.

## O que quase virou um segundo defeito

`fct_doador_candidatura` escolhe o nome mais representativo com
`array_agg(nome_doador order by valor desc limit 1)`. O `ARRAY_AGG` do BigQuery
**lança erro quando um elemento é nulo** — a correção de privacidade teria
quebrado o mart por causa de uma linha em 82.710. Resolvido com `ignore nulls`.

E na página de doadores o nome ausente virava célula em branco, que se lê como
defeito da página. Passa a mostrar travessão.

## Consequências

- A regra vale para as próximas cargas, não só para esta linha.
- O teste continua sendo a última linha de defesa: se a limpeza quebrar, ele
  volta a falhar e a atualização volta a parar.
- Fica registrado que a etapa fatal do `atualizar.bat` pagou por si. Sem ela, o
  CPF de um cidadão brasileiro estaria hoje num site público, e ninguém saberia.
