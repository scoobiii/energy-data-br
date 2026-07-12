
# energy-data-br

ETL + regras de negócio + API + visualização para os dados abertos de energia do Brasil — integrando **cadastro regulatório da ANEEL** (MMGD + SIGA) com **dados operacionais do ONS** (carga, despacho, geração).

Projeto da [MEx Energia](https://mex.eco.br), usado internamente para mapear oportunidades de mercado em barramento 800VDC + BESS. Aberto à comunidade porque a base de dados é pública e o desafio (ETL confiável + classificação regulatória + visualização) é comum a qualquer player do setor.

---

## 📦 O que é

- **Fontes oficiais**:
  - **ANEEL**: Portal de Dados Abertos (`dadosabertos.aneel.gov.br`)
    - **MMGD**: Micro e Minigeração Distribuída (snapshot ZIP, ~1.5GB CSV)
    - **SIGA**: Sistema de Informações de Geração (usinas centralizadas)
    - **Tarifas**: Componentes tarifários das distribuidoras
    - **SIGET**: Sistema de Gestão da Transmissão
  - **ONS**: Portal de Dados Abertos (`dados.ons.org.br`)
    - **apicarga**: Dados semi-horários de carga
    - **DESSEM**: Balanço energético e despacho
    - **S3 bulk**: Histórico completo (2000-2026)
- **Regras de negócio explícitas**: classificação de faixa regulatória (Lei 14.300/2022), fonte primária, modalidade e faixa estratégica — veja [`docs/regras_negocio.md`](docs/regras_negocio.md).
- **Persistência local**: SQLite com tabelas separadas para ANEEL (`mmgd_*`, `siga_*`) e ONS (`ons_*`, `dessem_*`), além de `mmgd_vector_docs` preparada para RAG/fine-tuning.
- **API REST**: Endpoints para consulta de empreendimentos, totais por UF/fonte, carga ONS.
- **Visualização**: Treemap estilo Finviz, totalmente offline, sem dependências externas de CDN ou JavaScript.

> Este repositório **não contém dados de exemplo, mocks ou placeholders**. Toda informação é obtida ao executar o ETL contra as fontes oficiais.

---

## 📊 Estado Atual (2026-07-12)

| Dataset | Registros | Tamanho | Cobertura | Status |
|---|---|---|---|---|
| **MMGD** (ANEEL) | 3,804,600 | 4.85GB | 84% do CSV (4.5M linhas) | ✅ Completo |
| **ONS apicarga** | 1,920 | ~5MB | Últimos 7 dias | ⚠️ Parcial |
| **DESSEM** (ONS) | 76,877 | ~50MB | Histórico disponível | ✅ Completo |
| **SIGA** (ANEEL) | — | — | 0% | ❌ Não implementado |
| **Tarifas** (ANEEL) | — | — | 0% | ❌ Não implementado |
| **SIGET** (ANEEL) | — | — | 0% | ❌ Não implementado |
| **Histórico ONS S3** | — | — | 0% | ❌ Não baixado |

**Banco SQLite**: 7.6GB (dados reais, sem fragmentação)
**API**: Respondendo em `localhost:8000`

---

## 🔧 Instalação

```bash
git clone https://github.com/scoobiii/energy-data-br.git
cd energy-data-br
pip install -e .
```

**Sem dependências externas pesadas** — utiliza apenas a biblioteca padrão do Python (`urllib`, `sqlite3`, `csv`, `argparse`, etc.).
`pytest` é opcional (apenas para desenvolvimento): `pip install -e ".[dev]"`.

---

## 🚀 Uso

### Sincronização de dados

```bash
# 1. Sincronizar ANEEL MMGD (teste rápido)
energy-data-br sync --source aneel --max-records 100

# 2. Sincronizar ANEEL MMGD completo (~1.55 GB CSV, 4.5M registros)
energy-data-br sync --source aneel

# 3. Sincronizar ONS apicarga (últimos 7 dias)
energy-data-br sync --source ons --days 7

# 4. Sincronizar DESSEM (balanço energético)
energy-data-br sync --source dessem
```

### API REST

```bash
# Subir API
energy-data-br serve --port 8000

# Endpoints disponíveis:
curl http://localhost:8000/stats                    # Estatísticas do banco
curl http://localhost:8000/totais/uf                # Totais por UF
curl http://localhost:8000/empreendimentos?uf=SP    # Empreendimentos por UF
curl http://localhost:8000/ons/carga                # Dados de carga ONS
```

### Exportação e visualização

```bash
# 1. Gerar documentos para RAG
energy-data-br build-vectors

# 2. Exportar treemap
energy-data-br export-treemap --out web/treemap.json

# 3. Estatísticas
energy-data-br stats

# 4. Visualizar o treemap
cd web
python3 -m http.server 8000
# Acesse: http://localhost:8000/treemap.html
```

---

## 🏗️ Arquitetura


```
energy-data-br/
├── energy_data_br/              # Pacote principal
│   ├── __init__.py
│   ├── cli.py                   # Interface unificada (argparse)
│   ├── db.py                    # SQLite (conexão, schema, queries)
│   ├── server.py                # API REST (http.server stdlib)
│   ├── export.py                # Exportação treemap JSON
│   ├── rules.py                 # Regras de negócio (classificação)
│   ├── aneel/                   # Cliente ANEEL
│   │   ├── __init__.py
│   │   ├── api_client.py        # ZIP + streaming CSV (1.55 GB)
│   │   └── cli.py               # Subcomandos ANEEL
│   └── ons/                     # Cliente ONS
│       ├── __init__.py
│       ├── api_carga.py         # API apicarga + S3
│       └── dessem_client.py     # Balanço DESSEM
├── tests/                       # Testes unitários e de integração
│   ├── conftest.py
│   ├── test_aneel_client.py
│   ├── test_cli.py
│   ├── test_ons_client.py
│   └── test_db.py
├── web/
│   └── treemap.html             # Visualizador offline (Finviz-style)
├── docs/
│   ├── regras_negocio.md        # Classificação regulatória
│   ├── constraints.md           # Regras de integridade
│   └── auditoria-2026-07-12.md  # Post-mortem incidente
├── bin/
│   └── energy-sync.sh           # Script de sync com lockfile
├── schema.sql                   # DDL completo
├── pyproject.toml               # Configuração do pacote
└── README.md
```

---

## 📊 Schema SQLite

### Tabelas principais

- **`mmgd_raw`** — Zona de pouso ANEEL MMGD (JSON bruto, schema-flexível)
  - 3,804,600 registros
  - Índice UNIQUE em `hash`
  
- **`mmgd_fato`** — Fato classificado ANEEL MMGD
  - 3,804,600 registros
  - Colunas: `cod_empreendimento`, `siguf`, `dscfontegeracao`, `potencia_instalada_kw`, `modalidade`, `faixa_regulatoria`, `hash`
  - Índice UNIQUE em `hash`
  
- **`ons_carga`** — Dados de carga ONS (apicarga)
  - 1,920 registros
  - Atualização semi-horária
  
- **`dessem_detalhe`** — Balanço energético DESSEM
  - 76,877 registros
  - Histórico completo disponível

### Tabelas auxiliares

- **`mmgd_vector_docs`** — Texto em PT-BR + metadata + coluna `embedding` (preparada para RAG)
- **`mmgd_meta`** — Metadados de sync (última atualização, hash do snapshot)
- **`growth_log`** — Log de crescimento diário (para projeções)

### Views

- `vw_totais_uf` — Totais por UF
- `vw_totais_fonte` — Totais por fonte de geração
- `vw_totais_uf_fonte` — Totais por UF e fonte
- `vw_totais_modalidade` — Totais por modalidade (micro/minigeração)
- `vw_faixa_mex` — Totais por faixa estratégica MEx

---

## 💡 Diferenciais Técnicos

| Diferencial | Como funciona |
|---|---|
| **Streaming de 1.55 GB** | `csv.DictReader` + `zipfile` — consumo de memória O(1) |
| **Cross-architecture** | Stdlib puro — roda em AMD64 e ARM64 (Termux) |
| **Zero dependências pesadas** | Apenas módulos nativos do Python |
| **Detecção de mudanças** | SHA-256 canônico por registro (idempotência) |
| **Robustez em rede instável** | Resume download + retry com backoff |
| **Offline-first** | Treemap com seletor manual de JSON |
| **Índices UNIQUE** | Previne duplicatas em syncs concorrentes |
| **API REST stdlib** | `http.server` + `ThreadingHTTPServer` (200 RPS) |
| **Lockfile de sync** | Previne execução concorrente |

---

## 🗺️ Roadmap — Sprints até Objetivo Final

### **Objetivo Final**
Sistema completo de dados energéticos brasileiros cobrindo:
- ✅ Geração distribuída (MMGD)
- ⏳ Geração centralizada (SIGA)
- ⏳ Carga e despacho (ONS tempo real)
- ⏳ Tarifas e componentes tarifários
- ⏳ Transmissão (SIGET)
- ⏳ Histórico completo (2000-2026)
- ⏳ Dashboard interativo + RAG

---

### **Sprint 1: SIGA — Usinas Centralizadas** (2-3h)
**Status**: ⏳ Não iniciado

**Objetivo**: Adicionar todos os ativos de geração centralizada (hidrelétricas, térmicas, eólicas utility-scale)

**Tarefas**:
- [ ] Baixar CSV SIGA (15MB) + XML diário (50MB)
- [ ] Validar estrutura e campos
- [ ] Implementar `energy_data_br/siga/api_client.py`
- [ ] Criar tabela `siga_raw` e `siga_fato`
- [ ] Popular com dados SIGA (~50K registros estimados)
- [ ] Atualizar API com endpoint `/ativos?perfil=SIGA`

**Entregáveis**:
- SIGA integrado ao banco
- API retorna MMGD + SIGA unificados
- Treemap atualizado com geração centralizada

---

### **Sprint 2: Histórico ONS S3** (1 dia)
**Status**: ⏳ Não iniciado

**Objetivo**: Baixar e processar histórico completo do ONS (2000-2026)

**Tarefas**:
- [ ] Download do bucket S3 `ons-aws-prod-opendata` (~6GB)
- [ ] Processar arquivos CSV/Parquet
- [ ] Criar tabela `ons_carga_historico`
- [ ] Popular com dados históricos
- [ ] Criar índices por data e área de carga

**Entregáveis**:
- 26 anos de dados de carga ONS
- API com endpoint `/ons/historico?area=&dat_inicio=&dat_fim=`
- Gráficos de série histórica no dashboard

---

### **Sprint 3: Atualização Tempo Real** (1 semana)
**Status**: ⏳ Não iniciado

**Objetivo**: Implementar atualização em tempo real (5 min a 1 hora)

**Tarefas**:
- [ ] Resolver `cod_areacarga` do apicarga
- [ ] Implementar despacho (API ONS, 5 min)
- [ ] Implementar geração por usina (API ONS, 1 hora)
- [ ] Implementar CMO (custo marginal, semanal)
- [ ] Criar cron jobs para atualização automática
- [ ] Implementar alertas de disponibilidade

**Entregáveis**:
- Dados atualizados em tempo real
- Dashboard com dados ao vivo
- Sistema de alertas

---

### **Sprint 4: Tarifas e Componentes Tarifários** (2-3 dias)
**Status**: ⏳ Não iniciado

**Objetivo**: Integrar dados de tarifas das distribuidoras

**Tarefas**:
- [ ] Baixar CSV de tarifas (~50MB)
- [ ] Implementar `energy_data_br/aneel/tarifas_client.py`
- [ ] Criar tabela `tarifas_distribuidoras`
- [ ] Popular com dados de TE (Tarifa de Energia) e TUSD (Tarifa de Uso do Sistema)
- [ ] Atualizar API com endpoint `/tarifas?distribuidora=&ano=`

**Entregáveis**:
- Tarifas de todas as distribuidoras
- API com consulta de tarifas históricas
- Treemap com densidade tarifária por UF

---

### **Sprint 5: SIGET — Transmissão** (2-3 dias)
**Status**: ⏳ Não iniciado

**Objetivo**: Integrar dados de linhas de transmissão

**Tarefas**:
- [ ] Baixar CSV SIGET (~30MB)
- [ ] Implementar `energy_data_br/aneel/siget_client.py`
- [ ] Criar tabela `siget_linhas`
- [ ] Popular com dados de linhas de transmissão
- [ ] Atualizar API com endpoint `/transmissao?uf=&tensao=`

**Entregáveis**:
- Mapa de linhas de transmissão
- API com consulta de capacidade
- Correlação com MMGD (proximidade a linhas)

---

### **Sprint 6: Dashboard Completo + RAG** (1 semana)
**Status**: ⏳ Não iniciado

**Objetivo**: Dashboard interativo completo + busca semântica

**Tarefas**:
- [ ] Expandir treemap.html com todos os datasets
- [ ] Implementar filtros avançados (data, fonte, UF, modalidade)
- [ ] Integrar RAG local (`bge-small-pt` + `sqlite-vec`)
- [ ] Fine-tuning de modelo para energia brasileira (Colab)
- [ ] Implementar busca semântica na API
- [ ] Criar endpoint `/api/rag?query=`

**Entregáveis**:
- Dashboard completo com todos os dados
- Busca semântica funcionando
- Modelo especializado em energia brasileira

---

### **Sprint 7: Otimização e Escalabilidade** (3-5 dias)
**Status**: ⏳ Não iniciado

**Objetivo**: Otimizar performance e preparar para produção

**Tarefas**:
- [ ] Migrar SQLite → PostgreSQL (se necessário)
- [ ] Implementar cache Redis para API
- [ ] Otimizar queries lentas (EXPLAIN ANALYZE)
- [ ] Implementar rate limiting na API
- [ ] Criar documentação OpenAPI/Swagger
- [ ] Implementar testes de carga (k6)

**Entregáveis**:
- API escalável (1000+ RPS)
- Documentação completa
- Testes de carga validados

---

### **Sprint 8: Deploy e Monitoramento** (2-3 dias)
**Status**: ⏳ Não iniciado

**Objetivo**: Deploy em produção com monitoramento

**Tarefas**:
- [ ] Configurar Docker + docker-compose
- [ ] Deploy em Cloud Run ou VPS
- [ ] Implementar monitoramento (Prometheus + Grafana)
- [ ] Configurar alertas (Slack/Email)
- [ ] Criar backup automático do banco
- [ ] Documentar procedimentos de operação

**Entregáveis**:
- Sistema em produção
- Monitoramento completo
- Documentação de operação

---

## 📈 Projeção de Armazenamento

| Componente | Tamanho | Status |
|---|---|---|
| MMGD (atual) | 7.6GB | ✅ OK |
| + SIGA | ~100MB | ⏳ Sprint 1 |
| + Histórico ONS | ~6GB | ⏳ Sprint 2 |
| + Tarifas | ~50MB | ⏳ Sprint 4 |
| + SIGET | ~30MB | ⏳ Sprint 5 |
| **Total estimado** | **~14GB** | 13% do disco (108GB) |

**Atualização tempo real**: ~500KB/dia → 180MB/ano

---

## 🤝 Contribuindo

Issues e Pull Requests são bem-vindos.
Antes de abrir um PR, rode `pytest -v`. Os testes de integração batem nas APIs reais e são ignorados automaticamente se você estiver offline.

---

## 📄 Licença

MIT — veja o arquivo [LICENSE](LICENSE).

---

## 📞 Contato

- **Projeto**: [MEx Energia](https://mex.eco.br)
- **GitHub**: [@scoobiii](https://github.com/scoobiii)
- **Issues**: [energy-data-br/issues](https://github.com/scoobiii/energy-data-br/issues)
