"""silver (parquet) -> DuckDB: carga incremental por partição + gold em SQL + checagens de qualidade."""
import logging

import duckdb

from src.config import PROJECT_ROOT, SILVER_DIR, WAREHOUSE_PATH, particao

logger = logging.getLogger(__name__)

GOLD_SQL_DIR = PROJECT_ROOT / "sql" / "gold"

# cada checagem retorna a quantidade de linhas que violam a regra (esperado: 0)
CHECAGENS = {
    "chave nula": "SELECT count(*) FROM silver.produtos WHERE codigo_produto IS NULL OR data_extracao IS NULL",
    "chave duplicada": """
        SELECT count(*) FROM (
            SELECT codigo_produto, data_extracao FROM silver.produtos
            GROUP BY ALL HAVING count(*) > 1
        )""",
    "preço <= 0": "SELECT count(*) FROM silver.produtos WHERE preco <= 0",
    "avaliação fora de 0-5": "SELECT count(*) FROM silver.produtos WHERE avaliacao_media NOT BETWEEN 0 AND 5",
}


def conectar() -> duckdb.DuckDBPyConnection:
    WAREHOUSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(WAREHOUSE_PATH))
    con.execute("CREATE SCHEMA IF NOT EXISTS silver")
    con.execute("CREATE SCHEMA IF NOT EXISTS gold")
    return con


def carregar_silver(con: duckdb.DuckDBPyConnection, categoria: str, data: str) -> None:
    """Substitui a partição (categoria, data) no banco — reprocessar não duplica."""
    arquivo = (particao(SILVER_DIR, categoria, data) / "produtos.parquet").as_posix()

    # na primeira carga, a tabela nasce com o schema do parquet + coluna da partição
    con.execute(f"""
        CREATE TABLE IF NOT EXISTS silver.produtos AS
        SELECT *, ''::VARCHAR AS categoria_slug FROM read_parquet('{arquivo}') LIMIT 0
    """)

    con.execute("BEGIN")
    con.execute(
        "DELETE FROM silver.produtos WHERE categoria_slug = ? AND CAST(data_extracao AS DATE) = ?",
        [categoria, data],
    )
    con.execute(
        f"INSERT INTO silver.produtos BY NAME SELECT *, ? AS categoria_slug FROM read_parquet('{arquivo}')",
        [categoria],
    )
    con.execute("COMMIT")

    n = con.execute(
        "SELECT count(*) FROM silver.produtos WHERE categoria_slug = ? AND CAST(data_extracao AS DATE) = ?",
        [categoria, data],
    ).fetchone()[0]
    logger.info("[load] silver.produtos %s %s | %d registros", categoria, data, n)


def construir_gold(con: duckdb.DuckDBPyConnection) -> None:
    for arquivo in sorted(GOLD_SQL_DIR.glob("*.sql")):
        con.execute(arquivo.read_text(encoding="utf-8"))
        tabela = arquivo.stem.split("_", 1)[1]
        n = con.execute(f"SELECT count(*) FROM gold.{tabela}").fetchone()[0]
        logger.info("[gold] gold.%s | %d linhas", tabela, n)


def checar_qualidade(con: duckdb.DuckDBPyConnection) -> None:
    falhas = {nome: con.execute(sql).fetchone()[0] for nome, sql in CHECAGENS.items()}
    falhas = {nome: n for nome, n in falhas.items() if n}
    if falhas:
        raise ValueError(f"Checagens de qualidade falharam: {falhas}")
    logger.info("[qualidade] %d checagens ok", len(CHECAGENS))


def carregar(particoes: list[tuple[str, str]]) -> None:
    with conectar() as con:
        for categoria, data in particoes:
            carregar_silver(con, categoria, data)
        checar_qualidade(con)
        construir_gold(con)
