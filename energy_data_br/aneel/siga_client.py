"""Cliente SIGA – usinas centralizadas (datastore_search paginado)."""
import urllib.request, json, time, hashlib
from typing import Iterator, Dict

CKAN_BASE = "https://dadosabertos.aneel.gov.br/api/3/action"
RESOURCE_ID = "11ec447d-698d-4ab8-977f-b424d5deee6a"  # CSV mensal (datastore_active=true)

def fetch_all() -> Iterator[Dict]:
    """Itera sobre todos os registros do SIGA via datastore_search."""
    offset = 0
    limit = 100
    total = None
    while total is None or offset < total:
        url = f"{CKAN_BASE}/datastore_search?resource_id={RESOURCE_ID}&limit={limit}&offset={offset}"
        with urllib.request.urlopen(url) as resp:
            data = json.loads(resp.read().decode('utf-8'))['result']
        if total is None:
            total = data['total']
        for rec in data['records']:
            yield rec
        offset += limit
        time.sleep(0.05)  # evitar sobrecarga

def normalize(rec: Dict) -> Dict:
    """Converte campos para tipos padrão e gera hash determinístico."""
    def parse_float(val: str) -> float:
        if not val:
            return 0.0
        return float(val.replace(',', '.'))
    cod_ceg = rec.get('CodCEG', '')
    return {
        'cod_ceg': cod_ceg,
        'nome_empreendimento': rec.get('NomEmpreendimento', ''),
        'uf': rec.get('SigUFPrincipal', ''),
        'tipo_geracao': rec.get('SigTipoGeracao', ''),
        'fase_usina': rec.get('DscFaseUsina', ''),
        'fonte_combustivel': rec.get('DscFonteCombustivel', ''),
        'potencia_outorgada_kw': parse_float(rec.get('MdaPotenciaOutorgadaKw', '0')),
        'potencia_fiscalizada_kw': parse_float(rec.get('MdaPotenciaFiscalizadaKw', '0')),
        'garantia_fisica_kw': parse_float(rec.get('MdaGarantiaFisicaKw', '0')),
        'lat': parse_float(rec.get('NumCoordNEmpreendimento', '0')),
        'lon': parse_float(rec.get('NumCoordEEmpreendimento', '0')),
        'data_entrada_operacao': rec.get('DatEntradaOperacao', ''),
        'proprietario': rec.get('DscPropriRegimePariticipacao', ''),
        'municipios': rec.get('DscMuninicpios', ''),
        'hash': cod_ceg if cod_ceg else hashlib.sha256(json.dumps(rec, sort_keys=True).encode()).hexdigest()
    }
