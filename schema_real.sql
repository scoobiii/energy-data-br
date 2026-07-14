CREATE TABLE mmgd_raw (
    row_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_resource_id TEXT NOT NULL,
    ingested_at TEXT NOT NULL DEFAULT (datetime('now')),
    raw_json TEXT NOT NULL
, hash TEXT);
CREATE TABLE sqlite_sequence(name,seq);
CREATE TABLE mmgd_fato (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cod_empreendimento TEXT,
    siguf TEXT,
    dscfontegeracao TEXT,
    potencia_instalada_kw REAL,
    hash TEXT,
    faixa_regulatoria TEXT,
    modalidade TEXT
);
CREATE TABLE mmgd_vector_docs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doc_id TEXT,
    content TEXT,
    metadata TEXT,
    embedding BLOB
);
CREATE TABLE ons_carga (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tipo TEXT NOT NULL,
    area TEXT NOT NULL,
    data_json TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE sqlite_stat1(tbl,idx,stat);
CREATE TABLE mmgd_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        );
CREATE INDEX idx_ons_carga_tipo_area ON ons_carga(tipo, area);
CREATE INDEX idx_mmgd_fato_siguf ON mmgd_fato(siguf);
CREATE INDEX idx_mmgd_fato_fonte ON mmgd_fato(dscfontegeracao);
CREATE INDEX idx_mmgd_fato_potencia ON mmgd_fato(potencia_instalada_kw);
CREATE INDEX idx_ons_carga_area ON ons_carga(area);
CREATE UNIQUE INDEX idx_mmgd_raw_hash ON mmgd_raw(hash);
CREATE TABLE dessem_detalhe (
    id INTEGER PRIMARY KEY, din_programacaodia TEXT, num_patamar INTEGER,
    cod_subsistema TEXT, val_demanda REAL, val_ger_hidraulica REAL,
    val_ger_pch REAL, val_ger_termica REAL, val_ger_pct REAL,
    val_ger_eolica REAL, val_ger_fotovoltaica REAL, val_ger_mmgd REAL,
    val_cons_elevatoria REAL, hash TEXT UNIQUE, fonte_arquivo TEXT);
CREATE UNIQUE INDEX idx_mmgd_fato_hash ON mmgd_fato(hash);
CREATE TABLE siga_fato (
    cod_ceg TEXT,
    nome_empreendimento TEXT,
    uf TEXT,
    tipo_geracao TEXT,
    fase_usina TEXT,
    fonte_combustivel TEXT,
    potencia_outorgada_kw REAL,
    potencia_fiscalizada_kw REAL,
    garantia_fisica_kw REAL,
    lat REAL,
    lon REAL,
    data_entrada_operacao TEXT,
    proprietario TEXT,
    municipios TEXT,
    hash TEXT UNIQUE
);
CREATE TABLE growth_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    data TEXT NOT NULL UNIQUE,
    mmgd_ativos INTEGER,
    mmgd_potencia_kw REAL,
    siga_ativos INTEGER,
    siga_potencia_kw REAL,
    ons_carga_media_mw REAL,
    total_registros INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_growth_log_data ON growth_log(data);
