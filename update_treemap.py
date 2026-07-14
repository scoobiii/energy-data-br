#!/usr/bin/env python3
"""
Atualiza handle_treemap_brasil para combinar MMGD + SIGA por potência (MW).
"""
import re

# Ler o arquivo atual
with open('energy_data_br/server.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Nova implementação da função
new_function = '''    def handle_treemap_brasil(self, query):
        """Treemap Brasil > UF > Fonte (estilo Finviz), combinando MMGD + SIGA por potência (MW)."""
        nivel = query.get('nivel', ['uf_fonte'])[0]
        conn = get_db_connection()

        # --- 1. Agregação combinada (MMGD + SIGA) por UF e Fonte ---
        # Para cada UF e fonte, soma potência de MMGD e SIGA
        sql_union = """
            SELECT uf, fonte, SUM(potencia_mw) AS potencia_mw, SUM(empreendimentos) AS empreendimentos
            FROM (
                SELECT siguf AS uf, dscfontegeracao AS fonte, 
                       SUM(potencia_instalada_kw)/1000.0 AS potencia_mw, 
                       COUNT(*) AS empreendimentos
                FROM mmgd_fato
                WHERE siguf != '' AND dscfontegeracao != ''
                GROUP BY siguf, dscfontegeracao
                UNION ALL
                SELECT uf, tipo_geracao AS fonte,
                       SUM(potencia_outorgada_kw)/1000.0 AS potencia_mw,
                       COUNT(*) AS empreendimentos
                FROM siga_fato
                WHERE uf != '' AND tipo_geracao != ''
                GROUP BY uf, tipo_geracao
            ) combined
            GROUP BY uf, fonte
        """

        # --- 2. Montar resposta conforme nível ---
        if nivel == 'fonte':
            rows = conn.execute("""
                SELECT fonte, SUM(potencia_mw) AS potencia_mw, SUM(empreendimentos) AS empreendimentos
                FROM ({})
                GROUP BY fonte
                ORDER BY potencia_mw DESC
            """.format(sql_union)).fetchall()
            children = [
                {"name": r["fonte"], "value": r["potencia_mw"], "empreendimentos": r["empreendimentos"]}
                for r in rows
            ]
            self.send_json({"name": "Brasil", "children": children})
            conn.close()
            return

        if nivel == 'uf':
            rows = conn.execute("""
                SELECT uf, SUM(potencia_mw) AS potencia_mw, SUM(empreendimentos) AS empreendimentos
                FROM ({})
                GROUP BY uf
                ORDER BY potencia_mw DESC
            """.format(sql_union)).fetchall()
            children = [
                {"name": r["uf"], "value": r["potencia_mw"], "empreendimentos": r["empreendimentos"]}
                for r in rows
            ]
            self.send_json({"name": "Brasil", "children": children})
            conn.close()
            return

        # nivel == 'uf_fonte' (default)
        rows = conn.execute("""
            SELECT uf, fonte, potencia_mw, empreendimentos
            FROM ({})
            ORDER BY uf, potencia_mw DESC
        """.format(sql_union)).fetchall()
        conn.close()

        por_uf = {}
        for r in rows:
            por_uf.setdefault(r["uf"], []).append({
                "name": r["fonte"],
                "value": r["potencia_mw"],
                "empreendimentos": r["empreendimentos"]
            })

        children = [
            {"name": uf, "children": fontes}
            for uf, fontes in sorted(por_uf.items(), key=lambda kv: -sum(f["value"] for f in kv[1]))
        ]
        self.send_json({"name": "Brasil", "children": children})'''

# Substituir a função existente
pattern = r'def handle_treemap_brasil\(.*?\n(.*?\n)*?    def '
replacement = new_function + '\n\n    def '

if 'def handle_treemap_brasil' in content:
    # Substituir a função existente
    parts = content.split('def handle_treemap_brasil')
    before = parts[0]
    after = 'def handle_treemap_brasil'.join(parts[1:])  # Juntar o restante
    after = after.split('    def ', 1)
    remaining = after[1] if len(after) > 1 else ''
    
    new_content = before + new_function + '\n\n    def ' + remaining
else:
    # Adicionar a função se não existir
    insert_pos = content.find('    def handle_treemap_uf')
    if insert_pos != -1:
        new_content = content[:insert_pos] + new_function + '\n\n' + content[insert_pos:]
    else:
        print("⚠️ Não encontrei posição para inserir a função")
        exit(1)

# Escrever o arquivo atualizado
with open('energy_data_br/server.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("✅ Função handle_treemap_brasil atualizada com sucesso!")
print("   - Combina MMGD + SIGA por potência (MW)")
print("   - Retorna também empreendimentos para tooltips")
print("   - Três níveis: 'fonte', 'uf', 'uf_fonte'")
