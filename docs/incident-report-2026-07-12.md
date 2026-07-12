# Relatório de Incidente - 2026-07-12

## Resumo
- mmgd_raw chegou a 12,2M registros (duplicação massiva)
- mmgd_fato ficou vazio durante operação interrompida
- Banco inchou para 18,89 GB

## Causa raiz
- cli.py usava INSERT simples (sem INSERT OR IGNORE)
- mmgd_raw não tinha UNIQUE INDEX em hash
- Syncs interrompidos (bateria, pkill) antes de completar leitura do CSV

## Correção
1. Criar UNIQUE INDEX em mmgd_raw.hash e mmgd_fato.hash
2. Substituir INSERT por INSERT OR IGNORE no cli.py
3. Executar dedup: DELETE FROM mmgd_raw WHERE rowid NOT IN (SELECT MAX(rowid) FROM mmgd_raw GROUP BY hash)
4. VACUUM (não liberou espaço, mas banco ficou compacto)
5. Refazer sync completo para trazer todos os 5,4M registros
6. Re-popular mmgd_fato via INSERT OR IGNORE

## Resultado
- mmgd_raw e mmgd_fato: 5.413.060 registros
- Índices UNIQUE criados
- integrity_check: ok
- Tamanho final: 8,3 GB (estabilizado)

## Prevenção futura
- Testar novos syncs com --max-records pequeno
- Manter tmux ou nohup para execuções longas
- Usar sync_lock.sh para evitar concorrência
