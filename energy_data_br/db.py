"""db.py — persistência SQLite com PRAGMAs robustos para FUSE/Android."""
import sqlite3
import json
from pathlib import Path

def schema_sql_text() -> str:
    base_dir = Path(__file__).parent.parent
    schema_path = base_dir / "schema.sql"
    if schema_path.exists():
        return schema_path.read_text(encoding="utf-8")
    return """
    CREATE TABLE IF NOT EXISTS mmgd_raw (
        row_id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_resource_id TEXT NOT NULL,
        ingested_at TEXT NOT NULL DEFAULT (datetime('now')),
        raw_json TEXT NOT NULL,
        hash TEXT UNIQUE
    );
    CREATE TABLE IF NOT EXISTS mmgd_fato (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cod_empreendimento TEXT,
        siguf TEXT,
        dscfontegeracao TEXT,
        potencia_instalada_kw REAL,
        hash TEXT UNIQUE,
        faixa_regulatoria TEXT,
        modalidade TEXT
    );
    CREATE TABLE IF NOT EXISTS mmgd_vector_docs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        doc_id TEXT,
        content TEXT,
        metadata TEXT,
        embedding BLOB
    );
    CREATE TABLE IF NOT EXISTS ons_carga (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tipo TEXT NOT NULL,
        area TEXT NOT NULL,
        data_json TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_ons_carga_tipo_area ON ons_carga(tipo, area);
    """

def connect(db_path: str | Path) -> sqlite3.Connection:
    """Conecta com PRAGMAs robustos para FUSE/Android."""
    conn = sqlite3.connect(str(db_path), timeout=60.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    
    # PRAGMAs críticos para performance e concorrência
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")        # ← NÃO FULL
    conn.execute("PRAGMA busy_timeout=30000")        # ← AGUARDA 30s
    conn.execute("PRAGMA cache_size=-64000")         # 64MB cache
    conn.execute("PRAGMA temp_store=MEMORY")         # temp em RAM
    conn.execute("PRAGMA mmap_size=268435456")       # 256MB mmap
    
    return conn

def init_db(conn: sqlite3.Connection) -> None:
    """Inicializa banco com schema.sql."""
    conn.executescript(schema_sql_text())

def insert_records(conn: sqlite3.Connection, resource_id: str, records: list[dict], cols: dict) -> int:
    cursor = conn.cursor()
    count = 0
    for rec in records:
        cursor.execute(
            "INSERT OR IGNORE INTO mmgd_raw (source_resource_id, raw_json, hash) VALUES (?, ?, ?)",
            (resource_id, json.dumps(rec, ensure_ascii=False), rec.get('_hash', ''))
        )
        count += 1
    conn.commit()
    return count
