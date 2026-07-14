"""
ETL mmgd_raw -> mmgd_fato, com parada correta.
"""
import logging
import sqlite3
import sys
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
WHERE rowid > ? AND rowid <= ?
ORDER BY rowid
"""


def populate_mmgd_fato(conn: sqlite3.Connection) -> dict:
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=30000")
    cur = conn.cursor()

    total = cur.execute("SELECT COUNT(*) FROM mmgd_raw").fetchone()[0]
    max_rowid = cur.execute("SELECT MAX(rowid) FROM mmgd_raw").fetchone()[0]
    inserted_antes = cur.execute("SELECT COUNT(*) FROM mmgd_fato").fetchone()[0]
    log.info(f"Total mmgd_raw: {total:,} | max_rowid: {max_rowid:,} | já em mmgd_fato: {inserted_antes:,}")

    # Encontra último rowid processado
    last_processed = cur.execute("""
        SELECT COALESCE(MAX(r.rowid), 0)
        FROM mmgd_fato f
        JOIN mmgd_raw r ON f.hash = r.hash
    """).fetchone()[0]
    log.info(f"Retomando do rowid: {last_processed:,}")

    last_rowid = last_processed
    inicio = time.time()

    while last_rowid < max_rowid:
        next_limit = min(last_rowid + BATCH, max_rowid)
        cur.execute(INSERT_SQL, (last_rowid, next_limit))
        batch_count = cur.rowcount
        conn.commit()

        last_rowid = next_limit
        inserido_total = cur.execute("SELECT COUNT(*) FROM mmgd_fato").fetchone()[0]
        pct = (last_rowid / max_rowid) * 100
        decorrido = time.time() - inicio
        taxa = (last_rowid - last_processed) / decorrido if decorrido > 0 else 0
        restante = max_rowid - last_rowid
        eta = restante / taxa if taxa > 0 else 0

        sys.stdout.write(
            f"\r[{pct:5.1f}%] {last_rowid:,}/{max_rowid:,} "
            f"rowid | lote={batch_count} | fato={inserido_total:,} | "
            f"{taxa:,.0f} rowid/s | ETA {eta:.0f}s"
        )
        sys.stdout.flush()

    sys.stdout.write("\n")
    sys.stdout.flush()

    inserted_depois = cur.execute("SELECT COUNT(*) FROM mmgd_fato").fetchone()[0]
    decorrido_total = time.time() - inicio
    log.info(
        f"Concluído em {decorrido_total:.0f}s | "
        f"mmgd_fato: {inserted_depois:,} (+{inserted_depois - inserted_antes:,})"
    )

    return {
        "total_raw": total,
        "fato_antes": inserted_antes,
        "fato_depois": inserted_depois,
        "novos": inserted_depois - inserted_antes,
        "tempo_segundos": decorrido_total,
    }


if __name__ == '__main__':
    import logging as _logging
    _logging.basicConfig(level=_logging.INFO, format='%(asctime)s %(message)s',
                         handlers=[_logging.FileHandler('logs/pop_mmgd_fato.log'), _logging.StreamHandler()])
    conn = sqlite3.connect("energy-data-br.sqlite")
    try:
        populate_mmgd_fato(conn)
    finally:
        conn.close()
