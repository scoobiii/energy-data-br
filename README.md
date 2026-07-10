# aneel-mmgd

ETL + regras de negócio + treemap para os dados abertos de **Micro e Minigeração
Distribuída (MMGD)** da ANEEL — geração solar, eólica, hídrica e térmica
conectada à rede de distribuição em todo o Brasil.

Projeto da [MEx Energia](https://mex.eco.br), usado internamente para
mapear mercado potencial de barramento 800VDC + BESS, e aberto à comunidade
porque a base é pública e o problema (ETL confiável + classificação
regulatória + visualização) é comum a qualquer player do setor.

## O que é

- **Fonte real**: API pública CKAN DataStore do Portal de Dados Abertos ANEEL
  (`dadosabertos.aneel.gov.br`) — sem chave, sem scraping, sem dado inventado.
- **Regras de negócio explícitas**: classificação de faixa regulatória
  (Lei 14.300/2022), fonte, modalidade — ver [`docs/regras_negocio.md`](docs/regras_negocio.md).
- **Persistência local em SQLite**, com uma tabela adicional
  (`mmgd_vector_docs`) já preparada para um pipeline de RAG/fine-tuning
  futuro (texto + metadata prontos; embedding fica para um job separado).
- **Visualização treemap estilo Finviz**, offline-first, zero dependência
  de CDN/JS externo — abre em qualquer navegador, inclusive via Termux.

Este repositório **não contém nenhum dado de exemplo, mock ou placeholder**.
Toda informação vem de rodar o ETL contra a API real.

## Instalação

```bash
git clone https://github.com/scoobiii/aneel-mmgd.git
cd aneel-mmgd
pip install -e .
```

Sem dependências externas (stdlib puro: `urllib`, `sqlite3`, `argparse`).
`pytest` é opcional, só para desenvolvimento (`pip install -e ".[dev]"`).

## Uso

```bash
# 1. baixa e classifica os dados reais (teste rápido: 20k registros)
aneel-mmgd --db aneel_mmgd.sqlite sync --max-records 20000

# 2. base inteira (milhões de linhas — pode levar bastante tempo)
aneel-mmgd --db aneel_mmgd.sqlite sync

# 3. gera os docs de texto prontos para um futuro pipeline de embeddings/RAG
aneel-mmgd --db aneel_mmgd.sqlite build-vectors

# 4. exporta a hierarquia Brasil > UF > Fonte para o treemap
aneel-mmgd --db aneel_mmgd.sqlite export-treemap --out web/aneel_mmgd_treemap.json

# 5. totais direto no terminal
aneel-mmgd --db aneel_mmgd.sqlite stats
```

### Ver o treemap

```bash
cd web
python3 -m http.server 8000
# abra http://localhost:8000/treemap.html
```

(Abrir `treemap.html` direto do disco também funciona — o arquivo tem um
seletor manual de arquivo `.json`, já que `file://` bloqueia `fetch()`.)

## Arquitetura

```
src/aneel_mmgd/
  api_client.py   # HTTP + paginação contra a API real da ANEEL
  rules.py         # regras de negócio puras (testáveis sem I/O)
  db.py            # persistência SQLite (schema.sql + inserts + agregações)
  export.py        # export treemap JSON + resumo de totais
  cli.py           # `aneel-mmgd` (sync / build-vectors / export-treemap / stats)
  schema.sql       # DDL: mmgd_raw -> mmgd_fato -> views -> mmgd_vector_docs
web/
  treemap.html     # viewer standalone, squarified treemap, zero dependência
docs/
  regras_negocio.md
tests/
  test_rules.py                    # regras de negócio, sem rede
  test_db.py                       # SQLite in-memory, sem rede
  test_api_client_integration.py   # bate na API real; pula (skip) se offline
```

### Schema SQLite

- `mmgd_raw` — landing zone (JSON verbatim de cada registro, schema-flexível)
- `mmgd_fato` — fato tipado e classificado (fonte, modalidade, faixa
  regulatória, faixa estratégica MEx, flag de outlier)
- `vw_totais_uf`, `vw_totais_fonte`, `vw_totais_uf_fonte`,
  `vw_totais_modalidade`, `vw_faixa_mex` — agregações prontas
- `mmgd_vector_docs` — texto PT-BR sintetizado a partir das agregações +
  metadata JSON + coluna `embedding` (NULL até um job de embedding rodar)

Detalhes de cada regra: [`docs/regras_negocio.md`](docs/regras_negocio.md).

## Por que a coluna resolve por keyword em vez de nome fixo?

A ANEEL já alterou nomenclatura de colunas entre revisões do dataset.
`rules.resolve_columns()` introspecta o schema real via
`datastore_search?limit=0` e resolve cada campo por substring
(`"potenciainstaladakw" in nome.lower()`), imprimindo o mapeamento resolvido
no início de cada `sync` — se algo não bater, aparece como `[aviso]` no
terminal, não silenciosamente como dado errado.

## Roadmap

- [ ] Job de embedding para `mmgd_vector_docs` (sentence-transformers local,
      ex: `bge-small-pt` ou similar) + índice `sqlite-vec`
- [ ] Suporte a outros datasets ANEEL/ONS via `--resource-id` (SIGA,
      empreendimentos de geração centralizada)
- [ ] Exportação incremental (`sync --since <data>`) em vez de full reload

## Contribuindo

Issues e PRs bem-vindos. Rode `pytest -v` antes de abrir PR — os testes de
integração (`test_api_client_integration.py`) batem na API real e pulam
sozinhos se você estiver offline.

## Licença

MIT — ver [`LICENSE`](LICENSE).
