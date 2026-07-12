"""Testes do cliente ONS com mocks (sem rede)."""
import pytest
import json
from unittest.mock import patch, MagicMock
from pathlib import Path

from energy_data_br.ons.api_carga import (
    fetch_carga_verificada,
    fetch_carga_programada,
    fetch_recent_window,
    CODIGOS_AREA_VALIDOS,
)

SAMPLE_ONS_RESPONSE = [
    {
        "cod_areacarga": "S",
        "dat_referencia": "2026-07-10",
        "val_cargaglobal": 12238.3,
        "val_cargammgd": 0.0,
    },
    {
        "cod_areacarga": "S",
        "dat_referencia": "2026-07-10",
        "val_cargaglobal": 11751.4,
        "val_cargammgd": 0.0,
    }
]

@patch('energy_data_br.ons.api_carga.urllib.request.urlopen')
def test_fetch_carga_verificada(mock_urlopen):
    """Testa fetch_carga_verificada com mock."""
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(SAMPLE_ONS_RESPONSE).encode()
    mock_urlopen.return_value.__enter__.return_value = mock_response

    records = fetch_carga_verificada("2026-07-10", "2026-07-11", "S")
    assert len(records) == 2
    assert records[0]['cod_areacarga'] == 'S'
    assert records[0]['val_cargaglobal'] == 12238.3

@patch('energy_data_br.ons.api_carga.urllib.request.urlopen')
def test_fetch_carga_programada(mock_urlopen):
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps(SAMPLE_ONS_RESPONSE).encode()
    mock_urlopen.return_value.__enter__.return_value = mock_response

    records = fetch_carga_programada("2026-07-10", "2026-07-11", "S")
    assert len(records) == 2

@patch('energy_data_br.ons.api_carga.fetch_carga_verificada')
def test_fetch_recent_window(mock_fetch):
    """Testa fetch_recent_window (agregação de áreas)."""
    mock_fetch.return_value = SAMPLE_ONS_RESPONSE
    
    records = list(fetch_recent_window(days=1))
    # 4 áreas * 2 registros = 8
    assert len(records) == 8
    # Verifica que os campos _fonte e _area foram adicionados
    assert records[0]['_fonte'] == 'verificada'
    assert records[0]['_area'] in CODIGOS_AREA_VALIDOS

def test_codigos_area_validos():
    """Verifica que a lista de códigos está definida."""
    assert len(CODIGOS_AREA_VALIDOS) == 4
    assert 'S' in CODIGOS_AREA_VALIDOS
    assert 'N' in CODIGOS_AREA_VALIDOS
    assert 'NE' in CODIGOS_AREA_VALIDOS
    assert 'SIN' in CODIGOS_AREA_VALIDOS
