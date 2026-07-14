#!/usr/bin/env python3
"""Orquestrador único de sync – com flock e logs de execução."""
import fcntl
import json
import logging
import sqlite3
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime, UTC
from pathlib import Path

# --- Conexão temporária com o banco (mesmo padrão do server.py) ---
DB_PATH = "/storage/emulated/0/energy-data-br.sqlite"

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=30000")
    return conn
# --- Fim da conexão temporária ---

# Importar as funções de ETL (presumindo que existam)
from energy_data_br.aneel.api_client import get_all_records
from energy_data_br.aneel.siga_client import fetch_all as siga_fetch_all
from energy_data_br.ons.api_carga import fetch_recent_window
from energy_data_br.ons.dessem_client import sync_all as dessem_sync_all
from energy_data_br.etl.populate_mmgd_fato import populate_mmgd_fato
from energy_data_br.etl.populate_siga_fato import populate_siga_fato

LOCK_PATH = Path.home() / "energy-data-br" / ".locks" / "sync.lock"
LOG = logging.getLogger("sync_orchestrator")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

@contextmanager
def single_lock():
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    fh = open(LOCK_PATH, "w")
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        LOG.error("Outra sincronização já está em andamento. Abortando.")
        sys.exit(1)
    try:
        yield
    finally:
        fcntl.flock(fh, fcntl.LOCK_UN)
        fh.close()

def main():
    conn = get_connection()
    with single_lock():
        LOG.info("Iniciando sync orquestrado...")
        # MMGD raw
        LOG.info("Baixando MMGD snapshot...")
        list(get_all_records())  # consome iterator
        LOG.info("MMGD raw concluído.")

        # MMGD fato
        LOG.info("Populando mmgd_fato...")
        populate_mmgd_fato(conn)
        LOG.info("mmgd_fato concluído.")

        # SIGA
        LOG.info("Atualizando SIGA...")
        populate_siga_fato(conn)
        LOG.info("SIGA concluído.")

        # ONS carga (último dia)
        LOG.info("Atualizando ONS carga...")
        for _ in fetch_recent_window(days=1):
            pass
        LOG.info("ONS carga concluído.")

        # DESSEM
        LOG.info("Atualizando DESSEM...")
        dessem_sync_all(delay_sec=0.5)
        LOG.info("DESSEM concluído.")

        LOG.info("Sync orquestrado finalizado com sucesso.")
        return 0

if __name__ == "__main__":
    sys.exit(main())
