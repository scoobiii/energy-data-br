"""
Módulo de tokenização de excedentes de MMGD.
Alinhado com Lei 14.300/2022, DREX e padrões Web3 (ERC-721, DID).
"""

import hashlib
import sqlite3
from datetime import datetime, timedelta
from typing import Optional

class TokenizacaoError(Exception):
    pass

def _conectar(db_path: str = "energy-data-br.sqlite") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

# ---------- Cadastro de cliente ----------
def cadastrar_cliente(cpf_cnpj: str, tipo: str, carteira: str = None, did: str = None, db_path: str = "energy-data-br.sqlite"):
    """Cadastra um novo cliente (PF/PJ) com hash anonimizado e identidade Web3 opcional."""
    cpf_cnpj_hash = hashlib.sha256(cpf_cnpj.encode()).hexdigest()
    conn = _conectar(db_path)
    try:
        conn.execute(
            "INSERT INTO cliente (cpf_cnpj_hash, tipo, carteira, did) VALUES (?, ?, ?, ?)",
            (cpf_cnpj_hash, tipo, carteira, did)
        )
        conn.commit()
        return conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    finally:
        conn.close()

# ---------- Cálculo de crédito excedente (simulado) ----------
def estimar_excedente(potencia_kw: float, fator_capacidade: float = 0.15, dias: int = 30) -> float:
    """
    Estima energia gerada no mês (kWh).
    fator_capacidade típico para solar no Brasil: 0.15 a 0.20.
    """
    return potencia_kw * 24 * dias * fator_capacidade

def gerar_credito_excedente(mmgd_fato_id: int, cliente_id: int, potencia_kw: float, 
                           valor_unitario_rs: float, token_contrato: str = None) -> int:
    """
    Cria um crédito excedente na tabela credito_excedente.
    Retorna o ID do crédito criado.
    """
    energia_kwh = estimar_excedente(potencia_kw)
    vencimento = (datetime.utcnow() + timedelta(days=1825)).isoformat()  # 60 meses ~ 1825 dias
    token_id = hashlib.sha256(f"{mmgd_fato_id}:{datetime.utcnow().isoformat()}".encode()).hexdigest()[:16]
    
    conn = _conectar()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO credito_excedente 
                (mmgd_fato_id, cliente_id, saldo_kwh, valor_unitario_rs, valor_unitario_token, 
                 data_vencimento, token_id, token_contrato)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (mmgd_fato_id, cliente_id, energia_kwh, valor_unitario_rs, valor_unitario_rs * 0.25, 
              vencimento, token_id, token_contrato))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

# ---------- Registro de transação ----------
def vender_credito(credito_id: int, quantidade_kwh: float, valor_rs: float, 
                  valor_token: float, tx_blockchain: str = None) -> int:
    """
    Registra uma venda de crédito (reduz saldo do crédito).
    Retorna ID da transação.
    """
    conn = _conectar()
    try:
        cur = conn.cursor()
        # Verifica saldo
        cur.execute("SELECT saldo_kwh FROM credito_excedente WHERE id = ?", (credito_id,))
        row = cur.fetchone()
        if not row:
            raise TokenizacaoError(f"Crédito {credito_id} não encontrado")
        saldo_atual = row[0]
        if saldo_atual < quantidade_kwh:
            raise TokenizacaoError(f"Saldo insuficiente: {saldo_atual} kWh disponíveis, {quantidade_kwh} solicitados")
        
        # Deduz saldo
        cur.execute("UPDATE credito_excedente SET saldo_kwh = saldo_kwh - ? WHERE id = ?", 
                   (quantidade_kwh, credito_id))
        
        # Registra transação
        cur.execute("""
            INSERT INTO transacao_token (credito_id, tipo, quantidade_kwh, valor_rs, valor_token, tx_blockchain)
            VALUES (?, 'venda', ?, ?, ?, ?)
        """, (credito_id, quantidade_kwh, valor_rs, valor_token, tx_blockchain))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()

# ---------- Consultas ----------
def saldo_disponivel(cliente_id: int) -> list[dict]:
    """Lista todos os créditos disponíveis de um cliente."""
    conn = _conectar()
    try:
        rows = conn.execute("""
            SELECT id, mmgd_fato_id, uc_beneficiaria, saldo_kwh, valor_unitario_rs,
                   data_vencimento, token_id
            FROM credito_excedente
            WHERE cliente_id = ? AND saldo_kwh > 0 AND data_vencimento > datetime('now')
            ORDER BY data_vencimento ASC
        """, (cliente_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()

def extrato_transacoes(cliente_id: int) -> list[dict]:
    """Histórico de transações do cliente."""
    conn = _conectar()
    try:
        rows = conn.execute("""
            SELECT t.id, t.tipo, t.quantidade_kwh, t.valor_rs, t.valor_token,
                   t.tx_blockchain, t.data_transacao
            FROM transacao_token t
            JOIN credito_excedente c ON t.credito_id = c.id
            WHERE c.cliente_id = ?
            ORDER BY t.data_transacao DESC
        """, (cliente_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
