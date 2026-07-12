"""Testes de persistência SQLite (sem rede)."""
import pytest
import sqlite3
import json
from energy_data_br import db

def test_schema_sql_text():
    """Verifica se schema_sql_text retorna string não vazia."""
    schema = db.schema_sql_text()
    assert isinstance(schema, str)
    assert len(schema) > 100
    assert "CREATE TABLE IF NOT EXISTS mmgd_raw" in schema
    assert "CREATE TABLE IF NOT EXISTS ons_carga" in schema

def test_init_db(temp_db):
    """Verifica se init_db cria todas as tabelas."""
    # temp_db já tem o schema aplicado pela fixture
    tables = temp_db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    table_names = [t[0] for t in tables]
    expected = {'mmgd_raw', 'mmgd_fato', 'mmgd_vector_docs', 'ons_carga'}
    assert expected.issubset(set(table_names))

def test_connect(tmp_path):
    """Verifica se connect cria o arquivo de banco."""
    db_path = tmp_path / "test.db"
    conn = db.connect(db_path)
    assert conn is not None
    conn.close()
    assert db_path.exists()

def test_insert_records(temp_db, sample_aneel_record):
    """Testa inserção de registros em mmgd_raw."""
    records = [sample_aneel_record]
    resource_id = "test_resource"
    count = db.insert_records(temp_db, resource_id, records, {})
    assert count == 1
    row = temp_db.execute("SELECT * FROM mmgd_raw").fetchone()
    assert row is not None
    # A coluna source_resource_id deve existir
    assert row['source_resource_id'] == resource_id
    parsed = json.loads(row['raw_json'])
    assert parsed['CodEmpreendimento'] == 'GD.TEST.001'
