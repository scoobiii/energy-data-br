"""
ETL mmgd_raw -> mmgd_fato, extraído de sync_lock.sh (mantendo a correção de
paginação já aplicada: MAX(rowid) escopado por subquery com o mesmo LIMIT).
"""
import logging
import sqlite3
import time

log = logging.getLogger("populate_mmgd_fato")
BATCH = 50_000

INSERT_SQL = """
INSERT OR IGNORE INTO mmgd_fato
    (cod_empreendimento, siguf, dscfontegeracao, potencia_instalada_kw,
     modalidade, faixa_regulatoria, hash)
SELECT
    json_extract(raw_json,'$.CodEmpreendimento'),
    json_extract(raw_json,'$.SigUF'),
    LOWER(json_extract(raw_json,'$.DscFonteGeracao')),
    CAST(REPLACE(COALESCE(json_extract(raw_json,'$.MdaPotenciaInstaladaKW'),'0'),',','.') AS REAL),
    LOWER(json_extract(raw_json,'$.SigModalidadeEmpreendimento')),
    CASE
        WHEN CAST(REPLACE(COALESCE(json_extract(raw_json,'$.MdaPotenciaInstaladaKW'),'0'),',','.') AS REAL) <= 75 THEN 'microgeracao'
        WHEN CAST(REPLACE(COALESCE(json_extract(raw_json,'$.MdaPotenciaInstaladaKW'),'0'),',','.') AS REAL) <= 5000 THEN 'minigeracao'
        ELSE 'geracao'
    END,
    hash
FROM mmgd_raw
WHERE rowid > ?
ORDER BY rowid
LIMIT ?
"""

MAX_ROWID_SQL = """
SELECT MAX(rowid) FROM (
    SELECT rowid FROM mmgd_raw WHERE rowid > ? ORDER BY rowid LIMIT ?
)
"""


def populate_mmgd_fato(conn: sqlite3.Connection) -> dict:
    conn.execute("PRAGMA journal_mode=WAL")
    cur = conn.cursor()
    total = cur.execute("SELECT COUNT(*) FROM mmgd_raw").fetchone()[0]
    inserted = cur.execute("SELECT COUNT(*) FROM mmgd_fato").fetchone()[0]
    log.info(f"Total mmgd_raw: {total:,} | já em mmgd_fato: {inserted:,}")

    last_rowid = 0
    start = time.time()
    while True:
        cur.execute(INSERT_SQL, (last_rowid, BATCH))
        batch_count = cur.rowcount
        novo_last_rowid = cur.execute(MAX_ROWID_SQL, (last_rowid, BATCH)).fetchone()[0]
        if novo_last_rowid is None:
            break  # fim real, sem mais linhas no intervalo
        last_rowid = novo_last_rowid
        inserted += batch_count
        conn.commit()
        elapsed = time.time() - start
        log.info(f"{inserted:,}/{total:,} ({100*inserted/total:.1f}%) | lote={batch_count} | {elapsed:.0f}s")

    log.info("populate_mmgd_fato: concluído")
    return {"total": total, "inserted": inserted}
