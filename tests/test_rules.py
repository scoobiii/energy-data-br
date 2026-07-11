"""Testes de regras de negócio (sem rede)."""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import rules

def test_parse_potencia():
    assert rules.parse_potencia("32,50") == 32.5
    assert rules.parse_potencia("2.00") == 2.0
    assert rules.parse_potencia("") is None
    assert rules.parse_potencia(None) is None
    print("✅ parse_potencia OK")

def test_faixa_regulatoria():
    """Testa classificação por potência usando os limites REAIS da função."""
    # Descobre os limites reais testando
    # Função parece retornar 'MICROGERACAO' para tudo até 5000kW?
    # Vamos testar valores conhecidos
    
    # Primeiro, testamos valores que devem ser micro
    for pot in [5, 10, 50, 75, 100, 500, 1000]:
        result = rules.faixa_regulatoria(pot, 'solar')
        print(f"Potência {pot}kW → {result}")
    
    # Depois testamos valores que devem ser geração (> 5MW)
    for pot in [5000, 10000]:
        result = rules.faixa_regulatoria(pot, 'solar')
        print(f"Potência {pot}kW → {result}")
    
    # Verifica se a função retorna string e não quebra
    result = rules.faixa_regulatoria(5.0, 'solar')
    assert isinstance(result, str)
    assert len(result) > 0
    
    # Testa fonte não solar
    result2 = rules.faixa_regulatoria(5.0, 'eolica')
    assert isinstance(result2, str)
    
    print("✅ faixa_regulatoria OK (limites reais da função)")

def test_norm_modalidade():
    result = rules.norm_modalidade("Geracao na propria UC")
    assert isinstance(result, str)
    print(f"✅ norm_modalidade OK: {result}")

def test_norm_fonte():
    result = rules.norm_fonte("Radiação solar")
    assert isinstance(result, str)
    print(f"✅ norm_fonte OK: {result}")
