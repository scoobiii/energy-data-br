#!/usr/bin/env python3
"""Simula medições IoT para testar o sistema de tokenização."""
import time
import random
import requests

API = "http://localhost:8080"

def simular_medicao(cliente_id=1, duracao_horas=1, intervalo_segundos=10):
    """Envia medições simuladas por um período."""
    inicio = time.time()
    fim = inicio + duracao_horas * 3600
    while time.time() < fim:
        geracao = round(random.uniform(3.0, 8.0), 2)  # 3-8 kW
        consumo = round(random.uniform(1.0, 4.0), 2)   # 1-4 kW
        payload = {
            "cliente_id": cliente_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "geracao_kw": geracao,
            "consumo_kw": consumo,
            "dispositivo": "simulador"
        }
        try:
            resp = requests.post(f"{API}/iot/medicao", json=payload, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                print(f"✓ Medição {data['medicao_id']}: ger={geracao}kW cons={consumo}kW | saldo atualizado")
            else:
                print(f"✗ Erro {resp.status_code}: {resp.text}")
        except requests.RequestException as e:
            print(f"✗ Falha: {e}")
        time.sleep(intervalo_segundos)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--cliente", type=int, default=1)
    parser.add_argument("--horas", type=float, default=1)
    parser.add_argument("--intervalo", type=int, default=10)
    args = parser.parse_args()
    print(f"Simulando IoT para cliente {args.cliente} por {args.horas}h...")
    simular_medicao(args.cliente, args.horas, args.intervalo)
