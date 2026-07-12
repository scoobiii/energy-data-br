"""Testes do cliente ANEEL com mocks (sem rede)."""
import pytest
import json
import zipfile
import io
from pathlib import Path
from unittest.mock import patch, MagicMock

from energy_data_br.aneel.api_client import (
    _get_latest_zip_url,
    _download_snapshot,
    iter_records,
    fetch_schema,
    get_all_records,
)

SAMPLE_CSV = """CodEmpreendimento;MdaPotenciaInstaladaKW;SigUF;DscFonteGeracao
GD.AC.001;32,50;AC;Radiação solar
GD.AC.002;2,00;AC;Radiação solar
"""

@patch('energy_data_br.aneel.api_client.urllib.request.urlopen')
def test_fetch_schema(mock_urlopen):
    """Testa fetch_schema (sem baixar ZIP)."""
    # Mock do retorno de package_show
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "success": True,
        "result": {
            "resources": [
                {"name": "test.zip", "format": "ZIP", "url": "http://test.zip"}
            ]
        }
    }).encode()
    mock_urlopen.return_value.__enter__.return_value = mock_response

    schema = fetch_schema()
    assert isinstance(schema, list)
    assert len(schema) > 0
    # Deve conter pelo menos os campos esperados
    field_ids = [f['id'] for f in schema]
    assert 'CodEmpreendimento' in field_ids
    assert 'MdaPotenciaInstaladaKW' in field_ids

@patch('energy_data_br.aneel.api_client._get_latest_zip_url')
@patch('energy_data_br.aneel.api_client.urllib.request.urlretrieve')
def test_download_snapshot(mock_urlretrieve, mock_get_url, tmp_path):
    """Testa download_snapshot com ZIP falso."""
    mock_get_url.return_value = "http://fake.zip"
    
    # Criar ZIP falso com CSV
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zf:
        zf.writestr('test.csv', SAMPLE_CSV)
    zip_data = zip_buffer.getvalue()
    
    def fake_retrieve(url, dest):
        with open(dest, 'wb') as f:
            f.write(zip_data)
    
    mock_urlretrieve.side_effect = fake_retrieve
    
    zip_path = _download_snapshot("http://fake.zip", cache_dir=tmp_path)
    assert zip_path.exists()
    assert zip_path.stat().st_size > 0

def test_iter_records(tmp_path):
    """Testa iteração sobre registros do CSV."""
    zip_path = tmp_path / "test.zip"
    with zipfile.ZipFile(zip_path, 'w') as zf:
        zf.writestr('test.csv', SAMPLE_CSV)
    
    records = list(iter_records(zip_path))
    assert len(records) == 2
    assert records[0]['codempreendimento'] == 'GD.AC.001'
    assert records[0]['mdapotenciainstaladakw'] == '32,50'
    assert records[0]['siguf'] == 'AC'
    assert records[0]['potencia_instalada_kw'] == 32.5
    assert '_hash' in records[0]
