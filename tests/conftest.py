"""Configuração comum para todos os testes."""
import pytest
import sqlite3
import json
from pathlib import Path
import sys

# Adiciona o diretório raiz ao path para importar os módulos
sys.path.insert(0, str(Path(__file__).parent.parent))

from energy_data_br.db import schema_sql_text, init_db, connect

@pytest.fixture
def temp_db():
    """Banco SQLite em memória com schema aplicado."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(schema_sql_text())
    yield conn
    conn.close()

@pytest.fixture
def sample_aneel_record():
    """Registro ANEEL mínimo para testes."""
    return {
        'CodEmpreendimento': 'GD.TEST.001',
        'SigUF': 'SP',
        'DscFonteGeracao': 'Radiação solar',
        'MdaPotenciaInstaladaKW': '32,50',
        '_hash': 'abc123'
    }

@pytest.fixture
def sample_ons_record():
    """Registro ONS mínimo para testes."""
    return {
        'cod_areacarga': 'S',
        'dat_referencia': '2026-07-10',
        'val_cargaglobal': 12238.3,
        'val_cargammgd': 0.0,
        '_fonte': 'verificada',
        '_area': 'S'
    }
