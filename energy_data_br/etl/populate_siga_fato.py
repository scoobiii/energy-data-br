"""
ETL siga_fato – atualiza a tabela com os dados mais recentes do SIGA.
Usa as funções reais do siga_client (fetch_all e normalize).
"""
import logging
import sqlite3
from energy_data_br.aneel.siga_client import fetch_all, normalize

log = logging.getLogger("populate_siga_fato")

def populate_siga_fato(conn: sqlite3.Connection) -> dict:
    conn.execute("PRAGMA journal_mode=WAL")
    cur = conn.cursor()
    inserted = 0
    for rec in fetch_all():
        norm = normalize(rec)
        # Mapeamento correto para o schema de siga_fato
        cur.execute("""
            INSERT OR REPLACE INTO siga_fato (
                cod_ceg, nome_empreendimento, uf, tipo_geracao,
                fase_usina, fonte_combustivel, potencia_outorgada_kw,
                potencia_fiscalizada_kw, garantia_fisica_kw, lat, lon,
                data_entrada_operacao, proprietario, municipios, hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            norm.get('cod_ceg'),
            norm.get('nome_empreendimento'),
            norm.get('uf'),
            norm.get('tipo_geracao'),
            norm.get('fase_usina'),
            norm.get('fonte_combustivel'),
            norm.get('potencia_outorgada_kw'),
            norm.get('potencia_fiscalizada_kw'),
            norm.get('garantia_fisica_kw'),
            norm.get('lat'),
            norm.get('lon'),
            norm.get('data_entrada_operacao'),
            norm.get('proprietario'),
            norm.get('municipios'),
            norm.get('hash')
        ))
        inserted += 1
    conn.commit()
    log.info(f"populate_siga_fato: {inserted:,} registros inseridos/atualizados")
    return {"inserted": inserted}
