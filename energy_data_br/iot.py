"""
Módulo de ingestão IoT – recebe medições de dispositivos e atualiza saldo de créditos.
Suporta formato genérico e adaptadores para APIs de fabricantes.
"""
import json
import hashlib
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any

class IoTError(Exception):
    pass

def _conectar(db_path: str = "energy-data-br.sqlite") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA busy_timeout=30000")
    conn.row_factory = sqlite3.Row
    return conn

def processar_medicao(
    cliente_id: int,
    timestamp: str,
    geracao_kw: float,
    consumo_kw: float = 0.0,
    bateria_soc: Optional[float] = None,
    bateria_potencia_kw: Optional[float] = None,
    dispositivo: str = "inversor",
    extra_json: Optional[Dict[str, Any]] = None,
    db_path: str = "energy-data-br.sqlite"
) -> int:
    """
    Processa uma medição IoT e atualiza o saldo de crédito excedente do cliente.
    Retorna o ID da medição inserida.
    """
    # Calcula excedente (geração - consumo). Se bateria está fornecendo, considera como geração.
    excedente = geracao_kw - consumo_kw
    if bateria_potencia_kw is not None and bateria_potencia_kw < 0:
        excedente += abs(bateria_potencia_kw)  # bateria descarregando = geração adicional
    excedente = max(0.0, excedente)  # não negativo

    # Gera hash único para evitar duplicatas
    hash_str = hashlib.sha256(
        f"{cliente_id}:{timestamp}:{geracao_kw}:{consumo_kw}:{dispositivo}".encode()
    ).hexdigest()

    conn = _conectar(db_path)
    try:
        # Insere medição
        conn.execute("""
            INSERT OR IGNORE INTO medicao_iot
                (cliente_id, dispositivo, timestamp, geracao_kw, consumo_kw,
                 bateria_soc, bateria_potencia_kw, extra_json, hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            cliente_id, dispositivo, timestamp, geracao_kw, consumo_kw,
            bateria_soc, bateria_potencia_kw,
            json.dumps(extra_json) if extra_json else None,
            hash_str
        ))
        conn.commit()

        # Se houve excedente, atualiza o crédito do cliente
        if excedente > 0:
            # Procura crédito ativo mais recente
            credito = conn.execute("""
                SELECT id, saldo_kwh FROM credito_excedente
                WHERE cliente_id = ? AND data_vencimento > datetime('now')
                ORDER BY data_vencimento ASC LIMIT 1
            """, (cliente_id,)).fetchone()

            if credito:
                # Atualiza saldo
                novo_saldo = credito['saldo_kwh'] + excedente
                conn.execute(
                    "UPDATE credito_excedente SET saldo_kwh = ?, ultima_atualizacao = datetime('now') WHERE id = ?",
                    (novo_saldo, credito['id'])
                )
                conn.commit()
            else:
                # Cria novo crédito (se houver medição mas não crédito)
                # Isso pode acontecer na primeira medição após cadastro
                vencimento = datetime.utcnow().isoformat()
                conn.execute("""
                    INSERT INTO credito_excedente
                        (mmgd_fato_id, cliente_id, saldo_kwh, valor_unitario_rs, valor_unitario_token,
                         data_vencimento, token_id)
                    VALUES (?, ?, ?, ?, ?, datetime('now', '+1825 days'), ?)
                """, (
                    None,  # mmgd_fato_id pode ser NULL se associado apenas ao cliente
                    cliente_id, excedente, 0.80, 0.20,  # valores padrão
                    hashlib.sha256(f"{cliente_id}:{datetime.utcnow().isoformat()}".encode()).hexdigest()[:16]
                ))
                conn.commit()

        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()

# ========== ADAPTADORES GENÉRICOS PARA FABRICANTES ==========
# Exemplo de adaptador para formato genérico JSON (já usado no endpoint)
def adaptar_payload_generico(payload: dict) -> dict:
    """Converte um payload genérico para o formato esperado por processar_medicao."""
    return {
        "cliente_id": payload.get("cliente_id"),
        "timestamp": payload.get("timestamp") or payload.get("data_hora"),
        "geracao_kw": float(payload.get("geracao_kw") or payload.get("power_kw") or 0),
        "consumo_kw": float(payload.get("consumo_kw") or payload.get("load_kw") or 0),
        "bateria_soc": float(payload["bateria_soc"]) if "bateria_soc" in payload else None,
        "bateria_potencia_kw": float(payload["bateria_potencia_kw"]) if "bateria_potencia_kw" in payload else None,
        "dispositivo": payload.get("dispositivo", "inversor"),
        "extra_json": payload.get("extra")
    }

# Exemplo de adaptador para API GoodWe (placeholder)
def adaptar_goodwe(payload: dict) -> dict:
    """Exemplo de adaptador para API da GoodWe."""
    return {
        "cliente_id": payload.get("station_id"),  # mapear para cliente_id
        "timestamp": payload.get("time"),
        "geracao_kw": float(payload.get("power", 0)),
        "consumo_kw": float(payload.get("load_power", 0)),
        "dispositivo": "goodwe",
        "extra_json": payload
    }
