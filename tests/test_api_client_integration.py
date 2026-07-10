"""
test_api_client_integration.py — bate na API REAL da ANEEL (sem mock).

Por depender de rede/serviço externo, este teste pula (skip) automaticamente
se o endpoint estiver inacessível no ambiente de execução (ex: CI sem
acesso à internet, sandbox com allowlist de domínio) — mas nunca substitui
a chamada real por um fake.
"""

import pytest

from aneel_mmgd import api_client


def _api_reachable() -> bool:
    try:
        api_client.fetch_schema(api_client.DEFAULT_RESOURCE_ID)
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _api_reachable(),
    reason="dadosabertos.aneel.gov.br inacessível neste ambiente (sem rede/allowlist)",
)


def test_fetch_schema_returns_real_fields():
    fields = api_client.fetch_schema(api_client.DEFAULT_RESOURCE_ID)
    assert isinstance(fields, list)
    assert len(fields) > 0
    assert all("id" in f for f in fields)


def test_fetch_page_returns_real_records():
    records = api_client.fetch_page(api_client.DEFAULT_RESOURCE_ID, offset=0, limit=5)
    assert isinstance(records, list)
    assert len(records) <= 5


def test_iter_records_respects_max_records():
    records = list(api_client.iter_records(
        resource_id=api_client.DEFAULT_RESOURCE_ID,
        page_size=10,
        max_records=25,
    ))
    assert len(records) == 25
