-- Schema do radar de licitações.
--
-- Modelagem deliberadamente rasa: três tabelas, sem normalizar órgão e fornecedor
-- em dimensões próprias. A razão é que os dados do PNCP são uma cópia analítica
-- somente-leitura, reconstruída a cada ingestão. Normalizar aqui traria os custos
-- de junção sem o benefício de integridade que normalização existe para dar.

DROP TABLE IF EXISTS item_resultado;
DROP TABLE IF EXISTS compra;
DROP TABLE IF EXISTS analise_item;

CREATE TABLE compra (
    numero_controle_pncp  TEXT PRIMARY KEY,
    orgao_cnpj            TEXT NOT NULL,
    orgao_nome            TEXT,
    unidade_administrativa TEXT,
    uf                    CHAR(2),
    municipio             TEXT,
    esfera                TEXT,
    poder                 TEXT,
    modalidade_id         INTEGER,
    modalidade_nome       TEXT,
    ano                   INTEGER,
    objeto                TEXT,
    data_publicacao       TIMESTAMPTZ
);

CREATE INDEX idx_compra_orgao ON compra (orgao_cnpj);
CREATE INDEX idx_compra_uf_ano ON compra (uf, ano);

-- Uma linha por resultado homologado de item. É o grão da análise.
CREATE TABLE item_resultado (
    id                        BIGSERIAL PRIMARY KEY,
    numero_controle_pncp      TEXT NOT NULL REFERENCES compra (numero_controle_pncp),
    numero_item               INTEGER NOT NULL,

    -- Texto como veio e texto normalizado convivem de propósito: o normalizado
    -- agrupa, o original é o que se mostra ao usuário. Guardar só o normalizado
    -- tornaria impossível auditar a normalização depois.
    descricao_original        TEXT,
    descricao_normalizada     TEXT NOT NULL,
    unidade_original          TEXT,
    unidade_normalizada       TEXT,
    chave_item                TEXT NOT NULL,

    material_ou_servico       CHAR(1),
    quantidade                NUMERIC(18, 4),

    -- NUMERIC, nunca FLOAT: dinheiro em ponto flutuante acumula erro de
    -- arredondamento, e aqui os valores são somados e comparados.
    valor_unitario_homologado NUMERIC(18, 4) NOT NULL,
    valor_unitario_estimado   NUMERIC(18, 4),   -- NULL quando orçamento sigiloso
    valor_total_homologado    NUMERIC(18, 4),

    fornecedor_cnpj           TEXT,
    fornecedor_nome           TEXT,
    fornecedor_porte_id       INTEGER,
    data_resultado            DATE
);

CREATE INDEX idx_item_chave ON item_resultado (chave_item);
CREATE INDEX idx_item_fornecedor ON item_resultado (fornecedor_cnpj);
CREATE INDEX idx_item_compra ON item_resultado (numero_controle_pncp);

-- Busca textual em português sobre a descrição original, para a tela de busca.
CREATE INDEX idx_item_busca ON item_resultado
    USING GIN (to_tsvector('portuguese', coalesce(descricao_original, '')));

-- Resultado pré-calculado da análise. É cache de leitura: pode ser reconstruído
-- inteiro a partir de item_resultado, e a tela não paga o custo do agrupamento.
CREATE TABLE analise_item (
    chave_item        TEXT PRIMARY KEY,
    descricao         TEXT NOT NULL,
    descricao_exemplo TEXT,
    unidade           TEXT,
    observacoes       INTEGER NOT NULL,
    orgaos            INTEGER NOT NULL,
    preco_mediano     NUMERIC(18, 4) NOT NULL,
    preco_minimo      NUMERIC(18, 4),
    preco_maximo      NUMERIC(18, 4),
    q1                NUMERIC(18, 4),
    q3                NUMERIC(18, 4),
    amplitude         NUMERIC(10, 2),
    comparativo       JSONB NOT NULL
);

CREATE INDEX idx_analise_amplitude ON analise_item (amplitude DESC);
