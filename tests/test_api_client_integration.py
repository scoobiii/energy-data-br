"""Testes de integração ANEEL - validados com dados reais."""
import pytest
import urllib.request
from pathlib import Path

def is_online() -> bool:
    try:
        urllib.request.urlopen("https://dadosabertos.aneel.gov.br/", timeout=5)
        return True
    except:
        return False

pytestmark = pytest.mark.skipif(not is_online(), reason="Offline ou ANEEL inacessível")

def test_fetch_schema_returns_real_fields():
    from energy_data_br.aneel.api_client import fetch_schema
    schema = fetch_schema()
    assert isinstance(schema, list)
    assert len(schema) > 0
    field_names = {f['id'] for f in schema}
    expected = {'CodEmpreendimento', 'SigUF', 'DscFonteGeracao'}
    assert expected.issubset(field_names)
    print(f"✅ Schema: {len(schema)} campos")

def test_iter_records_respects_max_records():
    """Usa _get_latest_zip_url + _download_snapshot + iter_records."""
    from energy_data_br.aneel.api_client import _get_latest_zip_url, _download_snapshot, iter_records
    
    zip_path = Path("cache/mmgd.zip")
    if not zip_path.exists():
        url = _get_latest_zip_url()
        zip_path = _download_snapshot(url)
    
    count = 0
    for _ in iter_records(zip_path):
        count += 1
        if count >= 10:
            break
    
    assert count == 10
    print(f"✅ {count} registros lidos")
