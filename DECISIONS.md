# Decisões de projeto

Registro das decisões técnicas e o *porquê* de cada uma, incluindo as alternativas
descartadas. Documento vivo — cada decisão nova entra com data.

---

## 1. Enquadramento: núcleo neutro com duas camadas de leitura

**Decisão.** O núcleo do sistema (ingestão + normalização + análise) é neutro: ele
descreve o que os dados dizem, sem julgamento. Por cima dele ficam duas leituras do
mesmo material:

- **Inteligência de mercado** — ajudar uma empresa a entender onde e por quanto o
  governo compra o que ela vende.
- **Transparência** — permitir que qualquer pessoa audite dispersão de preço entre
  órgãos públicos.

**Por quê.** As duas leituras precisam exatamente do mesmo pipeline: normalizar
descrição de item e comparar preço unitário. Construir um núcleo neutro evita
duplicar trabalho e deixa explícito que o dado não muda — muda a pergunta que se faz
a ele.

**Alternativa descartada.** Escolher só uma das duas. Descartada porque o custo de
suportar as duas é quase zero depois que o núcleo existe, e porque cada uma sozinha
conta uma história mais fraca.

---

## 2. Salvaguardas da camada de transparência

Acusar publicamente é fácil e irresponsável; um desvio estatístico tem muitas
explicações legítimas (urgência, quantidade, especificação diferente, região).
Portanto:

- **Linguagem factual, nunca acusatória.** O sistema relata *desvio estatístico*.
  Ele nunca afirma fraude, superfaturamento ou má-fé.
- **Agregação em CNPJ e órgão, jamais em pessoa física.** Nome e CPF de sócio são
  dado pessoal sob a LGPD; CNPJ de empresa e identificação de órgão público não são.
- **Metodologia publicada junto do resultado.** Toda marcação precisa ser auditável
  por quem discorda dela — inclusive pelo órgão marcado.

**Por quê.** Além de ser o certo, é o que torna o projeto defensável. Uma ferramenta
que aponta o dedo sem mostrar a conta não sobrevive ao primeiro contraditório.

---

## 3. Stack: Python na ingestão, Postgres, Next.js no frontend

**Decisão.** Python (ingestão, normalização, análise) → Postgres (Neon, via Vercel
Marketplace) → Next.js + TypeScript na Vercel.

**Por quê.** Duas linguagens, cada uma no que ela é padrão de mercado: Python é onde
vive o ferramental de dados; TypeScript é o que se cobra em vaga de frontend. A
divisão cobre backend e frontend numa fatia só. Postgres gerenciado tira operação de
banco do caminho — o projeto é sobre os dados, não sobre administrar servidor.

---

## 4. A API documentada do PNCP está fora do ar; usamos a interna

**Este é o trade-off mais desconfortável do projeto, e por isso está documentado.**

O PNCP expõe três superfícies HTTP:

| API | Situação |
|---|---|
| `/api/consulta/v1/…` — pública e **documentada** | 503/504 em **todas** as tentativas |
| `/api/search/` — busca **interna** do portal | 200 em ~6s, dados do minuto corrente |
| `/api/pncp/v1/…` — detalhe de compra/itens | 200, pública, sem autenticação |

**Decisão.** Descobrir compras pela `/api/search/` e buscar preços pela
`/api/pncp/v1/…`.

**Por quê.** A API documentada foi testada em duas sessões distintas (12 e 13 de
agosto de 2026), variando intervalo de datas, UF, modalidade e ano — falhou em todas,
levando de 20 a 100 segundos para retornar erro. Não é instabilidade momentânea. A
alternativa seria não ter projeto.

**O custo, declarado.** `/api/search/` é API interna, não documentada e sem contrato
público: pode mudar ou sumir sem aviso. Mitigação: **todo acesso à rede passa por um
único módulo** (`ingestao/radar/pncp.py`). Se a API documentada voltar, trocar a
fonte é mexer em um arquivo. Além disso a ingestão mantém cache local em disco, então
uma quebra da API não invalida os dados já baixados.

---

## 5. Comparar preço **homologado**, não estimado

**Decisão.** A análise do v1 compara `valorUnitarioHomologado` — o preço pelo qual o
item foi efetivamente adjudicado — e não `valorUnitarioEstimado`.

**Por quê.** O valor estimado é a expectativa do órgão antes da disputa; o homologado
é o que o dinheiro público de fato pagou. Comparar estimativas mede a qualidade da
pesquisa de preço; comparar homologados mede o resultado. O endpoint de resultados
ainda traz CNPJ, razão social e porte do fornecedor de graça, o que serve às duas
camadas de uma vez: quem ganha e com que desconto (mercado), e qual a dispersão entre
órgãos (transparência).

**Consequência.** Só entram na análise itens com resultado publicado. Itens sem
resultado ficam de fora do comparativo — o recorte precisa ser dito na interface,
para ninguém ler o número como "todas as compras".

---

## 6. Escopo do v1: uma fatia fina, ponta a ponta

**Decisão.** Distrito Federal + Pregão Eletrônico (~17.600 compras), uma única
análise (dispersão de preço do mesmo item entre órgãos), tela de busca e tela de
detalhe no ar.

**Por quê.** Uma fatia fina que funciona de ponta a ponta demonstra mais do que um
sistema amplo pela metade. O volume é grande o bastante para a análise ter sentido
estatístico e pequeno o bastante para reprocessar em minutos enquanto o pipeline
ainda está mudando.

---

## 7. Armadilhas dos dados que o pipeline precisa tratar

Levantadas na sondagem da API, todas capazes de produzir número errado em silêncio:

- **Itens cancelados vêm misturados.** `situacaoCompraItem = 3`
  (Anulado/Revogado/Cancelado) aparece na listagem normal. Entrar na média sem
  filtrar contamina o resultado.
- **`unidadeMedida` é texto livre** (`UNIDADE`, `UNI`, …). Comparar preço unitário
  sem normalizar unidade compara coisas diferentes — o erro mais perigoso do
  projeto, porque não parece erro.
- **`orcamentoSigiloso = true`** esconde o valor estimado; tratar como ausente, não
  como zero.
- **`tem_resultado` na busca não é filtrável** — o parâmetro é aceito e ignorado
  silenciosamente. A filtragem tem que ser feita do lado do cliente.

---

## 8. A busca trava em 10.000 resultados; particionamos por órgão

**O problema.** `/api/search/` corta em **offset 10.000** — o `max_result_window`
padrão do Elasticsearch. Verificado: página 200 (offset 9.950) responde normalmente,
página 201 (offset 10.000) falha de forma determinística e não adianta repetir. Como
a fatia DF + Pregão Eletrônico tem ~17.600 compras, **paginar do começo ao fim é
impossível**.

Filtrar por data resolveria, mas a API não deixa: `data_inicial` e `dataInicial`
fazem o servidor cortar a conexão, e `data_ini`/`data_fim`/`ano` são aceitos e
**ignorados em silêncio** — o total não muda. Ignorar em silêncio é pior que recusar,
porque o pipeline parece funcionar enquanto lê a fatia errada.

**Decisão.** Particionar por órgão, em dois passos:

1. Varrer o índice dentro da janela de 10.000 coletando os `orgao_id` distintos.
2. Para cada órgão, paginar suas próprias compras com `orgaos={orgao_id}` — nenhum
   órgão sozinho chega perto do teto (o maior visto tem dezenas de compras).

A união dos dois passos cobre a fatia inteira. O filtro `orgaos` aceita o **`orgao_id`
interno** (numérico, ex. `80579`), não o CNPJ — passar CNPJ retorna zero resultados
silenciosamente.

---

## 9. Não usar `ordenacao=-data`: ela não ordena

`ordenacao=-data` é aceita e **não ordena nada** — devolve datas embaralhadas
(2026-07-27, 2025-04-09, 2025-12-05 em sequência). `ordenacao=data` e
`-data_publicacao_pncp` derrubam a conexão.

**Decisão.** Não enviar `ordenacao`. O default devolve ordem de indexação crescente e
consistente (2022-11-16, 2022-11-17, 2022-11-21…).

**Por quê isso importa para a corretude, não só para a estética.** Paginação sobre
ordem instável produz item duplicado numa página e item pulado em outra, sem erro
nenhum. Ordem de indexação crescente é a mais segura aqui: documentos novos entram no
**fim** do índice e não deslocam as páginas já lidas. Ordenar por data decrescente
teria o defeito oposto — cada compra nova publicada durante a ingestão empurraria
tudo uma posição para frente.

---

## 10. A análise compara materiais, não serviços

**Decisão.** A dispersão de preço do v1 roda apenas sobre itens marcados como
material (`materialOuServico = "M"`).

**Por quê.** Nos dados reais, a descrição "Serviços de Gerenciamento de Redes de
Tecnologia da Informação e Comunicação (TIC)" aparece com valores homologados de
**R$ 6.111, R$ 25.000 e R$ 170.000**. Não é alguém pagando 27 vezes mais pela mesma
coisa: é que o escopo contratado sob esse mesmo rótulo é completamente diferente em
cada caso. A descrição de serviço não é especificação — é título.

Publicar essa comparação seria produzir um alarme falso espetacular, exatamente o
tipo de erro que a camada de transparência não pode cometer (§2). Materiais têm
descrição muito mais próxima de uma especificação real: "Caneleira", "Cabo Rede
Computador", "Disco Magnético".

**Reversível.** O filtro é uma flag (`--incluir-servicos`). Quando houver uma forma
melhor de comparar serviços — agrupar por item de catálogo em vez de texto livre, por
exemplo — o caminho já está aberto.

---

## 12. O PNCP não publica especificação — o que a análise pode afirmar mudou

**A descoberta.** A premissa original do v1 era "comparar o preço do mesmo item entre
órgãos". Ao olhar os dados reais, ela não se sustenta como estava escrita:

> "Monitor computador" aparece de **R$ 60 a R$ 18.810**.
> "Caneta Esferográfica" aparece de **R$ 0,58 a R$ 117,15**.

Os dados são internamente consistentes (unitário × quantidade = total bate), então
não é erro de cálculo. O problema é de **identidade do item**: a descrição do PNCP é
um rótulo de catálogo, não uma especificação. "Monitor computador" cobre tanto um
monitor de escritório quanto um painel profissional de grande porte.

Verificamos se havia especificação em algum outro campo. Em **3.540 itens
coletados**, estes campos vieram vazios em **100%** dos casos:
`informacaoComplementar`, `ncmNbsCodigo`, `ncmNbsDescricao`, `catalogo`,
`catalogoCodigoItem`, `categoriaItemCatalogo`. O único campo de categoria preenchido,
`itemCategoriaNome`, vale "Não se aplica" em todos.

**Não existe especificação técnica disponível nesta API.** A descrição é tudo que há.

**O que mudou na análise.**

1. **A afirmação foi reescrita.** O sistema não diz mais "preço do mesmo item". Diz
   *faixa de preço praticada dentro de uma categoria de catálogo*. É menos ambicioso
   e é o que o dado sustenta.
2. **Cerca de Tukey (1,5 × IQR).** Observações fora da faixa central saem das
   estatísticas. Elas não somem: voltam no campo
   `fora_da_faixa`, porque são justamente as que merecem olho humano.
   (Nesta base, um valor fora da cerca indica com muito mais frequência item
   diferente sob o mesmo rótulo do que preço diferente pela mesma coisa.)
3. **A ordenação deixou de ser por amplitude (máximo/mínimo).** Aquilo ordenava por
   "qual item tem o registro mais esquisito". Passou a ser o coeficiente quartílico
   de dispersão (IQR ÷ mediana), que é resistente a atípicos.
4. **A limitação é publicada junto do resultado**, no mesmo JSON e na interface — não
   escondida no rodapé.

**Efeito prático.** "Monitor computador" saiu de uma amplitude falsa de 313× para uma
mediana de R$ 869,77 com o registro de R$ 18.810 separado e sinalizado. O número
ficou menor e passou a ser verdadeiro.

---

## 13. Dispersão alta demais não é achado — é categoria que não é categoria

**O problema.** Ao rodar a análise sobre a fatia completa (9.268 linhas de item),
ordenar por dispersão colocou no topo exatamente o lixo:

| Categoria | Q1 | Q3 | Dispersão |
|---|---|---|---|
| Peça mecânica elétrica veículo automotivo | R$ 0,40 | R$ 2.419,04 | 9.856 |
| Equipamentos **diversos** para serviços profissionais | R$ 1.474 | R$ 230.351 | 8,0 |

O nome da segunda entrega o diagnóstico sozinho. Estes rótulos são baldes do
catálogo, não categorias de produto — comparar preço dentro deles não significa
nada. É o mesmo erro do §12 aparecendo com outra roupa: a métrica mudou, a
tendência de destacar o registro mais estranho continuou.

**Decisão, em duas partes.**

1. **Corte por dispersão.** Categorias com coeficiente quartílico acima de **2,0**
   saem da lista principal (89 comparáveis, 30 amplas demais). Não são apagadas:
   vão para `categorias_amplas` no JSON e são publicadas à parte — esconder o
   descartado seria escolher a dedo o que confirma a tese.
2. **A ordenação deixou de ser por dispersão.** A lista principal é ordenada por
   **força do dado** (quantos órgãos, depois quantas compras). Ordenar por dispersão
   colocava no topo justamente as categorias em que o número significa menos.

**Validação de que o pipeline está certo.** Depois do corte, os itens de maior
confiança se comportam como a realidade manda: **gasolina** aparece com mediana de
R$ 5,48 e dispersão de **0,08**; **óleo diesel**, R$ 5,61 e 0,22. Commodity tem
preço apertado — e é o que o sistema mostra. Se um combustível aparecesse com
dispersão alta, o erro estaria no código, não no governo.

---

## 14. Mudança de recorte: Distrito Federal → Tocantins

**Motivo inicial, prático:** o autor mora em Tocantins, e um projeto sobre compras
públicas da própria região é mais defensável e mais útil do que um sobre a capital.

**O que a medição mostrou — e foi uma surpresa boa.** Tocantins não é só viável, é
um recorte *melhor* para esta análise:

| | DF | TO |
|---|---|---|
| Compras disponíveis (pregão eletrônico) | 17.609 | 10.770 |
| Categorias comparáveis | 89 | **109** |
| Descartadas por serem amplas demais | 30 | **6** |
| Órgãos distintos | 104 | **307** |
| Maior amostra numa categoria | 62 compras | **436 compras, 26 órgãos** |

A razão é o perfil de compra. O DF concentra órgãos federais comprando TI e
mobiliário — onde "Monitor computador" vira balde. Tocantins é dominado por
**municípios comprando alimento e material básico**: arroz, açúcar, carne, legume,
verdura. Arroz é arroz; monitor não é monitor. Categorias homogêneas por natureza
dão comparação honesta, e a pulverização em 307 órgãos dá massa estatística.

**Como a troca foi feita:** parametrizando, não trocando texto. O pipeline já
aceitava `--uf`; os arquivos passaram a carregar a UF no nome
(`compras-{uf}.jsonl`), e a análise passou a gravar um bloco `recorte` deduzido dos
próprios dados. **A interface lê a UF do JSON** — não há nome de estado escrito no
código do frontend. Trocar de estado é reprocessar e publicar.

### 14.1. Efeito de seleção: o agrupamento favorece a descrição vaga

Ao trocar de estado apareceu um detalhe que não existia no DF: 13% das descrições
de Tocantins são especificações completas de verdade ("ARROZ AGULHINHA TIPO 1 —
Tipo 1. Constituídos de grãos inteiros, com aspecto, sabor e cheiro próprios…",
456 caracteres).

Isso parecia enfraquecer o §12 — mas mediu-se o oposto. **Entre as 109 categorias
efetivamente publicadas, 95% das descrições têm 40 caracteres ou menos** (mediana de
14: "Ovo", "Cola", "Café").

A explicação é um efeito de seleção: quando um órgão escreve a especificação
inteira, aquele item deixa de coincidir com o de qualquer outro e **não alcança o
mínimo de 3 órgãos**. Descrição detalhada é automaticamente eliminada pelo próprio
critério de agrupamento. Ou seja, o sistema publica justamente as descrições mais
genéricas — e isso está dito na metodologia, porque é uma limitação estrutural, não
um detalhe.

**Efeito colateral técnico:** as descrições longas geravam slugs de 300+ caracteres
e estouravam o limite de caminho do Windows durante a geração das páginas. O slug
passou a ser truncado em 60 caracteres com um hash curto da chave completa,
preservando unicidade.

---

## 15. Licitações abertas: a camada rasa, e por que ela é rasa

**O que é.** Uma segunda leitura sobre a mesma fonte: *o que está aberto agora*,
para quem vende ao governo. Ela para no nível da compra e não desce ao item.

**Por que rasa, e por que isso não é preguiça.** A análise de preço custa ~4,4
requisições por compra (uma para listar itens, mais uma por item com resultado).
Fazer isso para uma lista que precisa ser *recente* e *ampla* seria pagar caro
por profundidade que esta pergunta não usa: quem procura oportunidade quer saber
o que abriu e quando fecha, não o preço unitário histórico. Largura e
profundidade competem pelo mesmo orçamento de requisições, e cada camada escolhe
seu lado.

**Só um valor de `status` funciona.** `status=recebendo_proposta` filtra de
verdade — 457 de 34.353 no Tocantins. Todos os outros valores testados, inclusive
inventados (`abertas`, `encerrado`, `em_andamento`), são aceitos e **ignorados em
silêncio**, devolvendo a base inteira. É a mesma armadilha do §9: o parâmetro não
recusa, ele mente.

**Credenciamento não é disputa com prazo.** Responde por 188 dos 457 editais
abertos (41%) e fica aberto por meses ou anos — é cadastro permanente, não pregão
com data para fechar. Misturá-lo numa lista ordenada por urgência criaria pressão
falsa. Fica separado em aba própria e marcado, nunca escondido: quem procura
credenciamento precisa achá-lo.

**Prazo é calculado no navegador, não no build.** A página guarda a data absoluta
de fechamento; o "encerra em 4 dias" é recalculado a cada visita. Gravar o número
de dias no HTML estático produziria uma página que mente a partir do dia
seguinte. A data da coleta aparece no topo, junto do aviso de que editais
publicados depois dela não estão listados.

**A incompletude vai no arquivo, não só no log.** A coleta grava quantos editais
a API disse existir e quantos conseguiu ler. Se as duas contas divergirem, a
interface diz "lista incompleta" com os dois números. Uma primeira execução leu
348 de 450 — apresentar aquilo como se fosse tudo seria uma mentira silenciosa.

**O link do portal foi verificado, não deduzido.** O caminho correto é
`/app/compras/{cnpj}/{ano}/{seq}`. O palpite óbvio (`/app/editais/`) e o campo
`item_url` que a própria busca devolve (`/compras/{cnpj}/{ano}/{seq}`) **não
funcionam** — o segundo dá 404. Publicar link quebrado em ferramenta de
oportunidade seria pior que não publicar link.

---

## 11. Mediana e intervalo interquartil, não média e desvio padrão

Preço de compra pública tem cauda longa: um contrato atípico distorce a média e o
desvio padrão, mas quase não move a mediana e o IQR. Além disso a comparação é
**agregada por órgão antes de comparar** — sem isso, um órgão que comprou o mesmo
item 40 vezes dominaria a estatística, e o resultado descreveria aquele órgão em vez
do conjunto.
