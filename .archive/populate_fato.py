#!/usr/bin/env python3
"""Popula mmgd_fato a partir de mmgd_raw com barra de progresso."""
import sqlite3
import time
import sys

DB_PATH = "/storage/emulated/0/energy-data-br.sqlite"

def main():
    conn = sqlite3.connect(DB_PATH, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")

    # Total de registros com CodEmpreendimento
    total = conn.execute(
        "SELECT COUNT(*) FROM mmgd_raw WHERE raw_json LIKE '%CodEmpreendimento%'"
    ).fetchone()[0]
    print(f"📊 Total de registros a processar: {total:,}")

    if total == 0:
        print("⚠️ Nenhum registro com CodEmpreendimento encontrado.")
        conn.close()
        return

    batch_size = 5000
    processed = 0
    start_time = time.perf_counter()

    while processed < total:
        conn.execute("""
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
              AND row_id NOT IN (SELECT row_id FROM mmgd_fato)
            LIMIT ?
        """, (batch_size,))

        affected = conn.total_changes
        conn.commit()
        processed += affected

        percent = (processed / total) * 100
        elapsed = time.perf_counter() - start_time
        eta = (elapsed / processed) * (total - processed) if processed > 0 else 0
        print(f"  {processed:,} / {total:,} ({percent:.1f}%) | ETA: {eta:.0f}s", end='\r')
        sys.stdout.flush()

        if affected == 0:
            break

    print(f"\n✅ Concluído! {processed:,} registros inseridos em {time.perf_counter() - start_time:.1f}s")
    conn.close()

if __name__ == "__main__":
    main()
