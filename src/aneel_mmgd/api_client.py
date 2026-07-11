"""
api_client.py — ingestão ANEEL via ZIP snapshot (datastore_search morto, ver Sprint 0).
Nomes de função mantidos (fetch_schema, iter_records) para compatibilidade com cli.py existente.
"""
from __future__ import annotations
import csv
import hashlib
import json
import time
import urllib.error
import urllib.request
from io import TextIOWrapper
from pathlib import Path
from typing import Iterator

PACKAGE_ID = "relacao-de-empreendimentos-de-geracao-distribuida"
CKAN_BASE = "https://dadosabertos.aneel.gov.br/api/3/action"
CACHE_DIR = Path("cache")
USER_AGENT = "aneel-mmgd-etl/0.2 (+https://mex.eco.br)"


class AneelApiError(RuntimeError):
    pass


def _get_latest_zip_url() -> str:
    url = f"{CKAN_BASE}/package_show?id={PACKAGE_ID}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if not data.get("success"):
        raise AneelApiError(f"package_show falhou: {data.get('error')}")
    zips = [r for r in data["result"]["resources"] if r["name"].lower().endswith(".zip")]
    if not zips:
        raise AneelApiError("Nenhum resource .zip encontrado no package")
    return zips[0]["url"]


def _download_snapshot(url: str, retries: int = 3) -> Path:
    CACHE_DIR.mkdir(exist_ok=True)
    zip_path = CACHE_DIR / "mmgd.zip"
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            urllib.request.urlretrieve(url, zip_path)
            import zipfile
            with zipfile.ZipFile(zip_path) as zf:
                if zf.testzip() is not None:
                    raise zipfile.BadZipFile("ZIP corrompido")
            return zip_path
        except Exception as e:
            last_err = e
            if attempt < retries:
                time.sleep(2 ** attempt)
    raise AneelApiError(f"Download falhou após {retries} tentativas: {last_err}")


def fetch_schema(resource_id: str | None = None) -> list[dict]:
    """Introspecção real do CSV: lê o header do ZIP, sem hardcode de campo."""
    import zipfile
    zip_path = _download_snapshot(_get_latest_zip_url())
    with zipfile.ZipFile(zip_path) as zf:
        csv_name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        with zf.open(csv_name) as raw:
            header = TextIOWrapper(raw, encoding="latin-1").readline()
    fields = header.strip().split(";")
    return [{"id": f.strip('"'), "type": "text"} for f in fields]


def iter_records(
    resource_id: str | None = None,
    page_size: int = 5000,
    max_records: int | None = None,
    on_page=None,
) -> Iterator[dict]:
    """Streaming real do CSV dentro do ZIP. resource_id/page_size mantidos
    na assinatura por compatibilidade, não usados (dataset é snapshot único)."""
    import zipfile
    zip_path = _download_snapshot(_get_latest_zip_url())
    total = 0
    with zipfile.ZipFile(zip_path) as zf:
        csv_name = next(n for n in zf.namelist() if n.lower().endswith(".csv"))
        with zf.open(csv_name) as raw:
            text = TextIOWrapper(raw, encoding="latin-1")
            reader = csv.DictReader(text, delimiter=";")
            for row in reader:
                row["_hash"] = hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()
                yield row
                total += 1
                if on_page and total % page_size == 0:
                    on_page(total, page_size)
                if max_records is not None and total >= max_records:
                    return
