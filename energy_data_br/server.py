#!/usr/bin/env python3
"""
energy_data_br/server.py – API REST consolidada para energy-data-br.
Inclui todos os endpoints: MMGD, SIGA, ONS, DESSEM, Tokenização, Predição.
ThreadingHTTPServer + cache de consultas pesadas.
"""

import json
import sqlite3
import time
import urllib.parse
from datetime import datetime, timedelta
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path

DB_PATH = Path("energy-data-br.sqlite")
if not DB_PATH.exists():
    DB_PATH = Path("/storage/emulated/0/energy-data-br.sqlite")
WEB_DIR = Path("web")

# Cache simples (TTL 10 minutos)
class SimpleCache:
    def __init__(self, ttl=600):
        self.cache = {}
        self.ttl = ttl
    def get(self, key):
        if key in self.cache:
            data, ts = self.cache[key]
            if time.time() - ts < self.ttl:
                return data
        return None
    def set(self, key, data):
        self.cache[key] = (data, time.time())
cache = SimpleCache(ttl=600)

def get_db_connection():
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

class EnergyAPIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Rota raiz
        if path == '/':
            self.send_json({
                "message": "Energy Data BR API (stdlib)",
                "endpoints": [
                    "/stats", "/totais/uf", "/totais/fonte",
                    "/empreendimentos", "/ons/carga", "/siga",
                    "/siga/geojson", "/totais/temporal", "/growth",
                    "/treemap/brasil", "/treemap/uf/{uf}",
                    "/geracao/fonte", "/geracao/serie", "/geracao/atual",
                    "/carga/serie", "/mmgd/serie",
                    "/predicao/carga", "/predicao/mmgd",
                    "/token/saldo", "/token/vender (POST)",
                    "/dashboard", "/treemap"
                ]
            })

        # === MMGD ===
        elif path == '/stats':
            cached = cache.get('stats')
            if cached:
                self.send_json(json.loads(cached))
                return
            conn = get_db_connection()
            tables = ['mmgd_raw', 'mmgd_fato', 'ons_carga', 'dessem_detalhe', 'siga_fato']
            stats = {}
            for table in tables:
                try:
                    stats[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                except sqlite3.OperationalError:
                    stats[table] = None
            conn.close()
            cache.set('stats', json.dumps(stats))
            self.send_json(stats)

        elif path == '/totais/uf':
            cached = cache.get('totais_uf')
            if cached:
                self.send_json(json.loads(cached))
                return
            conn = get_db_connection()
            rows = conn.execute("""
                SELECT siguf, COUNT(*) as total
                FROM mmgd_fato WHERE siguf != ''
                GROUP BY siguf ORDER BY total DESC
            """).fetchall()
            conn.close()
            result = [dict(r) for r in rows]
            cache.set('totais_uf', json.dumps(result))
            self.send_json(result)

        elif path == '/totais/fonte':
            conn = get_db_connection()
            rows = conn.execute("""
                SELECT dscfontegeracao as fonte,
                       COUNT(*) as empreendimentos,
                       SUM(potencia_instalada_kw) as potencia_total_kw
                FROM mmgd_fato WHERE dscfontegeracao != ''
                GROUP BY dscfontegeracao ORDER BY empreendimentos DESC
            """).fetchall()
            conn.close()
            self.send_json([dict(r) for r in rows])

        elif path == '/empreendimentos':
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
            self.send_json([dict(r) for r in rows])

        elif path == '/mmgd/serie':
            uf = query.get('uf', ['MG'])[0]
            fonte = query.get('fonte', [None])[0]
            inicio = query.get('inicio', ['2015-01-01'])[0]
            fim = query.get('fim', ['2026-12-31'])[0]
            conn = get_db_connection()
            cur = conn.cursor()
            q = "SELECT substr(data_conexao,1,7) as mes, SUM(potencia_instalada_kw) as total_kw FROM mmgd_fato WHERE siguf=? AND data_conexao BETWEEN ? AND ?"
            params_sql = [uf, inicio, fim]
            if fonte:
                q += " AND dscfontegeracao=?"
                params_sql.append(fonte.lower())
            q += " GROUP BY mes ORDER BY mes"
            cur.execute(q, params_sql)
            rows = cur.fetchall()
            conn.close()
            self.send_json([{'mes': r['mes'], 'potencia_kw': r['total_kw']} for r in rows])

        # === ONS CARGA ===
        elif path == '/ons/carga':
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
            self.send_json([dict(r) for r in rows])

        elif path == '/carga/serie':
            area = query.get('area', ['S'])[0]
            inicio = query.get('inicio', [(datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')])[0]
            fim = query.get('fim', [datetime.utcnow().strftime('%Y-%m-%d')])[0]
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT data_json FROM ons_carga WHERE area=? AND json_extract(data_json,'$.din_referenciautc') BETWEEN ? AND ? ORDER BY data_json", (area, inicio, fim))
            rows = cur.fetchall()
            conn.close()
            resultado = []
            for r in rows:
                data = json.loads(r['data_json'])
                resultado.append({'data': data.get('din_referenciautc'), 'carga': data.get('val_cargaglobal')})
            self.send_json(resultado)

        # === SIGA ===
        elif path == '/siga':
            tipo = query.get('tipo', [''])[0].upper()
            uf = query.get('uf', [''])[0].upper()
            limit = min(int(query.get('limit', ['100'])[0]), 5000)
            offset = int(query.get('offset', ['0'])[0])
            conn = get_db_connection()
            sql = "SELECT nome_empreendimento, uf, tipo_geracao, potencia_outorgada_kw, municipios FROM siga_fato WHERE 1=1"
            params = []
            if tipo:
                sql += " AND tipo_geracao = ?"
                params.append(tipo)
            if uf:
                sql += " AND uf = ?"
                params.append(uf)
            sql += " ORDER BY potencia_outorgada_kw DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            rows = conn.execute(sql, params).fetchall()
            conn.close()
            self.send_json([dict(r) for r in rows])

        elif path == '/siga/geojson':
            limit = min(int(query.get('limit', ['100'])[0]), 5000)
            conn = get_db_connection()
            rows = conn.execute("""
                SELECT nome_empreendimento, uf, tipo_geracao, potencia_outorgada_kw, lat, lon
                FROM siga_fato WHERE lat IS NOT NULL AND lat != 0 AND lon IS NOT NULL AND lon != 0
                ORDER BY potencia_outorgada_kw DESC LIMIT ?
            """, (limit,)).fetchall()
            conn.close()
            features = [{
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [r['lon'], r['lat']]},
                "properties": dict(r)
            } for r in rows]
            self.send_json({"type": "FeatureCollection", "features": features})

        # === DESSEM / GERAÇÃO ===
        elif path == '/geracao/fonte':
            inicio = query.get('inicio', ['2025-01-01'])[0]
            fim = query.get('fim', ['2026-12-31'])[0]
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("""
                SELECT 'Hidráulica' as fonte, SUM(val_ger_hidraulica) as total FROM dessem_detalhe WHERE din_programacaodia BETWEEN ? AND ?
                UNION ALL SELECT 'Eólica', SUM(val_ger_eolica) FROM dessem_detalhe WHERE din_programacaodia BETWEEN ? AND ?
                UNION ALL SELECT 'Solar', SUM(val_ger_fotovoltaica) FROM dessem_detalhe WHERE din_programacaodia BETWEEN ? AND ?
                UNION ALL SELECT 'Térmica', SUM(val_ger_termica) FROM dessem_detalhe WHERE din_programacaodia BETWEEN ? AND ?
                UNION ALL SELECT 'PCH', SUM(val_ger_pch) FROM dessem_detalhe WHERE din_programacaodia BETWEEN ? AND ?
                UNION ALL SELECT 'PCT', SUM(val_ger_pct) FROM dessem_detalhe WHERE din_programacaodia BETWEEN ? AND ?
                UNION ALL SELECT 'MMGD', SUM(val_ger_mmgd) FROM dessem_detalhe WHERE din_programacaodia BETWEEN ? AND ?
            """, (inicio, fim, inicio, fim, inicio, fim, inicio, fim, inicio, fim, inicio, fim, inicio, fim))
            rows = cur.fetchall()
            conn.close()
            self.send_json([{'fonte': r[0], 'geracao_mw': round(r[1], 2)} for r in rows if r[1] is not None])

        elif path == '/geracao/serie':
            fonte = query.get('fonte', ['hidraulica'])[0]
            inicio = query.get('inicio', ['2025-01-01'])[0]
            fim = query.get('fim', ['2026-12-31'])[0]
            col_map = {'hidraulica':'val_ger_hidraulica','eolica':'val_ger_eolica','solar':'val_ger_fotovoltaica','termica':'val_ger_termica','pch':'val_ger_pch','pct':'val_ger_pct','mmgd':'val_ger_mmgd'}
            coluna = col_map.get(fonte, 'val_ger_hidraulica')
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute(f"SELECT din_programacaodia, SUM({coluna}) as geracao FROM dessem_detalhe WHERE din_programacaodia BETWEEN ? AND ? GROUP BY din_programacaodia ORDER BY din_programacaodia", (inicio, fim))
            rows = cur.fetchall()
            conn.close()
            self.send_json([{'data': r[0], 'geracao_mw': round(r[1], 2)} for r in rows if r[1] is not None])

        elif path == '/geracao/atual':
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT din_programacaodia, val_ger_hidraulica, val_ger_eolica, val_ger_fotovoltaica, val_ger_termica, val_ger_pch, val_ger_pct, val_ger_mmgd FROM dessem_detalhe ORDER BY din_programacaodia DESC LIMIT 1")
            row = cur.fetchone()
            conn.close()
            if row:
                resultado = {
                    'data': row['din_programacaodia'],
                    'Hidráulica': row['val_ger_hidraulica'],
                    'Eólica': row['val_ger_eolica'],
                    'Solar': row['val_ger_fotovoltaica'],
                    'Térmica': row['val_ger_termica'],
                    'PCH': row['val_ger_pch'],
                    'PCT': row['val_ger_pct'],
                    'MMGD': row['val_ger_mmgd']
                }
            else:
                resultado = {}
            self.send_json(resultado)

        # === PREDIÇÃO ===
        elif path == '/predicao/carga':
            from energy_data_br.predicao import prever_carga
            area = query.get('area', ['S'])[0]
            dias = int(query.get('dias', ['7'])[0])
            resultado = prever_carga(area, dias)
            self.send_json(resultado)

        elif path == '/predicao/mmgd':
            from energy_data_br.predicao import prever_mmgd
            uf = query.get('uf', ['MG'])[0]
            meses = int(query.get('meses', ['12'])[0])
            resultado = prever_mmgd(uf, meses)
            self.send_json(resultado)

        # === TOKENIZAÇÃO ===
        elif path == '/token/saldo':
            cliente_id = int(query.get('cliente_id', ['0'])[0])
            if cliente_id <= 0:
                self.send_json({'error': 'cliente_id obrigatório'}, 400)
                return
            from energy_data_br.tokenizacao import saldo_disponivel
            resultado = saldo_disponivel(cliente_id)
            self.send_json(resultado)

        elif path == '/token/vender':
            self.send_json({'error': 'Use POST para esta rota'}, 405)

        # === TEMPORAL / GROWTH ===
        elif path == '/totais/temporal':
            days = min(int(query.get('days', ['30'])[0]), 90)
            conn = get_db_connection()
            rows = conn.execute("""
                SELECT dat_referencia, SUM(val_cargaglobal) as carga_total
                FROM ons_carga WHERE dat_referencia >= date('now', ?)
                GROUP BY dat_referencia ORDER BY dat_referencia
            """, (f'-{days} days',)).fetchall()
            conn.close()
            self.send_json([dict(r) for r in rows])

        elif path == '/growth':
            limit = min(int(query.get('limit', ['30'])[0]), 365)
            conn = get_db_connection()
            rows = conn.execute("""
                SELECT data, mmgd_ativos, mmgd_potencia_kw,
                       siga_ativos, siga_potencia_kw,
                       ons_carga_media_mw, total_registros
                FROM growth_log ORDER BY data DESC LIMIT ?
            """, (limit,)).fetchall()
            conn.close()
            self.send_json([dict(r) for r in rows])

        # === TREEMAP ===
        elif path == '/treemap/brasil':
            nivel = query.get('nivel', ['uf_fonte'])[0]
            conn = get_db_connection()
            if nivel == 'fonte':
                rows = conn.execute("""
                    SELECT dscfontegeracao as fonte, SUM(potencia_instalada_kw) as valor_kw, COUNT(*) as empreendimentos
                    FROM mmgd_fato WHERE dscfontegeracao != ''
                    GROUP BY dscfontegeracao ORDER BY valor_kw DESC
                """).fetchall()
                conn.close()
                self.send_json({"name": "Brasil", "children": [{"name": r["fonte"], "value": r["valor_kw"], "empreendimentos": r["empreendimentos"]} for r in rows]})
                return
            if nivel == 'uf':
                rows = conn.execute("""
                    SELECT siguf as uf, SUM(potencia_instalada_kw) as valor_kw, COUNT(*) as empreendimentos
                    FROM mmgd_fato WHERE siguf != ''
                    GROUP BY siguf ORDER BY valor_kw DESC
                """).fetchall()
                conn.close()
                self.send_json({"name": "Brasil", "children": [{"name": r["uf"], "value": r["valor_kw"], "empreendimentos": r["empreendimentos"]} for r in rows]})
                return
            rows = conn.execute("""
                SELECT siguf as uf, dscfontegeracao as fonte, SUM(potencia_instalada_kw) as valor_kw, COUNT(*) as empreendimentos
                FROM mmgd_fato WHERE siguf != '' AND dscfontegeracao != ''
                GROUP BY siguf, dscfontegeracao ORDER BY siguf, valor_kw DESC
            """).fetchall()
            conn.close()
            por_uf = {}
            for r in rows:
                por_uf.setdefault(r["uf"], []).append({"name": r["fonte"], "value": r["valor_kw"], "empreendimentos": r["empreendimentos"]})
            children = [{"name": uf, "children": fontes} for uf, fontes in sorted(por_uf.items(), key=lambda kv: -sum(f["value"] for f in kv[1]))]
            self.send_json({"name": "Brasil", "children": children})

        elif path.startswith('/treemap/uf/'):
            uf = path.split('/')[-1].upper()
            limit = min(int(query.get('limit', ['100'])[0]), 1000)
            fonte_tipo = query.get('tipo', ['siga'])[0]
            conn = get_db_connection()
            if fonte_tipo == 'mmgd':
                rows = conn.execute("""
                    SELECT cod_empreendimento as name, potencia_instalada_kw as value, dscfontegeracao as fonte
                    FROM mmgd_fato WHERE siguf = ? ORDER BY potencia_instalada_kw DESC LIMIT ?
                """, (uf, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT nome_empreendimento as name, potencia_outorgada_kw as value, tipo_geracao as fonte
                    FROM siga_fato WHERE uf = ? ORDER BY potencia_outorgada_kw DESC LIMIT ?
                """, (uf, limit)).fetchall()
            conn.close()
            self.send_json({"name": uf, "children": [dict(r) for r in rows]})

        # === PÁGINAS ESTÁTICAS ===
        elif path == '/dashboard':
            self.send_file(str(WEB_DIR / 'dashboard.html'))
        elif path == '/treemap':
            self.send_file(str(WEB_DIR / 'treemap.html'))

        # === 404 ===
        else:
            self.send_json({"error": "Endpoint não encontrado"}, 404)

    # ====== MÉTODO POST (TOKENIZAÇÃO) ======
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == '/token/vender':
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

    # ====== HELPERS ======
    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path):
        try:
            with open(path, 'rb') as f:
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(f.read())
        except FileNotFoundError:
            self.send_json({"error": "File not found"}, 404)

def run_server(host='0.0.0.0', port=8000):
    server = ThreadingHTTPServer((host, port), EnergyAPIHandler)
    print(f"🚀 Servidor rodando em http://{host}:{port}")
    print("📊 Endpoints disponíveis em /")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Servidor encerrado.")
        server.shutdown()

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    run_server(args.host, args.port)
