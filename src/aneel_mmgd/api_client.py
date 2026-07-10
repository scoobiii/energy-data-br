"""
api_client.py — cliente para a API CKAN DataStore do Portal de Dados Abertos ANEEL.

Endpoint público, sem necessidade de API key para leitura:
    https://dadosabertos.aneel.gov.br/api/3/action/datastore_search

Dataset de referência:
    "Relação de empreendimentos de Mini e Micro Geração Distribuída"
    https://dadosabertos.aneel.gov.br/dataset/relacao-de-empreendimentos-de-geracao-distribuida
    resource_id: b1bd71e7-d0ad-4214-9053-cbd58e9564a7

Este módulo faz apenas transporte HTTP + paginação. Nenhum dado é
sintetizado ou inventado aqui — tudo vem diretamente da resposta da API.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Iterator

BASE_URL = "https://dadosabertos.aneel.gov.br/api/3/action/datastore_search"
DEFAULT_RESOURCE_ID = "b1bd71e7-d0ad-4214-9053-cbd58e9564a7"
DEFAULT_PAGE_SIZE = 5000
USER_AGENT = "aneel-mmgd-etl/0.1 (+https://mex.eco.br)"


class AneelApiError(RuntimeError):
    pass


def http_get_json(url: str, params: dict, retries: int = 3, timeout: int = 30) -> dict:
    """GET + parse JSON, with exponential backoff retries on network failure."""
    qs = urllib.parse.urlencode(params)
    full_url = f"{url}?{qs}"
    last_err: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(full_url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last_err = e
            if attempt < retries:
                time.sleep(2 ** attempt)
    raise AneelApiError(f"Falha ao buscar {full_url} após {retries} tentativas: {last_err}")


def fetch_schema(resource_id: str = DEFAULT_RESOURCE_ID) -> list[dict]:
    """Retorna a lista de campos reais expostos pelo datastore (introspecção,
    não hardcode) — ex: [{'id': 'SigUF', 'type': 'text'}, ...]."""
    data = http_get_json(BASE_URL, {"resource_id": resource_id, "limit": 0})
    if not data.get("success"):
        raise AneelApiError(f"datastore_search sem sucesso: {data}")
    return data["result"]["fields"]


def fetch_page(resource_id: str, offset: int, limit: int) -> list[dict]:
    data = http_get_json(BASE_URL, {"resource_id": resource_id, "limit": limit, "offset": offset})
    if not data.get("success"):
        raise AneelApiError(f"datastore_search sem sucesso (offset={offset}): {data}")
    return data["result"]["records"]


def iter_records(
    resource_id: str = DEFAULT_RESOURCE_ID,
    page_size: int = DEFAULT_PAGE_SIZE,
    max_records: int | None = None,
    on_page=None,
) -> Iterator[dict]:
    """Gera registros reais da API, paginando via offset/limit até esgotar
    o dataset (ou atingir max_records, se informado).

    on_page: callback opcional(offset:int, n:int) para progresso.
    """
    offset = 0
    total = 0
    while True:
        limit = page_size
        if max_records is not None:
            remaining = max_records - total
            if remaining <= 0:
                return
            limit = min(page_size, remaining)
        records = fetch_page(resource_id, offset, limit)
        if not records:
            return
        if on_page:
            on_page(offset, len(records))
        for r in records:
            yield r
        total += len(records)
        offset += len(records)
        if len(records) < limit:
            return  # última página do dataset
