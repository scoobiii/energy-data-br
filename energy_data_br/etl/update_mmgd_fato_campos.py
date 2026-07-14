import sqlite3, json, sys, time

def update_campos_faltantes(conn):
    cur = conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA busy_timeout=30000")
    total_fato = cur.execute("SELECT COUNT(*) FROM mmgd_fato WHERE municipio IS NULL").fetchone()[0]
    print(f"Registros a atualizar: {total_fato:,}")
    batch = 50000
    offset = 0
    atualizados = 0
    inicio = time.time()
    while True:
        cur.execute("""
            SELECT f.hash, r.raw_json
            FROM mmgd_fato f
            JOIN mmgd_raw r ON f.hash = r.hash
            WHERE f.municipio IS NULL
            LIMIT ? OFFSET ?
        """, (batch, offset))
        rows = cur.fetchall()
        if not rows:
            break
        for hash_val, raw_json_str in rows:
            data = json.loads(raw_json_str)
            municipio = data.get('NomMunicipio', '') or ''
            distribuidora = data.get('SigAgente', '') or ''
            data_conexao = data.get('DatConexao', '') or ''
            nome_titular = data.get('NomTitularEmpreendimento', '') or ''
            classe_producao = data.get('DscClasseProducao', '') or ''
            subgrupo = data.get('DscSubGrupo', '') or ''
            qtd_uc = data.get('QtdUcRecebeCredito', 0) or 0
            tipo_unidade = data.get('DscTipoUnidadeProdutora', '') or ''
            cur.execute("""
                UPDATE mmgd_fato SET
                    municipio = ?,
                    distribuidora = ?,
                    data_conexao = ?,
                    nome_titular = ?,
                    classe_producao = ?,
                    subgrupo = ?,
                    qtd_uc_recebe_credito = ?,
                    tipo_unidade_produtora = ?
                WHERE hash = ?
            """, (municipio, distribuidora, data_conexao, nome_titular, classe_producao, subgrupo, qtd_uc, tipo_unidade, hash_val))
        conn.commit()
        atualizados += len(rows)
        offset += batch
        decorrido = time.time() - inicio
        print(f"Atualizados {atualizados:,} registros em {decorrido:.0f}s...")
    conn.commit()
    print(f"Concluído: {atualizados:,} registros atualizados.")

if __name__ == '__main__':
    db_path = sys.argv[1] if len(sys.argv) > 1 else "energy-data-br.sqlite"
    conn = sqlite3.connect(db_path)
    update_campos_faltantes(conn)
    conn.close()
