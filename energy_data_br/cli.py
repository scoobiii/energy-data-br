#!/usr/bin/env python3
"""CLI unificada para energy-data-br."""
import argparse
import sys
import sqlite3
import json
from pathlib import Path

def main():
    parser = argparse.ArgumentParser(description="ETL de dados de energia do Brasil")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # sync
    sync = subparsers.add_parser("sync", help="Sincroniza dados")
    sync.add_argument("--source", choices=["aneel", "ons"], required=True)
    sync.add_argument("--max-records", type=int, help="Limite de registros")
    sync.add_argument("--days", type=int, default=1, help="Dias para ONS")
    sync.add_argument("--db", default="energy-data-br.sqlite")

    # stats
    stats = subparsers.add_parser("stats", help="Estatísticas")
    stats.add_argument("--db", default="energy-data-br.sqlite")

    # export-treemap
    treemap = subparsers.add_parser("export-treemap", help="Exporta treemap")
    treemap.add_argument("--out", default="web/treemap.json")
    treemap.add_argument("--db", default="energy-data-br.sqlite")

    # build-vectors
    vectors = subparsers.add_parser("build-vectors", help="Gera docs para RAG")
    vectors.add_argument("--db", default="energy-data-br.sqlite")

    # serve (API)
    serve = subparsers.add_parser("serve", help="Inicia servidor HTTP com a API")
    serve.add_argument("--host", default="0.0.0.0", help="Host para bind")
    serve.add_argument("--port", type=int, default=8000, help="Porta para bind")
    serve.add_argument("--reload", action="store_true", help="Recarregar automaticamente (desenvolvimento)")

    args = parser.parse_args()

    if args.command == "sync":
        if args.source == "aneel":
            sync_aneel(args.db, args.max_records)
        elif args.source == "ons":
            sync_ons(args.db, args.days)
    elif args.command == "stats":
        show_stats(args.db)
    elif args.command == "export-treemap":
        print("📊 Exportando treemap (implementação futura)")
    elif args.command == "build-vectors":
        print("🧠 Gerando documentos para RAG (implementação futura)")
    elif args.command == "serve":
        serve_api(args.host, args.port, args.reload)

    return 0

def sync_aneel(db_path, max_records):
    """Sincroniza ANEEL usando get_all_records (ZIP snapshot)."""
    from energy_data_br.aneel.api_client import get_all_records
    from energy_data_br.db import connect, init_db
    conn = connect(db_path)
    init_db(conn)
    print(f"🔄 Sincronizando ANEEL (limite: {max_records or 'todos'})...")
    count = 0
    for rec in get_all_records(max_records=max_records):
        hash_ = rec.get('_hash', '')
        cursor = conn.execute(
            """INSERT OR IGNORE INTO mmgd_raw 
               (source_resource_id, raw_json, hash) 
               VALUES (?, ?, ?)""",
            ("aneel_mmgd", json.dumps(rec, ensure_ascii=False), hash_)
        )
        count += 1
        if max_records and count >= max_records:
            break
        if count % 100 == 0:
            print(f"  {count} registros...")
            conn.commit()
    conn.commit()
    conn.close()
    print(f"✅ {count} registros ANEEL salvos")

def sync_ons(db_path, days):
    """Sincroniza ONS usando fetch_recent_window."""
    from energy_data_br.ons.api_carga import fetch_recent_window
    from energy_data_br.db import connect, init_db
    conn = connect(db_path)
    init_db(conn)
    # Garantir tabela ons_carga (caso schema.sql não tenha)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS ons_carga (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            area TEXT NOT NULL,
            data_json TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print(f"🔄 Sincronizando ONS (últimos {days} dias)...")
    count = 0
    for rec in fetch_recent_window(days=days):
        conn.execute(
            "INSERT INTO ons_carga (tipo, area, data_json) VALUES (?, ?, ?)",
            (rec.get('_fonte', 'verificada'), rec.get('_area', ''), json.dumps(rec))
        )
        count += 1
        if count % 100 == 0:
            print(f"  {count} registros...")
            conn.commit()
    conn.commit()
    conn.close()
    print(f"✅ {count} registros ONS salvos")

def show_stats(db_path):
    """Mostra estatísticas do banco."""
    if not Path(db_path).exists():
        print(f"❌ Banco {db_path} não encontrado.")
        return
    from energy_data_br.db import connect
    conn = connect(db_path)
    try:
        aneel = conn.execute("SELECT COUNT(*) FROM mmgd_raw").fetchone()[0]
    except sqlite3.OperationalError:
        aneel = 0
    try:
        ons = conn.execute("SELECT COUNT(*) FROM ons_carga").fetchone()[0]
    except sqlite3.OperationalError:
        ons = 0
    print(f"📊 Estatísticas:\n  ANEEL (mmgd_raw): {aneel} registros\n  ONS (ons_carga): {ons} registros")
    conn.close()

def serve_api(host: str, port: int, reload: bool):
    from energy_data_br.server import run_server
    run_server(host, port)
    """Inicia o servidor FastAPI."""
    try:
        import uvicorn
        from energy_data_br.server import app
    except ImportError as e:
        print(f"❌ Dependência faltando: {e}")
        print("   Instale com: pip install fastapi uvicorn")
        sys.exit(1)
    print(f"🚀 Iniciando API em http://{host}:{port}")
    print(f"📚 Documentação Swagger em http://{host}:{port}/docs")
    uvicorn.run(app, host=host, port=port, reload=reload)

if __name__ == "__main__":
    sys.exit(main())
