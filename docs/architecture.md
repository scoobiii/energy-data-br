# Arquitetura

## Componentes
- ANEEL MMGD: ZIP snapshot, parse streaming, dedup por hash
- ONS apicarga: API semi-horária, atualização diária
- DESSEM: Baixa diária dos 414 arquivos mais recentes
- SQLite: Banco único, tabelas separadas por fonte
- API: stdlib http.server, zero dependências

## Fluxo de dados
1. energy-data-br sync --source aneel → baixa ZIP, insere mmgd_raw (INSERT OR IGNORE)
2. sync_lock.sh → popula mmgd_fato a partir de mmgd_raw
3. energy-data-br sync --source ons → busca carga e insere em ons_carga
4. energy_data_br/ons/dessem_client.py → baixa CSVs do DESSEM

## Proteção contra duplicatas
- UNIQUE INDEX em hash (raw e fato)
- INSERT OR IGNORE em todos os syncs
- Lock file (/tmp/energy-data-br-sync.lock) impede execução concorrente

## Espaço em disco
- Banco atual: 8,3 GB (dados + índices + overhead)
- Crescimento esperado: ~0,5 GB/ano (apicarga) + novos datasets
