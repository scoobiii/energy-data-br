
# energy-data-br

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![SQLite](https://img.shields.io/badge/sqlite-3.0+-blue.svg)](https://www.sqlite.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Data: ANEEL + ONS](https://img.shields.io/badge/data-ANEEL%20%2B%20ONS-brightgreen)](https://dadosabertos.aneel.gov.br/)

ETL + API + dashboard interativo para os dados abertos de energia do Brasil — integrando **cadastro regulatório da ANEEL** (MMGD e SIGA) com **dados operacionais do ONS** (carga, balanço energético, despacho).

Projeto da [MEx Energia](https://mex.eco.br), usado internamente para mapear oportunidades de mercado em barramento 800VDC + BESS. Aberto à comunidade porque a base é pública e o desafio é comum.

---

## 📦 O que é

- **Fontes oficiais**:
  - **ANEEL MMGD**: Micro e Minigeração Distribuída – snapshot ZIP (4,53M registros).
  - **ANEEL SIGA**: Sistema de Informações de Geração – usinas centralizadas (25k registros).
  - **ONS apicarga**: Carga semi‑horária (atualização diária).
  - **ONS DESSEM**: Balanço energético detalhado (76.877 registros, 414 dias).
- **Regras de negócio explícitas**: classificação de faixa regulatória (Lei 14.300/2022), fonte, modalidade, faixa estratégica MEx.
- **Persistência**: SQLite único com tabelas separadas e índices `UNIQUE` para evitar duplicatas.
- **API REST**: stdlib puro, endpoints para dados agregados, geoespaciais (GeoJSON) e temporais.
- **Dashboard interativo**: mapa (Leaflet) + gráficos (Chart.js) + estatísticas, acessível via `/dashboard`.

> Este repositório **não contém dados de exemplo, mocks ou placeholders**. Toda informação é obtida ao executar o ETL contra as fontes oficiais.

---

## 🔧 Instalação

```bash
git clone https://github.com/scoobiii/energy-data-br.git
cd energy-data-br
pip install -e .
```

Sem dependências externas pesadas — utiliza apenas a biblioteca padrão do Python (urllib, sqlite3, csv, argparse, json, hashlib).
pytest é opcional (apenas para desenvolvimento): pip install -e ".[dev]".

---

🚀 Uso

Sincronização

```bash
# ANEEL – MMGD (teste rápido)
energy-data-br sync --source aneel --max-records 100

# ANEEL – MMGD (completo)
energy-data-br sync --source aneel

# ONS – carga (últimos N dias)
energy-data-br sync --source ons --days 7

# ONS – DESSEM (via módulo dedicado, ainda não integrado ao CLI)
python3 -c "from energy_data_br.ons.dessem_client import sync_all; sync_all()"
```

API (servidor HTTP)

```bash
# Iniciar a API na porta 8000
energy-data-br serve --port 8000
```

Em outro terminal:

```bash
curl http://localhost:8000/stats
curl http://localhost:8000/totais/uf
curl "http://localhost:8000/empreendimentos?uf=SP&limit=10"
curl http://localhost:8000/siga?tipo=UHE&limit=5
```

Dashboard

Acesse no navegador:
http://localhost:8000/dashboard

O dashboard inclui:

· Mapa interativo com ativos MMGD e usinas SIGA.
· Gráfico de barras com Top 10 UFs.
· Gráfico de pizza com distribuição por fonte.
· Tabela com as maiores usinas centralizadas.

Estatísticas e exportação

```bash
# Estatísticas rápidas
energy-data-br stats

# Exportar treemap (hierarquia Brasil > UF > Fonte)
energy-data-br export-treemap --out web/treemap.json

# Gerar documentos para RAG (embedding pendente)
energy-data-br build-vectors
```

---

🏗️ Arquitetura

```
energy-data-br/
├── energy_data_br/              # Pacote principal
│   ├── __init__.py
│   ├── aneel/                   # Cliente ANEEL (MMGD + SIGA)
│   │   ├── api_client.py        # MMGD – ZIP + streaming CSV
│   │   └── siga_client.py       # SIGA – datastore_search paginado
│   ├── ons/                     # Cliente ONS
│   │   ├── api_carga.py         # apicarga (carga semi‑horária)
│   │   └── dessem_client.py     # Balanço DESSEM (414 dias)
│   ├── cli.py                   # Interface de linha de comando
│   ├── db.py                    # Camada SQLite
│   ├── export.py                # Exportação treemap
│   ├── rules.py                 # Regras de negócio
│   └── server.py                # API HTTP (stdlib) + endpoints
├── web/
│   ├── treemap.html             # Visualizador offline (Finviz‑style)
│   └── dashboard.html           # Dashboard interativo (mapa + gráficos)
├── tests/                       # Testes unitários e integração
├── docs/                        # Documentação completa
│   ├── regras_negocio.md
│   ├── constraints.md
│   ├── architecture.md
│   ├── coverage.md
│   ├── incident-report-2026-07-12.md
│   ├── roadmap.md
│   └── deploy.md
├── bin/
│   └── energy-sync.sh           # Script de sincronização diária
├── schema.sql                   # DDL completo
├── pyproject.toml
└── README.md
```

---

📊 Schema SQLite

Tabelas principais

Tabela Descrição Registros
mmgd_raw Landing zone (JSON bruto da ANEEL) 4.533.061
mmgd_fato Fato classificado (fonte, modalidade, faixa regulatória, faixa estratégica MEx) 4.533.061
siga_fato Usinas centralizadas (hidro, térmica, eólica utility‑scale) 25.215
ons_carga Carga verificada/programada (semi‑horária) 1.920
dessem_detalhe Balanço Energético DESSEM (programação diária, patamares, geração por fonte) 76.877
mmgd_vector_docs Documentos para RAG (texto + metadata + coluna embedding) —

Índices UNIQUE (proteção contra duplicatas)

· idx_mmgd_raw_hash ON mmgd_raw(hash)
· idx_mmgd_fato_hash ON mmgd_fato(hash)
· idx_siga_fato_hash ON siga_fato(hash)

Views agregadas

· vw_totais_uf
· vw_totais_fonte
· vw_totais_uf_fonte
· vw_totais_modalidade
· vw_faixa_mex

---

💡 Diferenciais Técnicos

Diferencial Como funciona
Streaming de 1,55 GB csv.DictReader + zipfile — consumo de memória O(1)
Cross‑architecture Stdlib puro — roda em AMD64 e ARM64 (Termux)
Zero dependências pesadas Apenas módulos nativos do Python
Detecção de mudanças SHA‑256 canônico por registro (diff incremental)
Robustez em rede instável Resume download + retry com backoff
Índices UNIQUE Previnem duplicatas mesmo com execuções concorrentes
API stdlib Servidor HTTP nativo, sem frameworks externos
Geoespacial Endpoints GeoJSON para mapas (Leaflet, Mapbox, QGIS)
Dashboard offline‑first HTML estático com dados via API, zero dependência de CDN

---

🗺️ Roadmap

· ONS S3 bulk – histórico completo de carga/demanda (2000–2026)
· ONS Geração por usina – dados horários
· Embedding + RAG – sentence-transformers + sqlite-vec
· Série histórica diária – crescimento do MMGD (growth probe)
· Microserviço FastAPI – Swagger (/docs) e maior performance
· Integração CCEE – PLD, contratos

---

🤝 Contribuindo

Issues e Pull Requests são bem‑vindos.

Antes de abrir um PR:

```bash
pytest tests/ -v
```

Os testes de integração batem nas APIs reais e são ignorados automaticamente se você estiver offline.

---

📄 Licença

MIT — veja o arquivo LICENSE.

---

📚 Documentação adicional

· Regras de negócio
· Constraints de integridade
· Arquitetura
· Cobertura de dados
· Relatório de incidente 2026-07-12
· Roadmap
· Deploy

---

Última atualização: 2026-07-12
EOF

```

---
