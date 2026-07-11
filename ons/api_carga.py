"""Cliente ONS - 3 camadas confirmadas no Sprint 0."""
import urllib.request
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Iterator
from pathlib import Path

# Códigos de área válidos (confirmados via teste real)
CODIGOS_AREA_VALIDOS = ["S", "N", "NE", "SIN"]

# URLs reais
APICARGA_BASE = "https://apicarga.ons.org.br/prd"
S3_BASE = "https://ons-aws-prod-opendata.s3.amazonaws.com/dataset"

def fetch_carga_verificada(
    dat_inicio: str,
    dat_fim: str,
    cod_areacarga: str = "S"
) -> List[Dict[str, Any]]:
    """
    Busca carga verificada via apicarga.ons.org.br.
    Exemplo: dat_inicio=2026-07-10, dat_fim=2026-07-11
    """
    if cod_areacarga not in CODIGOS_AREA_VALIDOS:
        raise ValueError(f"cod_areacarga inválido. Use: {CODIGOS_AREA_VALIDOS}")
    
    url = f"{APICARGA_BASE}/cargaverificada?dat_inicio={dat_inicio}&dat_fim={dat_fim}&cod_areacarga={cod_areacarga}"
    
    req = urllib.request.Request(url, headers={
        'User-Agent': 'MEx-Energia-ETL/1.0',
        'Accept': 'application/json'
    })
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[ERROR] apicarga falhou: {e}")
        return []

def fetch_carga_programada(
    dat_inicio: str,
    dat_fim: str,
    cod_areacarga: str = "S"
) -> List[Dict[str, Any]]:
    """Busca carga programada via apicarga.ons.org.br."""
    if cod_areacarga not in CODIGOS_AREA_VALIDOS:
        raise ValueError(f"cod_areacarga inválido. Use: {CODIGOS_AREA_VALIDOS}")
    
    url = f"{APICARGA_BASE}/cargaprogramada?dat_inicio={dat_inicio}&dat_fim={dat_fim}&cod_areacarga={cod_areacarga}"
    
    req = urllib.request.Request(url, headers={
        'User-Agent': 'MEx-Energia-ETL/1.0',
        'Accept': 'application/json'
    })
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data if isinstance(data, list) else []
    except Exception as e:
        print(f"[ERROR] apicarga falhou: {e}")
        return []

def fetch_recent_window(days: int = 1) -> Iterator[Dict[str, Any]]:
    """Busca janela recente (últimos N dias) para todas as áreas."""
    today = datetime.now()
    dat_fim = today.strftime('%Y-%m-%d')
    dat_inicio = (today - timedelta(days=days)).strftime('%Y-%m-%d')
    
    for area in CODIGOS_AREA_VALIDOS:
        print(f"📊 Buscando área {area}...")
        records = fetch_carga_verificada(dat_inicio, dat_fim, area)
        for rec in records:
            rec['_fonte'] = 'verificada'
            rec['_area'] = area
            yield rec

def download_s3_bulk(dataset: str, dest: Path) -> bool:
    """Baixa CSV do S3 ONS (bulk histórico)."""
    url = f"{S3_BASE}/{dataset}"
    req = urllib.request.Request(url, headers={'User-Agent': 'MEx-Energia-ETL/1.0'})
    
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            with open(dest, 'wb') as f:
                while chunk := response.read(1024 * 1024):
                    f.write(chunk)
        return True
    except Exception as e:
        print(f"[ERROR] S3 download falhou: {e}")
        return False
