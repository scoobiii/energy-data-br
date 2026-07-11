"""Testes de integração ONS - validados com dados reais."""
import pytest
import urllib.request

def is_online() -> bool:
    """Testa endpoint real (não URL raiz)."""
    try:
        url = "https://apicarga.ons.org.br/prd/cargaverificada?dat_inicio=2026-07-10&dat_fim=2026-07-11&cod_areacarga=S"
        urllib.request.urlopen(url, timeout=10)
        return True
    except Exception as e:
        print(f"⚠️ ONS offline: {e}")
        return False

pytestmark = pytest.mark.skipif(not is_online(), reason="Offline ou ONS inacessível")

def test_fetch_carga_verificada():
    from ons.api_carga import fetch_carga_verificada
    records = fetch_carga_verificada("2026-07-10", "2026-07-11", "S")
    assert len(records) > 0
    assert records[0]['cod_areacarga'] == 'S'
    assert 'val_cargaglobal' in records[0]
    print(f"✅ {len(records)} registros de carga verificada (S)")

def test_codigos_area_validos():
    from ons.api_carga import CODIGOS_AREA_VALIDOS, fetch_carga_verificada
    for area in CODIGOS_AREA_VALIDOS:
        records = fetch_carga_verificada("2026-07-10", "2026-07-11", area)
        assert len(records) > 0, f"Área {area} não retornou dados"
        print(f"✅ Área {area}: {len(records)} registros")
