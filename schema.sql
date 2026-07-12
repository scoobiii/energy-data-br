-- mmgd_raw com source_resource_id
CREATE TABLE IF NOT EXISTS mmgd_raw (
    row_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_resource_id TEXT NOT NULL,
    ingested_at TEXT NOT NULL DEFAULT (datetime('now')),
    raw_json TEXT NOT NULL
);

-- mmgd_fato
CREATE TABLE IF NOT EXISTS mmgd_fato (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cod_empreendimento TEXT,
    siguf TEXT,
    dscfontegeracao TEXT,
    potencia_instalada_kw REAL,
    hash TEXT,
    faixa_regulatoria TEXT,
    modalidade TEXT
);

-- mmgd_vector_docs
CREATE TABLE IF NOT EXISTS mmgd_vector_docs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT,
    content TEXT,
    metadata TEXT,
    embedding BLOB
);

-- ons_carga (ONS semi-horário)
CREATE TABLE IF NOT EXISTS ons_carga (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,
    area TEXT NOT NULL,
    data_json TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_ons_carga_tipo_area ON ons_carga(tipo, area);
