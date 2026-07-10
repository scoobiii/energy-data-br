# Regras de Negócio — ANEEL MMGD → MEx Energia

Base regulatória: Lei nº 14.300/2022 (marco legal da GD) e REN ANEEL nº 1.000/2021
e nº 1.059/2023. Estas são as regras aplicadas pelo ETL (`aneel_mmgd_etl.py`) para
classificar cada registro bruto da base de Empreendimentos de Geração Distribuída.

## 1. Faixa regulatória (`faixa_regulatoria`)

| Faixa          | Critério                                                   |
|----------------|-------------------------------------------------------------|
| MICROGERACAO   | potência instalada ≤ 75 kW                                  |
| MINIGERACAO    | potência instalada > 75 kW e ≤ 3 MW (hídrica) / ≤ 5 MW (demais fontes) |
| INDEFINIDA     | potência nula, ausente ou fora dos limites acima            |

> Nota: o corte 3 MW vs 5 MW depende da fonte (hídrica vs demais). O ETL aplica
> 5 MW como teto padrão e sinaliza `is_outlier=1` para hídricas acima de 3 MW,
> para revisão manual — a regra exata varia por resolução e prazo de conexão.

## 2. Normalização de fonte (`fonte_norm`)

Classificação por palavra-chave no texto original (`fonte_bruta`), case-insensitive:

- **UFV** — contém "fotovolta", "solar", "ufv"
- **EOL** — contém "eólic", "eolic", "eol"
- **CGH** — contém "hidr", "cgh", "pch"
- **UTE** — contém "term", "biogás", "biomassa", "gás natural", "ute"
- **OUTRA** — qualquer outro caso (geotérmica, resíduos, não classificado)

## 3. Modalidade (`modalidade_norm`)

Conforme REN 1.000/2021, art. 2º, mapeado por palavra-chave:

- **GERACAO_PROPRIA** — geração na própria UC (autoconsumo local, sem compensação remota)
- **AUTOCONSUMO_REMOTO** — mesma titularidade, unidade geradora ≠ unidade consumidora
- **GERACAO_COMPARTILHADA** — consórcio/cooperativa, múltiplos titulares
- **MUC** — Múltiplas Unidades Consumidoras (mesmo terreno/condomínio)
- **EMUC** — Empreendimento com Múltiplas Unidades Consumidoras
- **INDEFINIDA** — texto não reconhecido pelas regras acima

## 4. Faixa de interesse MEx Energia (`faixa_potencia_mex`)

Esta é a régua estratégica — não regulatória — usada para priorizar leads/mercado
para o barramento 800VDC + BESS (cargas de alta densidade, GPUs, HVAC industrial):

| Bucket           | Potência (kW)     | Racional                                                     |
|------------------|--------------------|----------------------------------------------------------------|
| RESIDENCIAL      | ≤ 15               | fora do foco MEx (ticket baixo, sem caso de uso 800VDC)         |
| COMERCIAL_PEQUENO| 15 – 75            | GD tradicional, baixa prioridade                                |
| MINIGERACAO_ALVO | 75 – 1.000         | zona de entrada MEx: comércio/indústria média, BESS modular     |
| INDUSTRIAL_ALVO  | 1.000 – 5.000      | alvo primário: HVAC industrial, mini-datacenters, 800VDC nativo |
| GRANDE_CARGA     | > 5.000            | fora da faixa MMGD típica — tratar como geração centralizada    |

## 5. Outliers / qualidade (`is_outlier`)

Marcado como `1` quando:
- `potencia_kw` é nulo, ≤ 0, ou não numérico após parsing; ou
- `potencia_kw` > 50.000 kW (implausível para MMGD, provável erro de digitação); ou
- fonte hídrica classificada acima de 3.000 kW sob faixa MINIGERACAO (ver nota acima)

Registros com `is_outlier=1` são mantidos em `mmgd_fato` (auditáveis) mas
excluídos das views agregadas (`vw_totais_*`) para não distorcer os totais.

## 6. Totalização

Todas as views somam `potencia_kw` e convertem para MW (`/1000`), arredondado a
3 casas decimais. Contagem de empreendimentos é `COUNT(*)` simples (cada linha
da base = 1 empreendimento/UC conectada).
