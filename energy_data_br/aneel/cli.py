#!/usr/bin/env python3
"""CLI unificada para energy-data-br."""
import argparse
import sys
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

    args = parser.parse_args()

    if args.command == "sync":
        if args.source == "aneel":
            # Importação correta: mesmo pacote (aneel)
            from .api_client import fetch_records
            print(f"🔄 Sincronizando ANEEL (limite: {args.max_records or 'todos'})...")
            count = 0
            for record in fetch_records(limit=args.max_records):
                count += 1
                if count % 100 == 0:
                    print(f"   {count} registros...")
            print(f"✅ {count} registros processados")
        elif args.source == "ons":
            # Importação correta: pacote irmão (ons)
            from ..ons.api_carga import fetch_recent_window
            print(f"🔄 Sincronizando ONS (últimos {args.days} dias)...")
            count = 0
            for _ in fetch_recent_window(days=args.days):
                count += 1
            print(f"✅ {count} registros de carga processados")

    elif args.command == "stats":
        print("📊 Estatísticas (implementação pendente)")
    elif args.command == "export-treemap":
        print(f"📊 Exportando treemap para {args.out} (implementação pendente)")
    elif args.command == "build-vectors":
        print("🧠 Gerando documentos para RAG (implementação pendente)")

    return 0

if __name__ == "__main__":
    sys.exit(main())
