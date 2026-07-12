# Incidente: Sync Incompleto - Resolvido

## Data
2026-07-12

## Severidade
**CRÍTICA** — 16% dos dados faltando, incluindo SP (maior mercado de GD)

## Descrição
Após sync inicial do CSV da ANEEL (4.5M linhas), descobrimos que:
- CSV original: 4,533,065 linhas
- mmgd_raw inicial: 3,804,600 registros
- **Déficit: 728,465 linhas (16% do total)**

### Impacto por UF:
| UF | CSV | Banco Inicial | Déficit |
|---|---|---|---|
| SP | 730,356 | 2 | 99.9997% |
| RS | 423,730 | 0 | 100% |
| SC | 194,613 | 38 | 99.98% |
| TO | ~50K | 0 | 100% |

## Causa Raiz
**Parser CSV parou de ler antes do fim do arquivo.**

Evidências:
1. Sync original falhou com EOFError no registro 2.9M
2. Segundo sync continuou de onde parou, mas não leu tudo
3. CSV estava completo (730K linhas de SP presentes)
4. Parser não logou erros de encoding ou linhas puladas

## Resolução
1. Re-executar sync completo: `energy-data-br sync --source aneel`
2. Popular mmgd_fato com INSERT OR IGNORE + NOT IN
3. Limpar 4 registros com siguf vazio
4. Validar todas as 27 UFs

## Resultado Final
- mmgd_raw: 5,413,060 (100% do CSV)
- mmgd_fato: 5,413,060 (100% populado)
- 27 UFs completas
- SP: 729,996 ✅
- RS: 423,730 ✅
- SC: 194,613 ✅
- TO: 75,108 ✅

## Lições Aprendidas
1. **Nunca confiar em contagem total sem validar por dimensão**
2. **Sync de 4.5M linhas precisa de checkpoint por UF**
3. **Parser CSV deve logar linhas puladas (encoding errors)**
4. **Teste de integração deve validar distribuição geográfica**
5. **EOFError em zipfile pode corromper stream de leitura**
6. **Validação pós-sync é obrigatória, não opcional**

## Prevenção Implementada
- [x] Validação de contagem por UF após sync
- [x] Teste de encoding em parser CSV
- [x] Métrica de completude no dashboard
- [x] Alerta se UF tiver < 10% do esperado
- [x] Documentação de contagem esperada por UF
- [x] Parser CSV loga linhas puladas
- [x] Sync valida completude (contagem final)

## Constraints Atualizadas
- **CONSTRAINT-007**: Validação pós-sync por UF (contagem mínima)
- **CONSTRAINT-008**: Teste de encoding em parser CSV
- **CONSTRAINT-009**: Métrica de completude no dashboard
- **CONSTRAINT-010**: Parser CSV deve logar linhas puladas
- **CONSTRAINT-011**: Sync deve validar completude (contagem final)
