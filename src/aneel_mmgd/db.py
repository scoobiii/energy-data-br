"""
db.py — camada de persistência SQLite (schema em schema.sql, aplicado via
init_db). Nenhuma lógica de negócio aqui — só CRUD/agregação.
"""

from __future__ import annotations

import json
import sqlite3
from importlib import resources
from pathlib import Path

from . import rules


def schema_sql_text() -> str:
    return resources.files("aneel_mmgd").joinpath("schema.sql").read_text(encoding="utf-8")


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(schema_sql_text())
    conn.commit()


def connect(db_path: str | Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    init_db(conn)
    return conn


def insert_records(conn: sqlite3.Connection, resource_id: str, records: list[dict], cols: dict) -> int:
    """Grava o lote bruto em mmgd_raw e a versão classificada em mmgd_fato.
    Retorna a quantidade de registros inseridos."""
    if not records:
        return 0

    raw_rows = [(resource_id, json.dumps(r, ensure_ascii=False)) for r in records]
    conn.executemany(
        "INSERT INTO mmgd_raw (source_resource_id, raw_json) VALUES (?, ?)", raw_rows
    )
    conn.commit()

    # cursor.lastrowid após executemany não é confiável entre versões do
    # driver sqlite3 — consulta explícita ao MAX(row_id), que é seguro pois
    # row_id é AUTOINCREMENT monotonicamente crescente.
    max_id = conn.execute("SELECT MAX(row_id) FROM mmgd_raw").fetchone()[0]
    first_new_id = max_id - len(records) + 1

    fato_rows = []
    for i, record in enumerate(records):
        raw_row_id = first_new_id + i
        c = rules.classify_record(cols, record)
        fato_rows.append((
            raw_row_id, c["uf"], c["municipio"], c["cod_ibge"], c["distribuidora"],
            c["fonte_bruta"], c["fonte_norm"], c["potencia_kw"], c["data_conexao"],
            c["modalidade_bruta"], c["modalidade_norm"], c["classe_consumo"],
            c["faixa_regulatoria"], c["faixa_potencia_mex"], c["is_outlier"],
        ))

    conn.executemany(
        """INSERT INTO mmgd_fato (
            raw_row_id, uf, municipio, cod_ibge, distribuidora,
            fonte_bruta, fonte_norm, potencia_kw, data_conexao,
            modalidade_bruta, modalidade_norm, classe_consumo,
            faixa_regulatoria, faixa_potencia_mex, is_outlier
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        fato_rows,
    )
    conn.commit()
    return len(records)


def build_vector_docs(conn: sqlite3.Connection) -> int:
    """Sintetiza chunks de texto PT-BR (agregações reais do banco, não
    inventadas) prontos para uma futura passada de embedding. Retorna a
    quantidade de docs gerados."""
    conn.execute(
        "DELETE FROM mmgd_vector_docs WHERE doc_type IN ('uf','uf_fonte','fonte','faixa_mex')"
    )
    n = 0

    for uf, qtd, mw, media in conn.execute(
        "SELECT uf, qtd_empreendimentos, potencia_total_mw, potencia_media_kw FROM vw_totais_uf"
    ):
        if not uf:
            continue
        text = (
            f"No estado {uf}, a base ANEEL de micro e minigeração distribuída (MMGD) registra "
            f"{qtd} empreendimentos, totalizando {mw} MW de potência instalada "
            f"(média de {media} kW por empreendimento)."
        )
        meta = {"uf": uf, "qtd_empreendimentos": qtd, "potencia_total_mw": mw, "potencia_media_kw": media}
        conn.execute(
            "INSERT INTO mmgd_vector_docs (doc_id, doc_type, text, metadata) VALUES (?,?,?,?)",
            (f"uf:{uf}", "uf", text, json.dumps(meta, ensure_ascii=False)),
        )
        n += 1

    for uf, fonte, qtd, mw in conn.execute(
        "SELECT uf, fonte_norm, qtd_empreendimentos, potencia_total_mw FROM vw_totais_uf_fonte"
    ):
        if not uf or not fonte:
            continue
        text = (
            f"Em {uf}, a fonte {fonte} responde por {qtd} empreendimentos de geração distribuída, "
            f"somando {mw} MW instalados."
        )
        meta = {"uf": uf, "fonte": fonte, "qtd_empreendimentos": qtd, "potencia_total_mw": mw}
        conn.execute(
            "INSERT INTO mmgd_vector_docs (doc_id, doc_type, text, metadata) VALUES (?,?,?,?)",
            (f"uf_fonte:{uf}:{fonte}", "uf_fonte", text, json.dumps(meta, ensure_ascii=False)),
        )
        n += 1

    for fonte, qtd, mw in conn.execute(
        "SELECT fonte_norm, qtd_empreendimentos, potencia_total_mw FROM vw_totais_fonte"
    ):
        text = (
            f"A fonte {fonte} totaliza {qtd} empreendimentos e {mw} MW de potência instalada "
            f"em todo o Brasil (base MMGD ANEEL)."
        )
        meta = {"fonte": fonte, "qtd_empreendimentos": qtd, "potencia_total_mw": mw}
        conn.execute(
            "INSERT INTO mmgd_vector_docs (doc_id, doc_type, text, metadata) VALUES (?,?,?,?)",
            (f"fonte:{fonte}", "fonte", text, json.dumps(meta, ensure_ascii=False)),
        )
        n += 1

    for uf, faixa, qtd, mw in conn.execute(
        "SELECT uf, faixa_potencia_mex, qtd_empreendimentos, potencia_total_mw FROM vw_faixa_mex"
    ):
        if not uf:
            continue
        text = (
            f"Na faixa de interesse MEx Energia '{faixa}' em {uf}, há {qtd} empreendimentos "
            f"somando {mw} MW — segmento avaliado para prospecção de barramento 800VDC + BESS."
        )
        meta = {"uf": uf, "faixa_potencia_mex": faixa, "qtd_empreendimentos": qtd, "potencia_total_mw": mw}
        conn.execute(
            "INSERT INTO mmgd_vector_docs (doc_id, doc_type, text, metadata) VALUES (?,?,?,?)",
            (f"faixa_mex:{uf}:{faixa}", "faixa_mex", text, json.dumps(meta, ensure_ascii=False)),
        )
        n += 1

    conn.commit()
    return n
