"""
test_db.py — testa schema, persistência e agregações em SQLite in-memory.

Sem rede: exercita db.py/export.py com registros de entrada plausíveis
(estrutura real do datastore ANEEL), para validar schema.sql + regras de
ponta a ponta. Nenhum dado aqui é publicado como saída do produto.
"""

import json
import sqlite3

from aneel_mmgd import db, export, rules

FIELDS = [{"id": n, "type": "text"} for n in [
    "SigUF", "NomMunicipio", "CodIBGE", "NomAgenteDistribuidor",
    "NomFonteGeracao", "MdaPotenciaInstaladaKW", "DatConexao",
    "NomModalidadeEmpreendimento", "DscClasseConsumo",
]]

RECORDS = [
    {"SigUF": "SP", "NomMunicipio": "Osasco", "CodIBGE": "3536505",
     "NomAgenteDistribuidor": "Enel SP", "NomFonteGeracao": "Fotovoltaica",
     "MdaPotenciaInstaladaKW": "1200,50", "DatConexao": "2024-03-01",
     "NomModalidadeEmpreendimento": "Geração na própria UC", "DscClasseConsumo": "Industrial"},
    {"SigUF": "SP", "NomMunicipio": "Sao Paulo", "CodIBGE": "3550308",
     "NomAgenteDistribuidor": "Enel SP", "NomFonteGeracao": "Eólica",
     "MdaPotenciaInstaladaKW": "85", "DatConexao": "2023-11-11",
     "NomModalidadeEmpreendimento": "Autoconsumo remoto", "DscClasseConsumo": "Comercial"},
    {"SigUF": "MG", "NomMunicipio": "Belo Horizonte", "CodIBGE": "3106200",
     "NomAgenteDistribuidor": "Cemig", "NomFonteGeracao": "Fotovoltaica",
     "MdaPotenciaInstaladaKW": "7,5", "DatConexao": "2022-01-01",
     "NomModalidadeEmpreendimento": "Geração compartilhada", "DscClasseConsumo": "Residencial"},
    {"SigUF": "MG", "NomMunicipio": "Uberlandia", "CodIBGE": "3170206",
     "NomAgenteDistribuidor": "Cemig", "NomFonteGeracao": "Termica a biogas",
     "MdaPotenciaInstaladaKW": "0", "DatConexao": None,
     "NomModalidadeEmpreendimento": "", "DscClasseConsumo": "Rural"},
    {"SigUF": "BA", "NomMunicipio": "Salvador", "CodIBGE": "2927408",
     "NomAgenteDistribuidor": "Coelba", "NomFonteGeracao": "Fotovoltaica",
     "MdaPotenciaInstaladaKW": "3200", "DatConexao": "2024-06-01",
     "NomModalidadeEmpreendimento": "Múltiplas Unidades Consumidoras", "DscClasseConsumo": "Comercial"},
]


def make_conn():
    conn = sqlite3.connect(":memory:")
    db.init_db(conn)
    return conn


def test_schema_creates_all_tables_and_views():
    conn = make_conn()
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('table','view')"
    )}
    for expected in [
        "mmgd_raw", "mmgd_fato", "mmgd_vector_docs",
        "vw_totais_uf", "vw_totais_fonte", "vw_totais_uf_fonte",
        "vw_totais_modalidade", "vw_faixa_mex",
    ]:
        assert expected in tables


def test_insert_records_persists_raw_and_fato():
    conn = make_conn()
    cols = rules.resolve_columns(FIELDS)
    n = db.insert_records(conn, "test-resource", RECORDS, cols)
    assert n == len(RECORDS)

    raw_count = conn.execute("SELECT COUNT(*) FROM mmgd_raw").fetchone()[0]
    fato_count = conn.execute("SELECT COUNT(*) FROM mmgd_fato").fetchone()[0]
    assert raw_count == len(RECORDS)
    assert fato_count == len(RECORDS)

    # raw_json deve preservar o registro original verbatim
    raw_json = conn.execute("SELECT raw_json FROM mmgd_raw LIMIT 1").fetchone()[0]
    parsed = json.loads(raw_json)
    assert parsed["SigUF"] in {"SP", "MG", "BA"}


def test_outlier_excluded_from_aggregate_views():
    conn = make_conn()
    cols = rules.resolve_columns(FIELDS)
    db.insert_records(conn, "test-resource", RECORDS, cols)

    total_fato = conn.execute("SELECT COUNT(*) FROM mmgd_fato").fetchone()[0]
    total_agregado = sum(row[1] for row in conn.execute("SELECT uf, qtd_empreendimentos FROM vw_totais_uf"))
    # o registro de MG/Uberlandia com potencia=0 é outlier e não deve contar
    assert total_fato == 5
    assert total_agregado == 4


def test_vw_totais_uf_soma_corretamente():
    conn = make_conn()
    cols = rules.resolve_columns(FIELDS)
    db.insert_records(conn, "test-resource", RECORDS, cols)

    rows = {uf: mw for uf, _, mw, _ in conn.execute(
        "SELECT uf, qtd_empreendimentos, potencia_total_mw, potencia_media_kw FROM vw_totais_uf"
    )}
    assert rows["BA"] == 3.2
    assert rows["SP"] == round((1200.50 + 85) / 1000, 3)
    assert rows["MG"] == round(7.5 / 1000, 3)


def test_build_vector_docs_generates_text_no_embedding_yet():
    conn = make_conn()
    cols = rules.resolve_columns(FIELDS)
    db.insert_records(conn, "test-resource", RECORDS, cols)
    n = db.build_vector_docs(conn)
    assert n > 0

    row = conn.execute(
        "SELECT text, embedding, embedding_model FROM mmgd_vector_docs WHERE doc_id = 'uf:BA'"
    ).fetchone()
    text, embedding, embedding_model = row
    assert "BA" in text
    assert "1 empreendimentos" in text
    assert embedding is None            # preenchido só por um job de embedding futuro
    assert embedding_model is None


def test_export_treemap_json_structure(tmp_path):
    conn = make_conn()
    cols = rules.resolve_columns(FIELDS)
    db.insert_records(conn, "test-resource", RECORDS, cols)

    out_path = tmp_path / "treemap.json"
    tree = export.export_treemap_json(conn, out_path)

    assert out_path.exists()
    assert tree["name"] == "Brasil"
    assert tree["unit"] == "MW"
    uf_names = {c["name"] for c in tree["children"]}
    assert uf_names == {"SP", "MG", "BA"}

    sp_node = next(c for c in tree["children"] if c["name"] == "SP")
    fonte_names = {f["name"] for f in sp_node["children"]}
    assert fonte_names == {"UFV", "EOL"}


def test_totals_summary(tmp_path):
    conn = make_conn()
    cols = rules.resolve_columns(FIELDS)
    db.insert_records(conn, "test-resource", RECORDS, cols)

    s = export.totals_summary(conn)
    assert s["qtd_empreendimentos"] == 4
    assert s["potencia_total_mw"] > 0
    assert any(f["fonte"] == "UFV" for f in s["por_fonte"])
