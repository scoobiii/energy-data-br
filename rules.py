"""
rules.py — regras de negócio puras (sem I/O), aplicadas linha a linha aos
registros da base MMGD da ANEEL.

Fundamentação regulatória: Lei nº 14.300/2022, REN ANEEL nº 1.000/2021 e
nº 1.059/2023. Detalhes e racional de cada regra: ../../docs/regras_negocio.md

Todas as funções aqui são puras (mesma entrada -> mesma saída, sem rede,
sem banco) para permitir teste unitário direto e reutilização em outros
pipelines (ex: um agente RAG que precise reclassificar dados on-the-fly).
"""

from __future__ import annotations

COLUMN_HINTS: dict[str, list[str]] = {
    "uf": ["sigufconsumidora", "siguf", "uf"],
    "municipio": ["nommunicipio", "municipio"],
    "cod_ibge": ["codibge", "ibge"],
    "distribuidora": ["nomagentedistribuidor", "distribuidora", "agentedistribuidor"],
    "fonte": ["nomfontegeracao", "fontegeracao", "dscfonte", "fonte"],
    "potencia_kw": ["mdapotenciainstaladakw", "potenciainstalada", "potenciakw", "mdapotencia"],
    "data_conexao": ["datconexao", "dataconexao", "datgeracaoconjuntodados"],
    "modalidade": ["nommodalidadeempreendimento", "modalidade"],
    "classe_consumo": ["dscclasseconsumo", "classeconsumo"],
}


def resolve_columns(fields: list[dict]) -> dict[str, str | None]:
    """Mapeia nomes canônicos -> nome real da coluna no datastore, por
    correspondência de substring (case-insensitive). Não assume nomes
    exatos porque a ANEEL já alterou nomenclatura entre revisões do dataset.
    """
    field_ids = [f["id"] for f in fields]
    lower_map = {f.lower(): f for f in field_ids}
    resolved: dict[str, str | None] = {}
    for canonical, hints in COLUMN_HINTS.items():
        match = None
        for hint in hints:
            for lower_name, orig_name in lower_map.items():
                if hint in lower_name:
                    match = orig_name
                    break
            if match:
                break
        resolved[canonical] = match
    return resolved


def parse_potencia(raw) -> float | None:
    """Converte string numérica pt-BR ('1.200,50') ou en-US ('1200.50') para float."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    s = str(raw).strip()
    if not s:
        return None
    # heurística: se tem vírgula, assume formato pt-BR (ponto=milhar, vírgula=decimal)
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def norm_fonte(raw: str | None) -> str:
    """Normaliza texto livre de fonte de geração para um código curto."""
    if not raw:
        return "OUTRA"
    s = raw.lower()
    if any(k in s for k in ["fotovolta", "solar", "ufv"]):
        return "UFV"
    if any(k in s for k in ["eólic", "eolic", "eol"]):
        return "EOL"
    if any(k in s for k in ["hidr", "cgh", "pch"]):
        return "CGH"
    if any(k in s for k in ["term", "biogás", "biogas", "biomassa", "gás natural", "gas natural", "ute"]):
        return "UTE"
    return "OUTRA"


def norm_modalidade(raw: str | None) -> str:
    """Normaliza a modalidade do empreendimento conforme REN 1.000/2021, art. 2º."""
    if not raw:
        return "INDEFINIDA"
    s = raw.lower()
    if "remot" in s:
        return "AUTOCONSUMO_REMOTO"
    if "compartilhad" in s or "cooperativ" in s or "consórcio" in s or "consorcio" in s:
        return "GERACAO_COMPARTILHADA"
    if "múltiplas" in s or "multiplas" in s or "muc" in s:
        return "EMUC" if "empreend" in s else "MUC"
    if "própria" in s or "propria" in s or "local" in s:
        return "GERACAO_PROPRIA"
    return "INDEFINIDA"


def faixa_regulatoria(potencia_kw: float | None, fonte_norm: str) -> str:
    """Classifica MICROGERACAO / MINIGERACAO conforme Lei 14.300/2022.

    Teto de minigeração: 3 MW para fonte hídrica, 5 MW para as demais.
    """
    if potencia_kw is None or potencia_kw <= 0:
        return "INDEFINIDA"
    if potencia_kw <= 75:
        return "MICROGERACAO"
    teto = 3000 if fonte_norm == "CGH" else 5000
    if potencia_kw <= teto:
        return "MINIGERACAO"
    return "INDEFINIDA"


def faixa_potencia_mex(potencia_kw: float | None) -> str:
    """Régua estratégica MEx Energia (não regulatória) para priorização de
    prospecção comercial do barramento 800VDC + BESS. Ver docs/regras_negocio.md.
    """
    if potencia_kw is None or potencia_kw <= 0:
        return "INDEFINIDA"
    if potencia_kw <= 15:
        return "RESIDENCIAL"
    if potencia_kw <= 75:
        return "COMERCIAL_PEQUENO"
    if potencia_kw <= 1000:
        return "MINIGERACAO_ALVO"
    if potencia_kw <= 5000:
        return "INDUSTRIAL_ALVO"
    return "GRANDE_CARGA"


def is_outlier(potencia_kw: float | None, faixa_reg: str) -> int:
    """Sinaliza registros que não devem entrar nas views agregadas (mas
    permanecem auditáveis em mmgd_fato)."""
    if potencia_kw is None or potencia_kw <= 0:
        return 1
    if potencia_kw > 50_000:
        return 1
    if faixa_reg == "INDEFINIDA":
        return 1
    return 0


def classify_record(cols: dict, record: dict) -> dict:
    """Aplica todas as regras a um único registro bruto do datastore e
    retorna um dict pronto para persistência em mmgd_fato."""
    uf = record.get(cols.get("uf")) if cols.get("uf") else None
    municipio = record.get(cols.get("municipio")) if cols.get("municipio") else None
    cod_ibge = record.get(cols.get("cod_ibge")) if cols.get("cod_ibge") else None
    distribuidora = record.get(cols.get("distribuidora")) if cols.get("distribuidora") else None
    fonte_bruta = record.get(cols.get("fonte")) if cols.get("fonte") else None
    potencia_raw = record.get(cols.get("potencia_kw")) if cols.get("potencia_kw") else None
    data_conexao = record.get(cols.get("data_conexao")) if cols.get("data_conexao") else None
    modalidade_bruta = record.get(cols.get("modalidade")) if cols.get("modalidade") else None
    classe_consumo = record.get(cols.get("classe_consumo")) if cols.get("classe_consumo") else None

    potencia_kw = parse_potencia(potencia_raw)
    fonte_n = norm_fonte(fonte_bruta)
    modal_n = norm_modalidade(modalidade_bruta)
    faixa_reg = faixa_regulatoria(potencia_kw, fonte_n)
    faixa_mex = faixa_potencia_mex(potencia_kw)
    outlier = is_outlier(potencia_kw, faixa_reg)

    return {
        "uf": uf,
        "municipio": municipio,
        "cod_ibge": cod_ibge,
        "distribuidora": distribuidora,
        "fonte_bruta": fonte_bruta,
        "fonte_norm": fonte_n,
        "potencia_kw": potencia_kw,
        "data_conexao": data_conexao,
        "modalidade_bruta": modalidade_bruta,
        "modalidade_norm": modal_n,
        "classe_consumo": classe_consumo,
        "faixa_regulatoria": faixa_reg,
        "faixa_potencia_mex": faixa_mex,
        "is_outlier": outlier,
    }
