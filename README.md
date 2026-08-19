# Radar de Licitações

Ingestão, normalização e análise de contratações públicas do **PNCP** (Portal
Nacional de Contratações Públicas), com uma interface que mostra a faixa de preço
praticada por categoria de item entre órgãos públicos. O recorte atual é
**Tocantins**, mas a UF é um parâmetro do pipeline — a interface lê o recorte dos
próprios dados, sem nome de estado escrito no código.

O núcleo é neutro — ingere, normaliza e compara. Sobre ele ficam duas leituras do
mesmo dado: **inteligência de mercado** (onde e por quanto o governo compra) e
**transparência** (como o preço varia entre órgãos).

> **O que este projeto não afirma.** Ele não aponta superfaturamento nem
> irregularidade. O PNCP não publica especificação técnica de item, então a
> comparação é entre rótulos de catálogo, não entre produtos idênticos. Isso está
> dito na interface, não escondido no rodapé. Veja [DECISIONS.md](DECISIONS.md) §12.

## Estrutura

```
ingestao/          Python — pipeline de dados
  radar/
    pncp.py        único ponto de acesso à rede (cache em disco + retry)
    ingest.py      varredura da fatia → JSONL bruto
    normalizar.py  texto livre → chave de agrupamento
    analise.py     dispersão de preço, com cerca de atípicos
    segmentos.py   classificação por segmento de mercado
    abertos.py     editais com proposta em aberto (camada rasa)
    carregar.py    JSONL → Postgres
    schema.sql
  testes/
web/               Next.js 16 + TypeScript + Tailwind
  app/             busca, detalhe do item, licitações abertas, metodologia
  lib/dados.ts
DECISIONS.md       decisões técnicas e o porquê de cada uma
```

## Rodando

Requer [uv](https://docs.astral.sh/uv/) e Node 20+.

```bash
# 1. ingestão (a API do PNCP é instável — o cache torna a retomada barata)
cd ingestao
uv sync
uv run python -m radar.ingest --uf TO --limite 2500

# 2. normalização e análise (os arquivos carregam a UF no nome)
uv run python -m radar.normalizar --uf TO
uv run python -m radar.analise --uf TO

# 3. licitações abertas (opcional; sem cache, sempre busca do zero)
uv run python -m radar.abertos --uf TO

# 4. interface
cd ../web
npm install
npm run dev          # copia a análise para web/data/ automaticamente
```

Testes: `uv run python -m pytest` (em `ingestao/`).

### Postgres (opcional no v1)

O `schema.sql` e o carregador estão prontos. Com um `DATABASE_URL` definido:

```bash
uv run python -m radar.carregar
```

## Decisões que valem ler antes do código

- A API **documentada** do PNCP está fora do ar; a ingestão usa a API interna de
  busca do portal, isolada num módulo só para que a troca seja barata (§4).
- A busca trava em 10.000 resultados — a cobertura completa da fatia sai
  particionando por órgão (§8).
- `ordenacao=-data` é aceita e **não ordena**; paginar sobre ela geraria duplicata
  e buraco silenciosos (§9).
- A comparação usa o preço **homologado**, não o estimado (§5).
- Serviços ficam de fora: a descrição deles é título, não escopo (§10).
- O PNCP não publica especificação de item — o que a análise pode afirmar foi
  reescrito por causa disso (§12).
- Dispersão alta é sintoma de categoria-balde, não achado: entra corte e a
  ordenação passa a ser por força do dado (§13).
- O recorte é Tocantins, e a medição mostrou que ele é estatisticamente melhor que
  o Distrito Federal para esta análise — além de um efeito de seleção que faz o
  agrupamento favorecer descrições genéricas (§14).
- A camada de licitações abertas é rasa de propósito, e só um valor de `status`
  filtra de verdade na API — os outros são aceitos e ignorados (§15).

Cada uma está justificada em [DECISIONS.md](DECISIONS.md).

## Fonte

Dados abertos do [PNCP](https://pncp.gov.br). Este é um projeto de estudo, sem
vínculo com o Portal ou com qualquer órgão público.
