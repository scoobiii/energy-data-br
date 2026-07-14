#!/usr/bin/env python3
"""
energy_data_br/reconciliation/agent.py

Agente de reconciliação: compara a persistência local (SQLite) contra as
fontes oficiais (ONS API de carga verificada, ONS CKAN, ANEEL CKAN MMGD)
e reporta drift, staleness e gaps de schema.

Uso:
    python -m energy_data_br.reconciliation.agent --check all
    python -m energy_data_br.reconciliation.agent --check carga --dias 3
    python -m energy_data_br.reconciliation.agent --check mmgd
    python -m energy_data_br.reconciliation.agent --check schema
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============ CONFIG ============

DB_PATH = Path("energy-data-br.sqlite")
REPORT_DIR = Path("logs/reconciliation")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

ONS_CKAN_BASE = "https://dados.ons.org.br/api/3/action"
ONS_API_CARGA = "https://apicarga.ons.org.br/prd/cargaverificada"
ANEEL_CKAN_BASE = "https://dadosabertos.aneel.gov.br/api/3/action"

# tolerância aceitável de divergência entre valor local e valor oficial (%)
CARGA_TOLERANCE_PCT = 0.5

# datasets ANEEL relevantes (id do package no CKAN)
ANEEL_MMGD_PACKAGE = "relacao-de-empreendimentos-de-geracao-distribuida"

# áreas de carga a validar (códigos reais conforme API)
DEFAULT_AREAS = ["S", "NE", "N", "SIN"]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(REPORT_DIR / "agent.log"),
    ],
)
log = logging.getLogger("reconciliation")


# ============ SESSÃO HTTP RESILIENTE ============

def build_session() -> requests.Session:
    """Cria uma sessão requests com retry para erros de DNS e status instáveis."""
    session = requests.Session()
    retry = Retry(
        total=4,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; energy-data-br/1.0; reconciliation-agent)"
    })
    return session

_SESSION = build_session()


# ============ DATA CLASSES ============

@dataclass
class Divergence:
    tipo: str
    chave: str
    valor_local: Any
    valor_oficial: Any
    delta_pct: float | None = None
    severidade: str = "info"  # info | atencao | critico


@dataclass
class ReconciliationReport:
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    divergencias: list[Divergence] = field(default_factory=list)
    resumo: dict[str, Any] = field(default_factory=dict)

    def add(self, d: Divergence):
        self.divergencias.append(d)

    def to_dict(self):
        return {
            "timestamp": self.timestamp,
            "resumo": self.resumo,
            "divergencias": [asdict(d) for d in self.divergencias],
        }

    def save(self, name: str):
        path = REPORT_DIR / f"{name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        path.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False))
        log.info(f"Relatório salvo em {path}")
        return path


# ============ DB HELPERS ============

def get_conn() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Banco não encontrado: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_real_schema(conn: sqlite3.Connection) -> dict[str, list[str]]:
    schema = {}
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    for t in tables:
        cols = conn.execute(f"PRAGMA table_info({t['name']})").fetchall()
        schema[t["name"]] = [c["name"] for c in cols]
    return schema


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    counts = {}
    for t in tables:
        counts[t["name"]] = conn.execute(f"SELECT COUNT(*) c FROM {t['name']}").fetchone()["c"]
    return counts


# ============ ONS: CARGA VERIFICADA (DRIFT CHECK) ============

def fetch_ons_carga_oficial(area: str, data_inicio: str, data_fim: str) -> list[dict]:
    """Busca carga verificada oficial via API dedicada do ONS.
    Inclui tentativas de retry com backoff e trata array vazio como aviso, não erro."""
    params = {"dat_inicio": data_inicio, "dat_fim": data_fim, "cod_areacarga": area}
    for tentativa in range(3):
        try:
            resp = _SESSION.get(ONS_API_CARGA, params=params, timeout=30)
            if resp.status_code != 200:
                log.error(f"Área={area}: HTTP {resp.status_code} | corpo: {resp.text[:300]!r}")
                return []
            data = resp.json()
            if not data:
                log.warning(
                    f"Área={area}: array vazio para {data_inicio}..{data_fim} "
                    f"(código de área pode estar errado ou dado ainda não consolidado)"
                )
                return []
            if isinstance(data, dict):
                return data.get("resultado", data.get("data", []))
            return data
        except requests.exceptions.ConnectionError as e:
            error_str = str(e)
            if "NameResolutionError" in error_str or "Failed to resolve" in error_str:
                log.warning(f"Área={area}: DNS falhou na tentativa {tentativa+1}/3, retry em 2s...")
                time.sleep(2)
                continue
            log.error(f"Área={area}: erro de conexão: {e}")
            return []
        except requests.RequestException as e:
            log.error(f"Área={area}: falha: {e}")
            return []
    log.error(f"Área={area}: DNS falhou nas 3 tentativas, desistindo.")
    return []


def check_carga_drift(conn: sqlite3.Connection, dias: int, areas: list[str]) -> list[Divergence]:
    divergencias = []
    data_fim = datetime.utcnow().date()
    data_inicio = data_fim - timedelta(days=dias)

    for area in areas:
        oficiais = fetch_ons_carga_oficial(
            area, data_inicio.isoformat(), data_fim.isoformat()
        )
        if not oficiais:
            divergencias.append(Divergence(
                tipo="fetch_vazio",
                chave=area,
                valor_local=None,
                valor_oficial=None,
                severidade="atencao",
            ))
            continue

        rows = conn.execute(
            "SELECT data_json, created_at FROM ons_carga WHERE area = ? "
            "ORDER BY created_at DESC LIMIT 500",
            (area,),
        ).fetchall()

        local_by_ts = {}
        for r in rows:
            try:
                payload = json.loads(r["data_json"])
                ts = (payload.get("din_referenciautc") or
                      payload.get("din_referencia") or
                      payload.get("dat_referencia"))
                val = (payload.get("val_cargaglobal") or
                       payload.get("valor") or
                       payload.get("val_carga"))
                if ts is not None and val is not None:
                    local_by_ts[ts] = val
            except (json.JSONDecodeError, AttributeError):
                continue

        for registro in oficiais:
            ts = (registro.get("din_referenciautc") or
                  registro.get("din_referencia") or
                  registro.get("dat_referencia"))
            val_oficial = (registro.get("val_cargaglobal") or
                           registro.get("val_carga"))
            if ts is None or val_oficial is None:
                continue
            val_local = local_by_ts.get(ts)
            if val_local is None:
                divergencias.append(Divergence(
                    tipo="ausente_localmente",
                    chave=f"{area}:{ts}",
                    valor_local=None,
                    valor_oficial=val_oficial,
                    severidade="atencao",
                ))
                continue
            try:
                delta_pct = abs(float(val_local) - float(val_oficial)) / float(val_oficial) * 100
            except (ZeroDivisionError, ValueError, TypeError):
                continue
            if delta_pct > CARGA_TOLERANCE_PCT:
                divergencias.append(Divergence(
                    tipo="revisao_retroativa_nao_capturada",
                    chave=f"{area}:{ts}",
                    valor_local=val_local,
                    valor_oficial=val_oficial,
                    delta_pct=round(delta_pct, 3),
                    severidade="critico" if delta_pct > 5 else "atencao",
                ))

    return divergencias


# ============ ANEEL: MMGD (STALENESS CHECK) ============

def fetch_aneel_package_meta(package_id: str) -> dict | None:
    try:
        resp = _SESSION.get(
            f"{ANEEL_CKAN_BASE}/package_show", params={"id": package_id}, timeout=30
        )
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("success"):
            return None
        return payload["result"]
    except requests.RequestException as e:
        log.error(f"Falha ao buscar metadados ANEEL: {e}")
        return None


def check_mmgd_staleness(conn: sqlite3.Connection) -> list[Divergence]:
    divergencias = []
    meta = fetch_aneel_package_meta(ANEEL_MMGD_PACKAGE)
    if meta is None:
        divergencias.append(Divergence(
            tipo="fetch_falhou",
            chave=ANEEL_MMGD_PACKAGE,
            valor_local=None,
            valor_oficial=None,
            severidade="atencao",
        ))
        return divergencias

    oficial_modificado = meta.get("metadata_modified")

    row = conn.execute(
        "SELECT MAX(ingested_at) AS ultimo FROM mmgd_raw"
    ).fetchone()
    local_ultimo = row["ultimo"] if row else None

    if oficial_modificado and local_ultimo:
        try:
            dt_oficial = datetime.fromisoformat(oficial_modificado.replace("Z", "+00:00"))
            dt_local = datetime.fromisoformat(local_ultimo.replace("Z", "+00:00"))
            defasagem_dias = (dt_oficial.replace(tzinfo=None) - dt_local.replace(tzinfo=None)).days
            if defasagem_dias > 0:
                divergencias.append(Divergence(
                    tipo="mmgd_desatualizado",
                    chave=ANEEL_MMGD_PACKAGE,
                    valor_local=local_ultimo,
                    valor_oficial=oficial_modificado,
                    delta_pct=None,
                    severidade="critico" if defasagem_dias > 30 else "atencao",
                ))
        except ValueError:
            pass

    raw_count = conn.execute("SELECT COUNT(*) c FROM mmgd_raw").fetchone()["c"]
    fato_count = conn.execute("SELECT COUNT(*) c FROM mmgd_fato").fetchone()["c"]
    if raw_count > 0:
        pct_processado = fato_count / raw_count * 100
        if pct_processado < 95:
            divergencias.append(Divergence(
                tipo="etl_raw_para_fato_incompleto",
                chave="mmgd_raw->mmgd_fato",
                valor_local=fato_count,
                valor_oficial=raw_count,
                delta_pct=round(100 - pct_processado, 2),
                severidade="critico" if pct_processado < 50 else "atencao",
            ))

    return divergencias


# ============ SCHEMA GAP CHECK ============

CAMPOS_OFICIAIS_MMGD = {
    "distribuidora",
    "cod_empreendimento",
    "nome_titular",
    "classe_producao",
    "subgrupo",
    "qtd_uc_recebe_credito",
    "data_conexao",
    "tipo_unidade_produtora",
    "fonte",
    "potencia_instalada_kw",
    "municipio",
    "uf",
}

ALIASES = {
    "siguf": "uf",
    "dscfontegeracao": "fonte",
    "potencia_instalada_kw": "potencia_instalada_kw",
    "cod_empreendimento": "cod_empreendimento",
}


def check_schema_gap(conn: sqlite3.Connection) -> list[Divergence]:
    divergencias = []
    schema = get_real_schema(conn)
    campos_locais_mmgd = set(schema.get("mmgd_fato", []))
    campos_normalizados = {ALIASES.get(c, c) for c in campos_locais_mmgd}

    faltantes = CAMPOS_OFICIAIS_MMGD - campos_normalizados
    for campo in sorted(faltantes):
        divergencias.append(Divergence(
            tipo="campo_ausente_no_schema",
            chave=f"mmgd_fato.{campo}",
            valor_local="ausente",
            valor_oficial="presente na fonte ANEEL",
            severidade="atencao",
        ))
    return divergencias


# ============ ORQUESTRAÇÃO ============

def run(checks: list[str], dias: int, areas: list[str]) -> ReconciliationReport:
    conn = get_conn()
    report = ReconciliationReport()

    if "schema" in checks or "all" in checks:
        log.info("Verificando gaps de schema vs. dicionário oficial ANEEL...")
        for d in check_schema_gap(conn):
            report.add(d)

    if "mmgd" in checks or "all" in checks:
        log.info("Verificando staleness e completude do pipeline MMGD...")
        for d in check_mmgd_staleness(conn):
            report.add(d)

    if "carga" in checks or "all" in checks:
        log.info(f"Verificando drift de carga verificada (últimos {dias} dias, áreas={areas})...")
        for d in check_carga_drift(conn, dias, areas):
            report.add(d)

    counts = table_counts(conn)
    criticos = sum(1 for d in report.divergencias if d.severidade == "critico")
    atencoes = sum(1 for d in report.divergencias if d.severidade == "atencao")
    report.resumo = {
        "contagem_tabelas": counts,
        "total_divergencias": len(report.divergencias),
        "criticos": criticos,
        "atencoes": atencoes,
    }

    conn.close()
    return report


def print_summary(report: ReconciliationReport):
    print("\n" + "=" * 60)
    print("RELATÓRIO DE RECONCILIAÇÃO — energy-data-br vs fontes oficiais")
    print("=" * 60)
    print(f"Timestamp: {report.timestamp}")
    print(f"Total de divergências: {report.resumo['total_divergencias']}")
    print(f"  Críticos: {report.resumo['criticos']}  |  Atenção: {report.resumo['atencoes']}")
    print("-" * 60)
    for d in sorted(report.divergencias, key=lambda x: {"critico": 0, "atencao": 1, "info": 2}[x.severidade]):
        marcador = {"critico": "🔴", "atencao": "🟡", "info": "🔵"}[d.severidade]
        linha = f"{marcador} [{d.tipo}] {d.chave} | local={d.valor_local} oficial={d.valor_oficial}"
        if d.delta_pct is not None:
            linha += f" | delta={d.delta_pct}%"
        print(linha)
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Agente de reconciliação energy-data-br")
    parser.add_argument(
        "--check", choices=["all", "carga", "mmgd", "schema"], default="all",
        help="Qual verificação rodar",
    )
    parser.add_argument("--dias", type=int, default=3, help="Janela de dias para checar drift de carga")
    parser.add_argument("--areas", nargs="+", default=DEFAULT_AREAS, help="Áreas de carga a validar")
    args = parser.parse_args()

    checks = [args.check]
    report = run(checks, args.dias, args.areas)
    print_summary(report)
    report.save(f"reconciliation_{args.check}")

    if report.resumo["criticos"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
