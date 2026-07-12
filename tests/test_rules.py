"""Testes das regras de negócio (puros, sem I/O)."""
import pytest
from energy_data_br import rules

def test_parse_potencia():
    assert rules.parse_potencia("32,50") == 32.5
    assert rules.parse_potencia("2.00") == 2.0
    assert rules.parse_potencia("") is None
    assert rules.parse_potencia(None) is None

def test_norm_fonte():
    assert rules.norm_fonte("Radiação solar") == "solar"
    assert rules.norm_fonte("Eólica") == "eolica"
    assert rules.norm_fonte(None) == ""

def test_norm_modalidade():
    assert rules.norm_modalidade("Geracao na propria UC") == "propria_uc"
    assert rules.norm_modalidade("Condominio") == "condominio"
    assert rules.norm_modalidade(None) == "nao_informada"

def test_faixa_regulatoria():
    # Microgeração: <= 75kW
    assert rules.faixa_regulatoria(5.0, "solar") == "microgeracao"
    assert rules.faixa_regulatoria(75.0, "solar") == "microgeracao"
    # Minigeração: > 75kW e <= 5MW
    assert rules.faixa_regulatoria(100.0, "solar") == "minigeracao"
    assert rules.faixa_regulatoria(5000.0, "solar") == "minigeracao"  # limite da função
    # Geração: > 5MW
    assert rules.faixa_regulatoria(10000.0, "solar") == "geracao"

def test_faixa_potencia_mex():
    # Faixa estratégica MEx
    assert rules.faixa_potencia_mex(5.0) == "pequeno"
    assert rules.faixa_potencia_mex(100.0) == "medio"
    assert rules.faixa_potencia_mex(1000.0) == "grande"
    assert rules.faixa_potencia_mex(None) == ""

def test_is_outlier():
    assert rules.is_outlier(10.0, "microgeracao") == 0
    assert rules.is_outlier(10000.0, "microgeracao") == 1  # muito alto para micro
    assert rules.is_outlier(None, "microgeracao") == 0

def test_resolve_columns():
    fields = [
        {'id': 'CodEmpreendimento', 'type': 'text'},
        {'id': 'MdaPotenciaInstaladaKW', 'type': 'text'},
        {'id': 'SigUF', 'type': 'text'},
        {'id': 'DscFonteGeracao', 'type': 'text'},
    ]
    mapping = rules.resolve_columns(fields)
    assert mapping['CodEmpreendimento'] == 'cod_empreendimento'
    assert mapping['MdaPotenciaInstaladaKW'] == 'potencia_instalada_kw'
    assert mapping['SigUF'] == 'uf'
    assert mapping['DscFonteGeracao'] == 'fonte'

def test_classify_record():
    fields = [
        {'id': 'CodEmpreendimento'},
        {'id': 'MdaPotenciaInstaladaKW'},
        {'id': 'SigUF'},
        {'id': 'DscFonteGeracao'},
    ]
    record = {
        'CodEmpreendimento': 'GD.TEST.001',
        'MdaPotenciaInstaladaKW': '32,50',
        'SigUF': 'SP',
        'DscFonteGeracao': 'Radiação solar',
    }
    cols = rules.resolve_columns(fields)
    classified = rules.classify_record(cols, record)
    assert classified['cod_empreendimento'] == 'GD.TEST.001'
    assert classified['potencia_instalada_kw'] == 32.5
    assert classified['uf'] == 'SP'
    assert classified['fonte'] == 'solar'
    assert 'faixa_regulatoria' in classified
    assert 'modalidade' in classified
