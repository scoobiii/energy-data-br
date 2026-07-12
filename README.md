# energy-data-br

ETL + regras de negócio + API + visualização para dados abertos de energia do Brasil.

## Fontes
- ANEEL: MMGD (micro/minigeração), SIGA (usinas centralizadas), Tarifas, SIGET (transmissão)
- ONS: apicarga (carga semi-horária), DESSEM (balanço energético), S3 bulk (histórico)

## Estado atual
- mmgd_raw: 5.413.060 registros (100% do CSV ANEEL)
- mmgd_fato: 5.413.060 registros (100% populado)
- ons_carga: 1.920 registros
- 27 UFs completas
- Banco: 8,3 GB

## Instalação
```bash
git clone https://github.com/scoobiii/energy-data-br.git
cd energy-data-br
pip install -e .
```

## Uso
```bash
# Sync ANEEL MMGD
energy-data-br sync --source aneel

# Sync ONS
energy-data-br sync --source ons --days 7

# API
energy-data-br serve --port 8000

# Endpoints
curl http://localhost:8000/stats
curl http://localhost:8000/totais/uf
curl http://localhost:8000/empreendimentos?uf=SP
```

## Documentação
- [Regras de negócio](docs/regras_negocio.md)
- [Constraints](docs/constraints.md)
- [Arquitetura](docs/architecture.md)
- [Incidente 2026-07-12](docs/incident-report-2026-07-12.md)
- [Cobertura](docs/coverage.md)
- [Roadmap](docs/roadmap.md)
- [Deploy](docs/deploy.md)

## Licença
MIT
