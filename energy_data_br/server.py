#!/usr/bin/env python3
"""
energy_data_br/server.py - API REST para energy-data-br.
"""

import json
import sqlite3
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

# Cache simples para consultas pesadas
from functools import lru_cache
import time

@lru_cache(maxsize=32)
def cached_query(query_key: str, ttl: int = 600) -> str:
    """Retorna resultado da query como string JSON, com cache TTL (10 min padrão)."""
    # query_key é ignorada, usamos o tempo real como chave de invalidação
    pass

class SimpleCache:
    def __init__(self, ttl=600):
        self.cache = {}
        self.ttl = ttl
    
    def get(self, key):
        if key in self.cache:
            data, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return data
        return None
    
    def set(self, key, data):
        self.cache[key] = (data, time.time())

cache = SimpleCache(ttl=600)  # 10 minutos


DB_PATH = Path("energy-data-br.sqlite")
WEB_DIR = Path("web")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

class EnergyAPIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == '/stats':
            cached_data = cache.get('stats')
            if cached_data:
                self.send_json(json.loads(cached_data))
                return
            conn = get_db_connection()
            stats = {
                "mmgd_raw": conn.execute("SELECT COUNT(*) FROM mmgd_raw").fetchone()[0],
                "mmgd_fato": conn.execute("SELECT COUNT(*) FROM mmgd_fato").fetchone()[0],
                "ons_carga": conn.execute("SELECT COUNT(*) FROM ons_carga").fetchone()[0],
                "dessem_detalhe": conn.execute("SELECT COUNT(*) FROM dessem_detalhe").fetchone()[0],
                "siga_fato": conn.execute("SELECT COUNT(*) FROM siga_fato").fetchone()[0],
            }
            conn.close()
            cache.set('stats', json.dumps(stats))
            self.send_json(stats)
        elif path == '/totais/uf':
            cached_data = cache.get('totais_uf')
            if cached_data:
                self.send_json(json.loads(cached_data))
                return
            conn = get_db_connection()
            rows = conn.execute("SELECT siguf, COUNT(*) as total FROM mmgd_fato GROUP BY siguf ORDER BY total DESC").fetchall()
            conn.close()
            result = [{"siguf": r["siguf"], "total": r["total"]} for r in rows]
            cache.set('totais_uf', json.dumps(result))
            self.send_json(result)
        elif path.startswith('/empreendimentos'):
            params = dict(urllib.parse.parse_qsl(parsed.query))
            uf = params.get('uf', 'SP')
            limit = int(params.get('limit', 10))
            conn = get_db_connection()
            rows = conn.execute(
                "SELECT cod_empreendimento, siguf, dscfontegeracao, potencia_instalada_kw FROM mmgd_fato WHERE siguf=? LIMIT ?",
                (uf, limit)
            ).fetchall()
            conn.close()
            self.send_json([dict(r) for r in rows])
        elif path.startswith('/siga'):
            params = dict(urllib.parse.parse_qsl(parsed.query))
            tipo = params.get('tipo', 'UHE')
            limit = int(params.get('limit', 5))
            conn = get_db_connection()
            rows = conn.execute(
                "SELECT nome_empreendimento, uf, tipo_geracao, potencia_outorgada_kw, municipios FROM siga_fato WHERE tipo_geracao=? LIMIT ?",
                (tipo, limit)
            ).fetchall()
            conn.close()
            self.send_json([dict(r) for r in rows])
        elif path == '/dashboard':
            self.send_file(str(WEB_DIR / 'dashboard.html'))
        elif path == '/treemap':
            self.send_file(str(WEB_DIR / 'treemap.html'))
        elif path.startswith('/geracao/fonte'):
            params = dict(urllib.parse.parse_qsl(parsed.query))
            inicio = params.get('inicio', '2025-01-01')
            fim = params.get('fim', '2026-12-31')
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT 'Hidráulica' as fonte, SUM(val_ger_hidraulica) as total
                FROM dessem_detalhe WHERE din_programacaodia BETWEEN ? AND ?
                UNION ALL SELECT 'Eólica', SUM(val_ger_eolica) FROM dessem_detalhe WHERE din_programacaodia BETWEEN ? AND ?
                UNION ALL SELECT 'Solar', SUM(val_ger_fotovoltaica) FROM dessem_detalhe WHERE din_programacaodia BETWEEN ? AND ?
                UNION ALL SELECT 'Térmica', SUM(val_ger_termica) FROM dessem_detalhe WHERE din_programacaodia BETWEEN ? AND ?
                UNION ALL SELECT 'PCH', SUM(val_ger_pch) FROM dessem_detalhe WHERE din_programacaodia BETWEEN ? AND ?
                UNION ALL SELECT 'PCT', SUM(val_ger_pct) FROM dessem_detalhe WHERE din_programacaodia BETWEEN ? AND ?
                UNION ALL SELECT 'MMGD', SUM(val_ger_mmgd) FROM dessem_detalhe WHERE din_programacaodia BETWEEN ? AND ?
            """, (inicio, fim, inicio, fim, inicio, fim, inicio, fim, inicio, fim, inicio, fim, inicio, fim))
            rows = cur.fetchall()
            conn.close()
            resultado = [{'fonte': r[0], 'geracao_mw': round(r[1], 2)} for r in rows if r[1] is not None]
            self.send_json(resultado)
        elif path.startswith('/geracao/serie'):
            params = dict(urllib.parse.parse_qsl(parsed.query))
            fonte = params.get('fonte', 'hidraulica')
            inicio = params.get('inicio', '2025-01-01')
            fim = params.get('fim', '2026-12-31')
            col_map = {'hidraulica':'val_ger_hidraulica','eolica':'val_ger_eolica','solar':'val_ger_fotovoltaica','termica':'val_ger_termica','pch':'val_ger_pch','pct':'val_ger_pct','mmgd':'val_ger_mmgd'}
            coluna = col_map.get(fonte, 'val_ger_hidraulica')
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(f"SELECT din_programacaodia, SUM({coluna}) as geracao FROM dessem_detalhe WHERE din_programacaodia BETWEEN ? AND ? GROUP BY din_programacaodia ORDER BY din_programacaodia", (inicio, fim))
            rows = cur.fetchall()
            conn.close()
            resultado = [{'data': r[0], 'geracao_mw': round(r[1], 2)} for r in rows if r[1] is not None]
            self.send_json(resultado)
        elif path == '/token/saldo':
            params = dict(urllib.parse.parse_qsl(parsed.query))
            cliente_id = int(params.get('cliente_id', 0))
            if cliente_id <= 0:
                self.send_json({'error': 'cliente_id obrigatório'}, 400)
                return
            from energy_data_br.tokenizacao import saldo_disponivel
            resultado = saldo_disponivel(cliente_id)
            self.send_json(resultado)
        elif path.startswith('/token/vender'):
            self.send_json({'error': 'Use POST para esta rota'}, 405)
        else:
            self.send_json({"error": "Endpoint não encontrado"}, 404)

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path.startswith('/token/vender'):
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            data = json.loads(body)
            from energy_data_br.tokenizacao import vender_credito, TokenizacaoError
            try:
                transacao_id = vender_credito(
                    data['credito_id'],
                    data['quantidade_kwh'],
                    data['valor_rs'],
                    data.get('valor_token', data['valor_rs'] * 0.25),
                    data.get('tx_blockchain')
                )
                self.send_json({'transacao_id': transacao_id, 'status': 'venda_realizada'})
            except TokenizacaoError as e:
                self.send_json({'error': str(e)}, 400)
        else:
            self.send_json({"error": "Endpoint não encontrado"}, 404)

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def send_file(self, filepath):
        p = Path(filepath)
        if not p.exists():
            self.send_json({"error": "File not found"}, 404)
            return
        self.send_response(200)
        if p.suffix == '.html':
            self.send_header('Content-Type', 'text/html')
        elif p.suffix == '.css':
            self.send_header('Content-Type', 'text/css')
        elif p.suffix == '.js':
            self.send_header('Content-Type', 'application/javascript')
        elif p.suffix == '.json':
            self.send_header('Content-Type', 'application/json')
        else:
            self.send_header('Content-Type', 'application/octet-stream')
        self.end_headers()
        self.wfile.write(p.read_bytes())

def run_server(host='0.0.0.0', port=8000):
    from http.server import ThreadingHTTPServer
    server = ThreadingHTTPServer((host, port), EnergyAPIHandler)
    print(f"Servidor rodando em http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
        server.server_close()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    run_server(args.host, args.port)
