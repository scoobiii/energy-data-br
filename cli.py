"""
cli.py — interface de linha de comando `aneel-mmgd`.

Subcomandos:
    sync            baixa dados reais da API ANEEL e carrega no SQLite
    build-vectors    (re)gera os docs de texto para RAG a partir do banco já carregado
    export-treemap   exporta a hierarquia Brasil>UF>Fonte para JSON
    stats            imprime totais agregados no terminal
"""

from __future__ import annotations

import argparse
import sys

from . import api_client, db, export, rules


def cmd_sync(args: argparse.Namespace) -> int:
    print(f"[1/3] Introspectando schema do resource {args.resource_id} ...")
    fields = api_client.fetch_schema(args.resource_id)
    cols = rules.resolve_columns(fields)
    for k, v in cols.items():
        print(f"      {k:16s} -> {v}")
    unresolved = [k for k, v in cols.items() if v is None]
    if unresolved:
        print(f"      [aviso] não resolvidos automaticamente: {unresolved}", file=sys.stderr)

    print(f"[2/3] Conectando/criando SQLite em {args.db} ...")
    conn = db.connect(args.db)

    print("[3/3] Baixando e classificando registros (paginado) ...")
    total = 0

    def on_page(offset, n):
        nonlocal total

    batch: list[dict] = []
    for record in api_client.iter_records(
        resource_id=args.resource_id,
        page_size=args.page_size,
        max_records=args.max_records,
    ):
        batch.append(record)
        if len(batch) >= args.page_size:
            db.insert_records(conn, args.resource_id, batch, cols)
            total += len(batch)
            print(f"      ... {total} registros carregados")
            batch = []
    if batch:
        db.insert_records(conn, args.resource_id, batch, cols)
        total += len(batch)
        print(f"      ... {total} registros carregados")

    conn.close()
    print(f"OK. {total} registros em {args.db}")
    return 0


def cmd_build_vectors(args: argparse.Namespace) -> int:
    conn = db.connect(args.db)
    n = db.build_vector_docs(conn)
    conn.close()
    print(f"OK. {n} documentos de texto (RAG) gerados em mmgd_vector_docs.")
    return 0


def cmd_export_treemap(args: argparse.Namespace) -> int:
    conn = db.connect(args.db)
    tree = export.export_treemap_json(conn, args.out)
    conn.close()
    n_uf = len(tree.get("children", []))
    print(f"OK. {n_uf} UFs exportadas -> {args.out}")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    conn = db.connect(args.db)
    s = export.totals_summary(conn)
    conn.close()
    print(f"Empreendimentos: {s['qtd_empreendimentos']}")
    print(f"Potência total : {s['potencia_total_mw']} MW")
    print("\nPor fonte:")
    for row in s["por_fonte"]:
        print(f"  {row['fonte']:8s} {row['qtd']:>8} empreend. {row['mw']:>12.3f} MW")
    print("\nPor UF (top 10):")
    for row in s["por_uf"][:10]:
        print(f"  {row['uf']:4s} {row['qtd']:>8} empreend. {row['mw']:>12.3f} MW")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="aneel-mmgd", description=__doc__)
    p.add_argument("--db", default="aneel_mmgd.sqlite", help="caminho do arquivo SQLite")
    sub = p.add_subparsers(dest="command", required=True)

    p_sync = sub.add_parser("sync", help="baixa dados reais da API ANEEL e carrega no SQLite")
    p_sync.add_argument("--resource-id", default=api_client.DEFAULT_RESOURCE_ID)
    p_sync.add_argument("--page-size", type=int, default=api_client.DEFAULT_PAGE_SIZE)
    p_sync.add_argument("--max-records", type=int, default=None, help="limite p/ teste rápido")
    p_sync.set_defaults(func=cmd_sync)

    p_vec = sub.add_parser("build-vectors", help="gera docs de texto p/ RAG a partir do banco")
    p_vec.set_defaults(func=cmd_build_vectors)

    p_tree = sub.add_parser("export-treemap", help="exporta JSON Brasil>UF>Fonte")
    p_tree.add_argument("--out", default="web/aneel_mmgd_treemap.json")
    p_tree.set_defaults(func=cmd_export_treemap)

    p_stats = sub.add_parser("stats", help="imprime totais agregados")
    p_stats.set_defaults(func=cmd_stats)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
