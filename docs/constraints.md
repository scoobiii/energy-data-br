# Constraints de integridade

## UNIQUE hash
- mmgd_raw.hash e mmgd_fato.hash são UNIQUE
- Impedem duplicatas em execuções concorrentes

```sql
CREATE UNIQUE INDEX idx_mmgd_raw_hash ON mmgd_raw(hash);
CREATE UNIQUE INDEX idx_mmgd_fato_hash ON mmgd_fato(hash);
```

## Índices adicionais
- idx_mmgd_fato_siguf - consultas por UF
- idx_mmgd_fato_fonte - consultas por fonte
- idx_mmgd_fato_potencia - filtros por potência
- idx_ons_carga_tipo_area - consultas ONS

## Auto-vacuum
Por padrão desligado (0). Ativar com:
```sql
PRAGMA auto_vacuum=FULL;
```
