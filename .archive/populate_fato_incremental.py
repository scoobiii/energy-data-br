#!/usr/bin/env python3
"""Popula mmgd_fato incrementalmente (apenas registros novos)."""
import sqlite3
import time
import sys

DB_PATH = "/storage/emulated/0/energy-data-br.sqlite"
BATCH = 10000

def main():
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")

    # Cria tabela de metadados se não existir
    conn.execute("""
        CREATE TABLE IF NOT EXISTS mmgd_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Lê último rowid processado
    row = conn.execute(
        "SELECT value FROM mmgd_meta WHERE key = 'last_processed_rowid'"
    ).fetchone()
    last_row_id = int(row[0]) if row else 0

    # Total de registros a processar (apenas os que ainda não foram)
    total = conn.execute(
        "SELECT COUNT(*) FROM mmgd_raw WHERE raw_json LIKE '%CodEmpreendimento%' AND rowid > ?",
        (last_row_id,)
    ).fetchone()[0]
    print(f"📊 Novos registros a processar: {total:,} (a partir de rowid {last_row_id})")

    if total == 0:
        print("✅ Nenhum registro novo.")
        conn.close()
        return

    processed = 0
    start = time.perf_counter()

    while True:
        cursor = conn.execute("""
            INSERT OR IGNORE INTO mmgd_fato
              (cod_empreendimento, siguf, dscfontegeracao, potencia_instalada_kw, hash)
            SELECT
              json_extract(raw_json, '$.CodEmpreendimento'),
              json_extract(raw_json, '$.SigUF'),
              json_extract(raw_json, '$.DscFonteGeracao'),
              CAST(json_extract(raw_json, '$.MdaPotenciaInstaladaKW') AS REAL),
              hex(randomblob(16)) || hex(randomblob(16))
            FROM mmgd_raw
            WHERE raw_json LIKE '%CodEmpreendimento%'
              AND rowid > ?
            LIMIT ?
        """, (last_row_id, BATCH))

        inserted = cursor.rowcount
        if inserted == 0:
            break

        # Atualiza o último rowid processado (avança o batch)
        last_row_id += BATCH
        processed += inserted

        # Salva progresso a cada lote
        conn.execute(
            "INSERT OR REPLACE INTO mmgd_meta (key, value) VALUES ('last_processed_rowid', ?)",
            (str(last_row_id),)
        )
        conn.commit()

        elapsed = time.perf_counter() - start
        percent = (processed / total) * 100 if total > 0 else 0
        eta = (elapsed / processed) * (total - processed) if processed > 0 else 0
        print(f"  {processed:,} / {total:,} ({percent:.1f}%) | ETA: {eta:.0f}s", end='\r')
        sys.stdout.flush()

    print(f"\n✅ Concluído! {processed:,} registros inseridos em {time.perf_counter() - start:.1f}s")
    conn.close()

if __name__ == "__main__":
    main()
