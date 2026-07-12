#!/bin/bash
DB="/storage/emulated/0/energy-data-br.sqlite"

echo "=== CORREÇÃO DEFINITIVA energy-data-br ==="
echo "Banco atual:"
ls -lh "$DB"
echo ""

# 1. VACUUM (mantendo WAL)
echo "1. VACUUM (10-15 min) - NÃO DERRUBA ARROMBAD(A)O!"
echo "   Monitorar em outro terminal: watch -n 10 'ls -lh $DB'"
echo ""

time sqlite3 "$DB" << 'SQL'
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=-256000;
VACUUM;
ANALYZE;
SQL

echo ""
echo "Tamanho após VACUUM:"
ls -lh "$DB"
echo ""

# 2. Índices UNIQUE
echo "2. Criando índices UNIQUE (constraints)..."
sqlite3 "$DB" << 'SQL'
DROP INDEX IF EXISTS idx_mmgd_raw_hash;
DROP INDEX IF EXISTS idx_mmgd_fato_hash;

CREATE UNIQUE INDEX idx_mmgd_raw_hash ON mmgd_raw(hash);
CREATE UNIQUE INDEX idx_mmgd_fato_hash ON mmgd_fato(hash);

SELECT '✅ ' || name || ': ' || sql 
FROM sqlite_master 
WHERE type='index' AND name LIKE '%hash%';
SQL

echo ""

# 3. Popular mmgd_fato com barra de progresso
echo "3. Populando mmgd_fato (~3.8M registros)"
echo "   Isso vai demorar 15-25 minutos..."
echo ""

python3 << 'PYCODE'
import sqlite3
import sys
import time

DB_PATH = "/storage/emulated/0/energy-data-br.sqlite"
BATCH_SIZE = 50000

conn = sqlite3.connect(DB_PATH)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA synchronous=NORMAL")
conn.execute("PRAGMA cache_size=-256000")
cur = conn.cursor()

# Contar total
total = cur.execute("""
    SELECT COUNT(*) FROM mmgd_raw 
    WHERE hash IS NOT NULL 
      AND hash != '' 
      AND json_extract(raw_json, '$.SigUF') IS NOT NULL
""").fetchone()[0]

print(f"📊 Total de registros: {total:,}")
print("")

# Limpar mmgd_fato
cur.execute("DELETE FROM mmgd_fato")
conn.commit()

# Processar em batches usando rowid (mais eficiente que OFFSET)
inserted = 0
last_rowid = 0
start_time = time.time()

while inserted < total:
    cur.execute(f"""
        INSERT INTO mmgd_fato (
            cod_empreendimento, siguf, dscfontegeracao, 
            potencia_instalada_kw, modalidade, faixa_regulatoria, hash
        )
        SELECT 
            json_extract(raw_json, '$.CodEmpreendimento'),
            json_extract(raw_json, '$.SigUF'),
            LOWER(json_extract(raw_json, '$.DscFonteGeracao')),
            CAST(REPLACE(COALESCE(json_extract(raw_json, '$.MdaPotenciaInstaladaKW'), '0'), ',', '.') AS REAL),
            LOWER(json_extract(raw_json, '$.SigModalidadeEmpreendimento')),
            CASE 
                WHEN CAST(REPLACE(COALESCE(json_extract(raw_json, '$.MdaPotenciaInstaladaKW'), '0'), ',', '.') AS REAL) <= 75 THEN 'microgeracao'
                WHEN CAST(REPLACE(COALESCE(json_extract(raw_json, '$.MdaPotenciaInstaladaKW'), '0'), ',', '.') AS REAL) <= 5000 THEN 'minigeracao'
                ELSE 'geracao'
            END,
            hash
        FROM mmgd_raw
        WHERE rowid > {last_rowid}
          AND hash IS NOT NULL 
          AND hash != ''
          AND json_extract(raw_json, '$.SigUF') IS NOT NULL
        ORDER BY rowid
        LIMIT {BATCH_SIZE}
    """)
    
    batch_count = cur.rowcount
    if batch_count == 0:
        break
    
    last_rowid = cur.execute("""
        SELECT MAX(rowid) FROM mmgd_raw 
        WHERE rowid > ? 
          AND hash IS NOT NULL 
          AND hash != ''
    """, (last_rowid,)).fetchone()[0]
    
    inserted += batch_count
    conn.commit()
    
    # Barra de progresso
    progress = (inserted / total) * 100
    elapsed = time.time() - start_time
    eta = (elapsed / inserted) * (total - inserted) if inserted > 0 else 0
    
    bar_length = 40
    filled = int(bar_length * progress / 100)
    bar = '█' * filled + '░' * (bar_length - filled)
    
    sys.stdout.write(f"\r[{bar}] {progress:5.1f}% ({inserted:,}/{total:,}) | ETA: {eta/60:.1f}min")
    sys.stdout.flush()

elapsed_total = time.time() - start_time
print(f"\n\n✅ INSERT concluído em {elapsed_total/60:.1f} minutos!")

cur.execute("SELECT COUNT(*) FROM mmgd_fato")
fato_count = cur.fetchone()[0]
print(f"📊 Registros em mmgd_fato: {fato_count:,}")

conn.close()
PYCODE

echo ""
echo "=== VERIFICAÇÃO FINAL ==="
echo ""

echo "Integridade do banco:"
sqlite3 "$DB" "PRAGMA integrity_check;"
echo ""

echo "Contagens:"
sqlite3 "$DB" << 'SQL'
SELECT 'mmgd_raw: ' || COUNT(*) FROM mmgd_raw;
SELECT 'mmgd_fato: ' || COUNT(*) FROM mmgd_fato;
SELECT 'ons_carga: ' || COUNT(*) FROM ons_carga;
SQL
echo ""

echo "Índices UNIQUE:"
sqlite3 "$DB" "SELECT name, sql FROM sqlite_master WHERE type='index' AND name LIKE '%hash%';"
echo ""

echo "Tamanho final:"
ls -lh "$DB"
echo ""

echo "✅ BANCO CORRIGIDO COM SUCESSO!"
echo ""
echo "Próximos passos:"
echo "1. Testar API: curl http://localhost:8000/stats"
echo "2. Validar dados: curl http://localhost:8000/totais/uf"
echo "3. Commit: git add -A && git commit -m 'fix: banco corrigido com UNIQUE constraints'"
