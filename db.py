"""db.py — camada de persistência SQLite (schema em schema.sql)."""
import sqlite3
import json
from pathlib import Path
from typing import Optional, Dict, Any

def schema_sql_text() -> str:
    """Lê schema.sql do diretório atual."""
    schema_path = Path(__file__).parent / "schema.sql"
    if schema_path.exists():
        return schema_path.read_text(encoding="utf-8")
    # Fallback mínimo
    return """
    CREATE TABLE IF NOT EXISTS mmgd_raw (id INTEGER PRIMARY KEY, data TEXT);
    CREATE TABLE IF NOT EXISTS mmgd_fato (id INTEGER PRIMARY KEY, data TEXT);
    CREATE TABLE IF NOT EXISTS mmgd_vector_docs (id INTEGER PRIMARY KEY, data TEXT);
    """

def init_db(conn: sqlite3.Connection) -> None:
    """Inicializa banco com schema.sql."""
    conn.executescript(schema_sql_text())

def connect(db_path: str | Path) -> sqlite3.Connection:
    """Conecta ao banco SQLite."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn
