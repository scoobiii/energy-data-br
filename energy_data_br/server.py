"""API HTTP stdlib puro para energy-data-br – zero dependências."""
import json
import sqlite3
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from pathlib import Path

DB_PATH = "/storage/emulated/0/energy-data-br.sqlite"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

def json_response(data, status=200):
    body = json.dumps(data, ensure_ascii=False).encode('utf-8')
    return (body, status, [('Content-Type', 'application/json; charset=utf-8')])

class EnergyAPIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == '/':
            self.send_json({
                "message": "Energy Data BR API (stdlib)",
                "endpoints": [
                    "/stats",
                    "/totais/uf",
                    "/totais/fonte",
                    "/empreendimentos?uf=SP&limit=10",
                    "/ons/carga?area=S&limit=10"
                ]
            })
        elif path == '/stats':
            self.handle_stats()
        elif path == '/totais/uf':
            self.handle_totais_uf()
        elif path == '/totais/fonte':
            self.handle_totais_fonte()
        elif path == '/empreendimentos':
            self.handle_empreendimentos(query)
        elif path == '/ons/carga':
            self.handle_ons_carga(query)
        else:
            self.send_json({"error": "Endpoint não encontrado"}, 404)

    def send_json(self, data, status=200):
        body, status, headers = json_response(data, status)
        self.send_response(status)
        for k, v in headers:
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def handle_stats(self):
        conn = get_db_connection()
        mmgd_raw = conn.execute("SELECT COUNT(*) FROM mmgd_raw").fetchone()[0]
        mmgd_fato = conn.execute("SELECT COUNT(*) FROM mmgd_fato").fetchone()[0]
        ons_carga = conn.execute("SELECT COUNT(*) FROM ons_carga").fetchone()[0]
        conn.close()
        self.send_json({
            "mmgd_raw": mmgd_raw,
            "mmgd_fato": mmgd_fato,
            "ons_carga": ons_carga
        })

    def handle_totais_uf(self):
        conn = get_db_connection()
        rows = conn.execute("""
            SELECT siguf, COUNT(*) as total
            FROM mmgd_fato
            WHERE siguf != ''
            GROUP BY siguf
            ORDER BY total DESC
        """).fetchall()
        conn.close()
        self.send_json([dict(row) for row in rows])

    def handle_totais_fonte(self):
        conn = get_db_connection()
        rows = conn.execute("""
            SELECT dscfontegeracao as fonte,
                   COUNT(*) as empreendimentos,
                   SUM(potencia_instalada_kw) as potencia_total_kw
            FROM mmgd_fato
            WHERE dscfontegeracao != ''
            GROUP BY dscfontegeracao
            ORDER BY potencia_total_kw DESC
        """).fetchall()
        conn.close()
        self.send_json([dict(row) for row in rows])

    def handle_empreendimentos(self, query):
        uf = query.get('uf', [''])[0].upper()
        fonte = query.get('fonte', [''])[0]
        limit = min(int(query.get('limit', ['100'])[0]), 5000)
        offset = int(query.get('offset', ['0'])[0])

        conn = get_db_connection()
        sql = "SELECT cod_empreendimento, siguf, dscfontegeracao, potencia_instalada_kw FROM mmgd_fato WHERE 1=1"
        params = []
        if uf:
            sql += " AND siguf = ?"
            params.append(uf)
        if fonte:
            sql += " AND dscfontegeracao LIKE ?"
            params.append(f"%{fonte}%")
        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        self.send_json([dict(row) for row in rows])

    def handle_ons_carga(self, query):
        area = query.get('area', [''])[0].upper()
        limit = min(int(query.get('limit', ['100'])[0]), 1000)
        offset = int(query.get('offset', ['0'])[0])

        conn = get_db_connection()
        sql = "SELECT area, tipo, data_json FROM ons_carga WHERE 1=1"
        params = []
        if area:
            sql += " AND area = ?"
            params.append(area)
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(sql, params).fetchall()
        conn.close()
        self.send_json([dict(row) for row in rows])

def run_server(host='0.0.0.0', port=8000):
    server = HTTPServer((host, port), EnergyAPIHandler)
    print(f"🚀 Servidor rodando em http://{host}:{port}")
    print(f"📊 Endpoint /stats, /totais/uf, /totais/fonte, /empreendimentos, /ons/carga")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Servidor encerrado.")
        server.shutdown()

if __name__ == '__main__':
    run_server()
