#!/usr/bin/env python3
"""Popula mmgd_fato com progresso, usando rowid da mmgd_raw."""
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

    total = conn.execute(
        "SELECT COUNT(*) FROM mmgd_raw WHERE raw_json LIKE '%CodEmpreendimento%'"
    ).fetchone()[0]
    print(f"📊 Total: {total:,} registros")

    processed = 0
    last_row_id = 0  # rowid da mmgd_raw (não confundir com id da mmgd_fato)
    start = time.perf_counter()

    while True:
        # Insere até BATCH registros com rowid > last_row_id
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

        # Atualiza last_row_id com o maior rowid inserido nesta rodada
        # Para saber, pegamos o último rowid inserido na mmgd_raw correspondente
        # Podemos obter o maior rowid da mmgd_fato (que é independente), mas para avançar,
        # usamos o último rowid da mmgd_raw que foi processado.
        # Uma forma simples: após cada inserção, pegamos o maior rowid da mmgd_raw
        # que já foi processado (baseado no fato que os rowids são sequenciais e nós
        # já passamos por todos até last_row_id). Na verdade, podemos usar o
        # rowid máximo da mmgd_raw que foi inserido, que é aproximadamente
        # last_row_id + inserted, mas para precisão, vamos buscar:
        last_row_id = conn.execute(
            "SELECT MAX(rowid) FROM mmgd_raw WHERE rowid > ? AND raw_json LIKE '%CodEmpreendimento%'",
            (last_row_id,)
        ).fetchone()[0] or last_row_id

        processed += inserted
        elapsed = time.perf_counter() - start
        percent = (processed / total) * 100 if total > 0 else 0
        eta = (elapsed / processed) * (total - processed) if processed > 0 else 0
        print(f"  {processed:,} / {total:,} ({percent:.1f}%) | ETA: {eta:.0f}s", end='\r')
        sys.stdout.flush()

        # Commit a cada lote
        conn.commit()

    print(f"\n✅ Concluído! {processed:,} registros em {time.perf_counter() - start:.1f}s")
    conn.close()

if __name__ == "__main__":
    main()
