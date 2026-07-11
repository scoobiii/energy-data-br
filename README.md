
# energy-data-br

ETL + regras de negócio + treemap para os dados abertos de energia do Brasil — integrando **cadastro regulatório da ANEEL** (MMGD) com **dados operacionais do ONS** (carga e geração).

Projeto da [MEx Energia](https://mex.eco.br), usado internamente para mapear oportunidades de mercado em barramento 800VDC + BESS. Aberto à comunidade porque a base de dados é pública e o desafio (ETL confiável + classificação regulatória + visualização) é comum a qualquer player do setor.

---

## 📦 O que é

- **Fontes oficiais**:
  - **ANEEL**: Portal de Dados Abertos (`dadosabertos.aneel.gov.br`) — snapshot ZIP do cadastro de Micro e Minigeração Distribuída (MMGD).
  - **ONS**: Portal de Dados Abertos (`dados.ons.org.br`) — API `apicarga` (dados semi-horários de carga) e bucket S3 (histórico).
- **Regras de negócio explícitas**: classificação de faixa regulatória (Lei 14.300/2022), fonte primária, modalidade e faixa estratégica — veja [`docs/regras_negocio.md`](docs/regras_negocio.md).
- **Persistência local**: SQLite com tabelas separadas para ANEEL (`mmgd_*`) e ONS (`ons_*`), além de `mmgd_vector_docs` preparada para RAG/fine-tuning.
- **Visualização**: Treemap estilo Finviz, totalmente offline, sem dependências externas de CDN ou JavaScript.

> Este repositório **não contém dados de exemplo, mocks ou placeholders**. Toda informação é obtida ao executar o ETL contra as fontes oficiais.

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

```bash
# 1. Sincronizar ANEEL (teste rápido)
energy-data-br sync --source aneel --max-records 100

# 2. Sincronizar ANEEL completo (~1.55 GB CSV)
energy-data-br sync --source aneel

# 3. Sincronizar ONS (últimos 7 dias)
energy-data-br sync --source ons --days 7

# 4. Gerar documentos para RAG
energy-data-br build-vectors

# 5. Exportar treemap
energy-data-br export-treemap --out web/treemap.json

# 6. Estatísticas
energy-data-br stats
```

### Visualizar o treemap

```bash
cd web
python3 -m http.server 8000
```

Acesse: [http://localhost:8000/treemap.html](http://localhost:8000/treemap.html)

> O arquivo `treemap.html` também pode ser aberto diretamente do disco (possui seletor manual de arquivo JSON).

---

## 🏗️ Arquitetura

```
energy-data-br/
├── aneel/                  # Cliente ANEEL
│   ├── __init__.py
│   └── api_client.py       # ZIP + streaming CSV (1.55 GB)
├── ons/                    # Cliente ONS
│   ├── __init__.py
│   └── api_carga.py        # API apicarga + S3
├── tests/
│   ├── test_api_client_integration.py
│   ├── test_ons_client.py
│   ├── test_db.py
│   └── test_rules.py
├── web/
│   └── treemap.html        # Visualizador offline
├── docs/
│   └── regras_negocio.md
├── cli.py                  # Interface unificada
├── db.py                   # SQLite
├── export.py               # Exportação treemap
├── rules.py                # Regras de negócio
├── schema.sql              # DDL
├── pyproject.toml
└── README.md
```

---

## 📊 Schema SQLite

- `mmgd_raw` — zona de pouso (JSON bruto, schema-flexível)
- `mmgd_fato` — fato classificado (fonte, modalidade, faixa regulatória, faixa estratégica MEx, outlier)
- `ons_fato` — dados de carga verificada/programada por subsistema
- `mmgd_vector_docs` — texto em PT-BR + metadata + coluna `embedding`
- **Views**: `vw_totais_uf`, `vw_totais_fonte`, `vw_totais_uf_fonte`, `vw_totais_modalidade`, `vw_faixa_mex`

---

## 💡 Diferenciais Técnicos

| Diferencial                     | Como funciona |
|-------------------------------|-------------|
| Streaming de 1.55 GB          | `csv.DictReader` + `zipfile` — consumo de memória O(1) |
| Cross-architecture            | Stdlib puro — roda em AMD64 e ARM64 (Termux) |
| Zero dependências pesadas     | Apenas módulos nativos do Python |
| Detecção de mudanças          | SHA-256 canônico por registro |
| Robustez em rede instável     | Resume download + retry com backoff |
| Offline-first                 | Treemap com seletor manual de JSON |

---

## 🗺️ Roadmap

- Geração por usina (ONS) para correlação com MMGD
- Download completo do histórico S3 do ONS
- Pipeline de embeddings + RAG (`sentence-transformers` + `sqlite-vec`)
- Série histórica diária de crescimento do MMGD
- Microserviço FastAPI com Swagger

---

## 🤝 Contribuindo

Issues e Pull Requests são bem-vindos.  
Antes de abrir um PR, rode `pytest -v`. Os testes de integração batem nas APIs reais e são ignorados automaticamente se você estiver offline.

---

## 📄 Licença

MIT — veja o arquivo [LICENSE](LICENSE).

---


