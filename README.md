


# energy-data-br

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![SQLite](https://img.shields.io/badge/sqlite-3.0+-blue.svg)](https://www.sqlite.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Data: ANEEL + ONS](https://img.shields.io/badge/data-ANEEL%20%2B%20ONS-brightgreen)](https://dadosabertos.aneel.gov.br/)

**O que era:** um scraper frágil que quebrava com DNS instável e perdia 77% dos dados.

**O que é:** ETL + API + dashboard + agente de reconciliação — pipeline canônico para dados abertos de energia do Brasil, integrando cadastro regulatório da ANEEL (MMGD e SIGA) com dados operacionais do ONS (carga, balanço energético, despacho), rodando em produção no seu bolso (Termux + Galaxy A23).

**O que pode ser:** plataforma de tokenização de excedentes de micro e minigeração distribuída (Lei 14.300/2022), pronta para Web3 (DREX, ERC-721, DID) e negociação peer‑to‑peer.

---

## 📦 O que é

- **Fontes oficiais**:
  - **ANEEL MMGD**: Micro e Minigeração Distribuída – 5.947.561 registros (snapshot completo).
  - **ANEEL SIGA**: Sistema de Informações de Geração – usinas centralizadas (25.215 registros).
  - **ONS apicarga**: Carga semi‑horária (1.536 pontos recentes, atualização a cada 30 min).
  - **ONS DESSEM**: Balanço energético detalhado (76.877 registros, 414 dias).
- **Regras de negócio explícitas**: classificação de faixa regulatória (Lei 14.300/2022), fonte, modalidade, faixa estratégica MEx.
- **Persistência**: SQLite único com tabelas separadas e índices `UNIQUE` para evitar duplicatas.
- **API REST**: stdlib puro, endpoints para dados agregados, geoespaciais (GeoJSON), temporais e tokenização de excedentes.
- **Dashboard interativo**: mapa (Leaflet) + gráficos (Chart.js) + estatísticas, acessível via `/dashboard`.
- **Agente de reconciliação**: monitoramento contínuo da integridade dos dados (zero críticos).
- **Módulo de tokenização**: cadastro de clientes (PF/PJ), créditos excedentes tokenizáveis (ERC-721/DREX), histórico de transações on‑chain.

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
# Iniciar a API na porta 8080
energy-data-br serve --port 8080
```

Em outro terminal:

```bash
# Estatísticas gerais
curl http://localhost:8080/stats

# Totais por UF
curl http://localhost:8080/totais/uf

# Empreendimentos MMGD
curl "http://localhost:8080/empreendimentos?uf=SP&limit=10"

# Usinas centralizadas (SIGA)
curl http://localhost:8080/siga?tipo=UHE&limit=5

# Geração por fonte (DESSEM)
curl "http://localhost:8080/geracao/fonte?inicio=2025-05-23&fim=2025-05-24"

# Série temporal de geração
curl "http://localhost:8080/geracao/serie?fonte=solar&inicio=2025-05-20&fim=2025-05-30"

# Tokenização – saldo de créditos
curl "http://localhost:8080/token/saldo?cliente_id=1"

# Tokenização – vender excedente (POST)
curl -X POST "http://localhost:8080/token/vender" \
  -H "Content-Type: application/json" \
  -d '{"credito_id":1, "quantidade_kwh":500, "valor_rs":400, "tx_blockchain":"0xTxSimulado123"}'
```

Dashboard

Acesse no navegador:
http://localhost:8080/dashboard

O dashboard inclui:

· Mapa interativo com ativos MMGD e usinas SIGA.
· Gráfico de barras com Top 10 UFs.
· Gráfico de pizza com distribuição por fonte.
· Tabela com as maiores usinas centralizadas.

Reconciliação

```bash
# Verificação completa
python3 -m energy_data_br.reconciliation.agent --check all
```

---

🏗️ Arquitetura

```
energy-data-br/
├── energy_data_br/              # Pacote principal
│   ├── aneel/                   # Cliente ANEEL (MMGD + SIGA)
│   │   ├── api_client.py        # MMGD – ZIP + streaming CSV
│   │   └── siga_client.py       # SIGA – datastore_search paginado
│   ├── ons/                     # Cliente ONS
│   │   ├── api_carga.py         # Carga semi‑horária (retry DNS incluso)
│   │   └── dessem_client.py     # Balanço DESSEM (414 dias)
│   ├── etl/                     # ETL
│   │   ├── populate_mmgd_fato.py
│   │   ├── populate_siga_fato.py
│   │   └── update_mmgd_fato_campos.py
│   ├── reconciliation/          # Agente de reconciliação
│   │   └── agent.py
│   ├── tokenizacao.py           # Módulo de tokenização de excedentes
│   ├── predicao.py              # Predição de carga e MMGD (statsmodels)
│   ├── cli.py                   # Interface de linha de comando
│   ├── db.py                    # Camada SQLite
│   ├── export.py                # Exportação treemap
│   ├── rules.py                 # Regras de negócio
│   └── server.py                # API HTTP (stdlib) + endpoints
├── web/
│   ├── treemap.html
│   └── dashboard.html
├── tests/                       # Testes unitários e integração
├── docs/                        # Documentação completa
├── schema.sql                   # DDL completo
├── pyproject.toml
└── README.md
```

---

📊 Schema SQLite

Tabela Descrição Registros
mmgd_raw Landing zone (JSON bruto da ANEEL) 5.947.561
mmgd_fato Fato classificado + campos descritivos + tokenização 5.947.561
siga_fato Usinas centralizadas 25.215
ons_carga Carga verificada semi‑horária 1.920
dessem_detalhe Balanço energético DESSEM 76.877
cliente Clientes PF/PJ com DID e carteira Web3 —
credito_excedente Créditos tokenizáveis —
transacao_token Histórico de transações on‑chain —

---

💡 Diferenciais Técnicos

Diferencial Como funciona
Streaming de 1,55 GB csv.DictReader + zipfile — memória O(1)
Cross‑architecture Stdlib puro — roda em AMD64 e ARM64 (Termux)
Zero dependências pesadas Apenas módulos nativos do Python
Detecção de mudanças SHA‑256 canônico por registro (diff incremental)
Robustez em rede instável Resume download + retry com backoff
Índices UNIQUE Previnem duplicatas mesmo com execuções concorrentes
API stdlib Servidor HTTP nativo, sem frameworks externos
Geoespacial Endpoints GeoJSON para mapas
Tokenização Web3 Pronto para DREX, ERC-721, DID (Lei 14.300/2022)
Dashboard offline‑first HTML estático com dados via API, zero CDN

---

🗺️ Roadmap

· ETL robusto com retry e reconciliação
· API REST com séries temporais e tokenização
· Agente de reconciliação (zero críticos)
· Módulo de tokenização (créditos, vendas, blockchain)
· ONS S3 bulk – histórico completo de carga (2000–2026)
· Integração real com smart contracts (DREX/Web3)
· Importação de faturas para saldo real de créditos
· Microserviço FastAPI – Swagger (/docs) e maior performance

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

Última atualização: 2026-07-14
Status: Back-end 100% operacional. Pipeline ETL + API + Tokenização. "O pai voa."

```
