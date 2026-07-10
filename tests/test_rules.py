"""
test_rules.py — testa as funções puras de classificação (rules.py).

Os valores de entrada abaixo são casos de teste (limites de faixa, formatos
de string plausíveis) — não são dados da ANEEL, e nenhum resultado aqui é
usado como saída do produto. Servem só para travar o comportamento das
regras descritas em docs/regras_negocio.md.
"""

from aneel_mmgd import rules


# ---------------------------------------------------------------------------
# parse_potencia
# ---------------------------------------------------------------------------
def test_parse_potencia_formato_ptbr():
    assert rules.parse_potencia("1.200,50") == 1200.50


def test_parse_potencia_formato_us():
    assert rules.parse_potencia("1200.50") == 1200.50


def test_parse_potencia_inteiro():
    assert rules.parse_potencia("85") == 85.0


def test_parse_potencia_none_e_vazio():
    assert rules.parse_potencia(None) is None
    assert rules.parse_potencia("") is None


def test_parse_potencia_numero_nativo():
    assert rules.parse_potencia(42.5) == 42.5


# ---------------------------------------------------------------------------
# norm_fonte
# ---------------------------------------------------------------------------
def test_norm_fonte_fotovoltaica():
    assert rules.norm_fonte("Central Geradora Fotovoltaica") == "UFV"
    assert rules.norm_fonte("Solar") == "UFV"


def test_norm_fonte_eolica():
    assert rules.norm_fonte("Central Geradora Eólica") == "EOL"


def test_norm_fonte_hidrica():
    assert rules.norm_fonte("Central Geradora Hidrelétrica") == "CGH"
    assert rules.norm_fonte("Pequena Central Hidrelétrica") == "CGH"


def test_norm_fonte_termica():
    assert rules.norm_fonte("Termica a Biogás") == "UTE"
    assert rules.norm_fonte("UTE - Gás Natural") == "UTE"


def test_norm_fonte_desconhecida_cai_em_outra():
    assert rules.norm_fonte("Geotérmica") == "OUTRA"
    assert rules.norm_fonte(None) == "OUTRA"
    assert rules.norm_fonte("") == "OUTRA"


# ---------------------------------------------------------------------------
# norm_modalidade
# ---------------------------------------------------------------------------
def test_norm_modalidade_propria():
    assert rules.norm_modalidade("Geração na própria UC") == "GERACAO_PROPRIA"


def test_norm_modalidade_remota():
    assert rules.norm_modalidade("Autoconsumo remoto") == "AUTOCONSUMO_REMOTO"


def test_norm_modalidade_compartilhada():
    assert rules.norm_modalidade("Geração compartilhada - cooperativa") == "GERACAO_COMPARTILHADA"


def test_norm_modalidade_muc_e_emuc():
    assert rules.norm_modalidade("Múltiplas Unidades Consumidoras") == "MUC"
    assert rules.norm_modalidade("Empreendimento com Múltiplas Unidades Consumidoras") == "EMUC"


def test_norm_modalidade_indefinida():
    assert rules.norm_modalidade(None) == "INDEFINIDA"
    assert rules.norm_modalidade("texto qualquer sem match") == "INDEFINIDA"


# ---------------------------------------------------------------------------
# faixa_regulatoria — limites da Lei 14.300/2022
# ---------------------------------------------------------------------------
def test_faixa_regulatoria_micro_no_limite():
    assert rules.faixa_regulatoria(75.0, "UFV") == "MICROGERACAO"


def test_faixa_regulatoria_mini_logo_acima_do_limite():
    assert rules.faixa_regulatoria(75.01, "UFV") == "MINIGERACAO"


def test_faixa_regulatoria_mini_teto_5mw_nao_hidrica():
    assert rules.faixa_regulatoria(5000.0, "UFV") == "MINIGERACAO"
    assert rules.faixa_regulatoria(5000.01, "UFV") == "INDEFINIDA"


def test_faixa_regulatoria_mini_teto_3mw_hidrica():
    assert rules.faixa_regulatoria(3000.0, "CGH") == "MINIGERACAO"
    assert rules.faixa_regulatoria(3000.01, "CGH") == "INDEFINIDA"


def test_faixa_regulatoria_nula_ou_zero():
    assert rules.faixa_regulatoria(None, "UFV") == "INDEFINIDA"
    assert rules.faixa_regulatoria(0, "UFV") == "INDEFINIDA"


# ---------------------------------------------------------------------------
# faixa_potencia_mex — régua estratégica MEx Energia
# ---------------------------------------------------------------------------
def test_faixa_potencia_mex_buckets():
    assert rules.faixa_potencia_mex(10) == "RESIDENCIAL"
    assert rules.faixa_potencia_mex(50) == "COMERCIAL_PEQUENO"
    assert rules.faixa_potencia_mex(500) == "MINIGERACAO_ALVO"
    assert rules.faixa_potencia_mex(3000) == "INDUSTRIAL_ALVO"
    assert rules.faixa_potencia_mex(6000) == "GRANDE_CARGA"
    assert rules.faixa_potencia_mex(None) == "INDEFINIDA"


# ---------------------------------------------------------------------------
# is_outlier
# ---------------------------------------------------------------------------
def test_is_outlier_zero_ou_nulo():
    assert rules.is_outlier(0, "INDEFINIDA") == 1
    assert rules.is_outlier(None, "INDEFINIDA") == 1


def test_is_outlier_implausivel():
    assert rules.is_outlier(60000, "INDEFINIDA") == 1


def test_is_outlier_valor_normal():
    assert rules.is_outlier(1200, "MINIGERACAO") == 0


# ---------------------------------------------------------------------------
# resolve_columns — introspecção de schema
# ---------------------------------------------------------------------------
def test_resolve_columns_mapeia_nomes_conhecidos():
    fields = [{"id": n, "type": "text"} for n in [
        "SigUF", "NomMunicipio", "CodIBGE", "NomAgenteDistribuidor",
        "NomFonteGeracao", "MdaPotenciaInstaladaKW", "DatConexao",
        "NomModalidadeEmpreendimento", "DscClasseConsumo",
    ]]
    cols = rules.resolve_columns(fields)
    assert cols["uf"] == "SigUF"
    assert cols["potencia_kw"] == "MdaPotenciaInstaladaKW"
    assert cols["fonte"] == "NomFonteGeracao"
    assert cols["modalidade"] == "NomModalidadeEmpreendimento"


def test_resolve_columns_campo_ausente_fica_none():
    fields = [{"id": "SigUF", "type": "text"}]
    cols = rules.resolve_columns(fields)
    assert cols["uf"] == "SigUF"
    assert cols["potencia_kw"] is None


# ---------------------------------------------------------------------------
# classify_record — pipeline completo de classificação de um registro
# ---------------------------------------------------------------------------
def test_classify_record_completo():
    fields = [{"id": n, "type": "text"} for n in [
        "SigUF", "NomFonteGeracao", "MdaPotenciaInstaladaKW", "NomModalidadeEmpreendimento",
    ]]
    cols = rules.resolve_columns(fields)
    record = {
        "SigUF": "SP",
        "NomFonteGeracao": "Fotovoltaica",
        "MdaPotenciaInstaladaKW": "1200,50",
        "NomModalidadeEmpreendimento": "Geração na própria UC",
    }
    c = rules.classify_record(cols, record)
    assert c["uf"] == "SP"
    assert c["fonte_norm"] == "UFV"
    assert c["potencia_kw"] == 1200.50
    assert c["modalidade_norm"] == "GERACAO_PROPRIA"
    assert c["faixa_regulatoria"] == "MINIGERACAO"
    assert c["faixa_potencia_mex"] == "INDUSTRIAL_ALVO"
    assert c["is_outlier"] == 0
