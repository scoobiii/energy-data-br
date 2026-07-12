"""
export.py — exportações derivadas do banco (nenhum dado sintético: tudo
vem das views SQL, que por sua vez vêm de mmgd_fato, que vem da API real).
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path


def export_treemap_json(conn: sqlite3.Connection, path: str | Path) -> dict:
    """Hierarquia Brasil > UF > Fonte, dimensionada em MW, para web/treemap.html."""
    ufs = conn.execute(
        "SELECT uf, potencia_total_mw, qtd_empreendimentos FROM vw_totais_uf"
    ).fetchall()

    children = []
    for uf, mw, qtd in ufs:
        if not uf:
            continue
        fontes = conn.execute(
            "SELECT fonte_norm, potencia_total_mw, qtd_empreendimentos "
            "FROM vw_totais_uf_fonte WHERE uf = ? ORDER BY potencia_total_mw DESC",
            (uf,),
        ).fetchall()
        uf_children = [
            {"name": f, "value": fmw, "qtd": fqtd, "fonte": f}
            for f, fmw, fqtd in fontes if fmw and fmw > 0
        ]
        if not uf_children:
            continue
        children.append({"name": uf, "value": mw, "qtd": qtd, "children": uf_children})

    tree = {
        "name": "Brasil",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "unit": "MW",
        "children": children,
    }
    Path(path).write_text(json.dumps(tree, ensure_ascii=False, indent=2), encoding="utf-8")
    return tree


def totals_summary(conn: sqlite3.Connection) -> dict:
    """Resumo numérico simples para `aneel-mmgd stats` / smoke tests."""
    row = conn.execute(
        "SELECT COUNT(*), ROUND(SUM(potencia_kw)/1000.0,3) FROM mmgd_fato WHERE is_outlier=0"
    ).fetchone()
    qtd_total, mw_total = row
    por_fonte = conn.execute(
        "SELECT fonte_norm, qtd_empreendimentos, potencia_total_mw FROM vw_totais_fonte"
    ).fetchall()
    por_uf = conn.execute(
        "SELECT uf, qtd_empreendimentos, potencia_total_mw FROM vw_totais_uf"
    ).fetchall()
    return {
        "qtd_empreendimentos": qtd_total or 0,
        "potencia_total_mw": mw_total or 0.0,
        "por_fonte": [{"fonte": f, "qtd": q, "mw": mw} for f, q, mw in por_fonte],
        "por_uf": [{"uf": u, "qtd": q, "mw": mw} for u, q, mw in por_uf],
    }
