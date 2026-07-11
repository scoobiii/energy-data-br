"""Testes de persistência SQLite (sem rede)."""
import pytest
import sqlite3
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))
import db

@pytest.fixture
def temp_db():
    conn = sqlite3.connect(":memory:")
    conn.executescript(db.schema_sql_text())
    yield conn
    conn.close()

def test_schema_creates_tables(temp_db):
    tables = temp_db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    table_names = [t[0] for t in tables]
    expected = {'mmgd_raw', 'mmgd_fato', 'mmgd_vector_docs'}
    for table in expected:
        assert table in table_names, f"Tabela {table} não encontrada"
    print(f"✅ Tabelas criadas: {table_names}")

def test_init_db():
    conn = sqlite3.connect(":memory:")
    db.init_db(conn)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    assert len(tables) > 0
    print(f"✅ init_db criou {len(tables)} tabelas")
    conn.close()
