"""
ETL siga_raw -> siga_fato, usando aneel.siga_client (fetch_all + normalize).
Hoje esse ETL NÃO EXISTE em nenhum lugar do sync automatizado — este módulo
fecha essa lacuna.
"""
import logging
import sqlite3

from energy_data_br.aneel.siga_client import fetch_all, normalize

log = logging.getLogger("populate_siga_fato")


def populate_siga_fato(conn: sqlite3.Connection) -> dict:
    conn.execute("PRAGMA journal_mode=WAL")
    cur = conn.cursor()
    inserted = 0
    for rec in fetch_all():
        norm = normalize(rec)
        cur.execute(
            """
            INSERT OR IGNORE INTO siga_fato
                (cod_usina, siguf, dscfonte, potencia_outorgada_kw, hash)
            VALUES (:cod_usina, :siguf, :dscfonte, :potencia_outorgada_kw, :hash)
            """,
            norm,  # ajuste as chaves do dict conforme o retorno real de normalize()
        )
        inserted += cur.rowcount
    conn.commit()
    log.info(f"populate_siga_fato: {inserted:,} registros inseridos/atualizados")
    return {"inserted": inserted}
