"""dessem_client.py — ONS Balanço DESSEM Detalhado, confirmado: 414 arquivos, UTF-8, ';', ponto decimal"""
import urllib.request, json, time, csv, io

CKAN_BASE = "https://dados.ons.org.br/api/3/action"
PACKAGE_ID = "balanco_dessem_detalhe"

def list_resources() -> list[dict]:
    url = f"{CKAN_BASE}/package_show?id={PACKAGE_ID}"
    data = json.loads(urllib.request.urlopen(url, timeout=30).read())
    if not data.get("success"):
        raise RuntimeError(f"package_show falhou: {data.get('error')}")
    return [r for r in data["result"]["resources"] if r.get("format") == "CSV"]

def fetch_csv_rows(resource_url: str) -> list[dict]:
    with urllib.request.urlopen(resource_url, timeout=30) as resp:
        text = resp.read().decode("utf-8")
    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    return list(reader)

def sync_all(delay_sec: float = 0.5):
    resources = list_resources()
    print(f"[dessem] {len(resources)} arquivos a processar")
    for i, r in enumerate(resources, 1):
        rows = fetch_csv_rows(r["url"])
        yield r["name"], rows
        if i % 20 == 0:
            print(f"[dessem] {i}/{len(resources)}")
        time.sleep(delay_sec)
