#!/bin/bash
LOCKFILE="$HOME/energy-data-br/.locks/sync.lock"
if [ -f "$LOCKFILE" ]; then
    echo "❌ Já existe operação rodando. Aborta."
    exit 1
fi
touch "$LOCKFILE" || { echo "❌ não conseguiu criar lock"; exit 1; }
trap "rm -f $LOCKFILE" EXIT

python3 -c "
import sqlite3, time, json
DB = '/storage/emulated/0/energy-data-br.sqlite'
BATCH = 50000
conn = sqlite3.connect(DB)
conn.execute('PRAGMA journal_mode=WAL')
cur = conn.cursor()
total = cur.execute('SELECT COUNT(*) FROM mmgd_raw').fetchone()[0]
ja_feito = cur.execute('SELECT COUNT(*) FROM mmgd_fato').fetchone()[0]
print(f'Total mmgd_raw: {total:,} | já em mmgd_fato: {ja_feito:,}')

last_rowid = 0
inserted = ja_feito
start = time.time()
while True:
    cur.execute(f'''INSERT OR IGNORE INTO mmgd_fato
        (cod_empreendimento, siguf, dscfontegeracao, potencia_instalada_kw, modalidade, faixa_regulatoria, hash)
        SELECT json_extract(raw_json,'\$.CodEmpreendimento'), json_extract(raw_json,'\$.SigUF'),
               LOWER(json_extract(raw_json,'\$.DscFonteGeracao')),
               CAST(REPLACE(COALESCE(json_extract(raw_json,'\$.MdaPotenciaInstaladaKW'),'0'),',','.') AS REAL),
               LOWER(json_extract(raw_json,'\$.SigModalidadeEmpreendimento')),
               CASE WHEN CAST(REPLACE(COALESCE(json_extract(raw_json,'\$.MdaPotenciaInstaladaKW'),'0'),',','.') AS REAL) <= 75 THEN 'microgeracao'
                    WHEN CAST(REPLACE(COALESCE(json_extract(raw_json,'\$.MdaPotenciaInstaladaKW'),'0'),',','.') AS REAL) <= 5000 THEN 'minigeracao'
                    ELSE 'geracao' END, hash
        FROM mmgd_raw WHERE rowid > {last_rowid} ORDER BY rowid LIMIT {BATCH}''')
    batch = cur.rowcount
    # CORRIGIDO: MAX escopado dentro de subquery com o mesmo LIMIT, não sobre a tabela inteira
    row = cur.execute(f'SELECT MAX(rowid) FROM (SELECT rowid FROM mmgd_raw WHERE rowid > {last_rowid} ORDER BY rowid LIMIT {BATCH})').fetchone()
    novo_last_rowid = row[0]
    if novo_last_rowid is None:
        break  # sem mais linhas de fato, agora sim é fim real
    last_rowid = novo_last_rowid
    inserted += batch
    conn.commit()
    elapsed = time.time() - start
    print(f'{inserted:,}/{total:,} ({100*inserted/total:.1f}%) | lote={batch} | {elapsed:.0f}s')
print('populate: concluído de verdade')
conn.close()
"
