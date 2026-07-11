-- ============================================================================
-- schema.sql — ANEEL MMGD (Micro e Minigeração Distribuída) local warehouse
-- MEx Energia · scoobiii
-- ============================================================================
-- Design goals:
--   1. mmgd_raw     : landing zone, 1:1 with source CKAN datastore (schema-flex)
--   2. mmgd_fato     : typed/classified fact table (business rules applied)
--   3. vw_*          : pre-aggregated views for the treemap / dashboards
--   4. mmgd_vector_docs : text+metadata rows ready for a future embedding pass
--                         (RAG for a non-LLM agent / fine-tuning corpus)
-- ============================================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- 1. RAW LANDING ZONE
-- Kept schema-flexible (TEXT everywhere) because ANEEL's CKAN field names
-- vary slightly between dataset revisions. The ETL introspects the live
-- datastore schema (`datastore_search?limit=0`) and maps columns by keyword,
-- rather than hardcoding brittle exact names.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mmgd_raw (
    row_id            INTEGER PRIMARY KEY AUTOINCREMENT,
    source_resource_id TEXT NOT NULL,
    ingested_at       TEXT NOT NULL DEFAULT (datetime('now')),
    raw_json          TEXT NOT NULL      -- full original record, verbatim, as JSON
);

CREATE INDEX IF NOT EXISTS idx_mmgd_raw_resource ON mmgd_raw(source_resource_id);

-- ---------------------------------------------------------------------------
-- 2. FACT TABLE — typed columns + business-rule classification applied
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mmgd_fato (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_row_id          INTEGER REFERENCES mmgd_raw(row_id),

    -- identity / geography
    uf                  TEXT,
    municipio           TEXT,
    cod_ibge            TEXT,
    distribuidora       TEXT,

    -- technical
    fonte_bruta         TEXT,             -- original text from source
    fonte_norm          TEXT,             -- normalized: UFV | EOL | CGH | UTE | OUTRA
    potencia_kw         REAL,
    data_conexao        TEXT,             -- ISO date, when parseable

    -- regulatory classification (see regras_negocio.md)
    modalidade_bruta    TEXT,
    modalidade_norm      TEXT,            -- GERACAO_PROPRIA | AUTOCONSUMO_REMOTO |
                                           -- GERACAO_COMPARTILHADA | MUC | EMUC | INDEFINIDA
    classe_consumo      TEXT,             -- Residencial | Comercial | Industrial | Rural | Poder Público | ...
    faixa_regulatoria   TEXT,             -- MICROGERACAO | MINIGERACAO | INDEFINIDA
    faixa_potencia_mex  TEXT,             -- bucket used for MEx BESS/800VDC targeting (see regras_negocio.md)

    -- quality flags
    is_outlier          INTEGER DEFAULT 0,  -- 1 if potencia_kw is null/zero/implausible

    ingested_at         TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_fato_uf       ON mmgd_fato(uf);
CREATE INDEX IF NOT EXISTS idx_fato_fonte    ON mmgd_fato(fonte_norm);
CREATE INDEX IF NOT EXISTS idx_fato_modal    ON mmgd_fato(modalidade_norm);
CREATE INDEX IF NOT EXISTS idx_fato_faixa    ON mmgd_fato(faixa_regulatoria);

-- ---------------------------------------------------------------------------
-- 3. AGGREGATION VIEWS — feed the treemap / dashboard directly
-- ---------------------------------------------------------------------------
DROP VIEW IF EXISTS vw_totais_uf;
CREATE VIEW vw_totais_uf AS
SELECT uf,
       COUNT(*)                    AS qtd_empreendimentos,
       ROUND(SUM(potencia_kw)/1000.0, 3) AS potencia_total_mw,
       ROUND(AVG(potencia_kw), 2)  AS potencia_media_kw
FROM mmgd_fato
WHERE is_outlier = 0
GROUP BY uf
ORDER BY potencia_total_mw DESC;

DROP VIEW IF EXISTS vw_totais_fonte;
CREATE VIEW vw_totais_fonte AS
SELECT fonte_norm,
       COUNT(*)                    AS qtd_empreendimentos,
       ROUND(SUM(potencia_kw)/1000.0, 3) AS potencia_total_mw
FROM mmgd_fato
WHERE is_outlier = 0
GROUP BY fonte_norm
ORDER BY potencia_total_mw DESC;

DROP VIEW IF EXISTS vw_totais_uf_fonte;
CREATE VIEW vw_totais_uf_fonte AS
SELECT uf, fonte_norm,
       COUNT(*) AS qtd_empreendimentos,
       ROUND(SUM(potencia_kw)/1000.0, 3) AS potencia_total_mw
FROM mmgd_fato
WHERE is_outlier = 0
GROUP BY uf, fonte_norm
ORDER BY uf, potencia_total_mw DESC;

DROP VIEW IF EXISTS vw_totais_modalidade;
CREATE VIEW vw_totais_modalidade AS
SELECT modalidade_norm,
       COUNT(*) AS qtd_empreendimentos,
       ROUND(SUM(potencia_kw)/1000.0, 3) AS potencia_total_mw
FROM mmgd_fato
WHERE is_outlier = 0
GROUP BY modalidade_norm
ORDER BY potencia_total_mw DESC;

DROP VIEW IF EXISTS vw_faixa_mex;
CREATE VIEW vw_faixa_mex AS
-- the slice MEx Energia actually cares about: minigeração de médio/alto porte,
-- candidata natural a barramento 800VDC + BESS (cargas de alta densidade)
SELECT uf, faixa_potencia_mex,
       COUNT(*) AS qtd_empreendimentos,
       ROUND(SUM(potencia_kw)/1000.0, 3) AS potencia_total_mw
FROM mmgd_fato
WHERE is_outlier = 0
GROUP BY uf, faixa_potencia_mex
ORDER BY potencia_total_mw DESC;

-- ---------------------------------------------------------------------------
-- 4. VECTOR-READY DOCS — for a future RAG agent (non-LLM embedding model,
--    e.g. sentence-transformers / bge-small, indexed with sqlite-vec or
--    exported to a vector store). Each row = one retrievable "chunk".
--    Embeddings are NOT computed here — this table only stores the text +
--    metadata; a separate offline job fills `embedding` later.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mmgd_vector_docs (
    doc_id       TEXT PRIMARY KEY,        -- e.g. 'uf:SP', 'uf-fonte:SP:UFV', 'fonte:EOL'
    doc_type     TEXT NOT NULL,           -- 'uf' | 'uf_fonte' | 'fonte' | 'modalidade' | 'faixa_mex'
    text         TEXT NOT NULL,           -- natural-language synthesis, PT-BR
    metadata     TEXT NOT NULL,           -- JSON blob: raw numeric facts behind the text
    embedding    BLOB,                    -- NULL until an embedding job runs
    embedding_model TEXT,                 -- e.g. 'bge-small-en-v1.5' — set when embedding is filled
    updated_at   TEXT NOT NULL DEFAULT (datetime('now'))
);
