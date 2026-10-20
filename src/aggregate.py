"""silver -> gold: tabelas agregadas prontas para análise. Recalculadas a partir de toda a silver."""
import logging

import pandas as pd

from src.config import GOLD_DIR, SILVER_DIR

logger = logging.getLogger(__name__)


def ler_silver() -> pd.DataFrame:
    arquivos = sorted(SILVER_DIR.glob("categoria=*/data_extracao=*/produtos.parquet"))
    if not arquivos:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(a) for a in arquivos], ignore_index=True)


def resumo_por_faixa(df: pd.DataFrame) -> pd.DataFrame:
    return (
        df.groupby(["categoria", "data_extracao", "faixa_preco"], observed=True)
        .agg(
            qtd_produtos=("codigo_produto", "count"),
            preco_medio=("preco", "mean"),
            desconto_medio_pct=("desconto_pct", "mean"),
            pct_com_desconto=("tem_desconto", "mean"),
            avaliacao_media=("avaliacao_media", "mean"),
        )
        .round(2)
        .reset_index()
    )


def historico_precos(df: pd.DataFrame) -> pd.DataFrame:
    """Preço de cada produto em cada extração — base para acompanhar variação ao longo do tempo."""
    return (
        df[["codigo_produto", "titulo_produto", "categoria", "data_extracao", "preco", "preco_original"]]
        .sort_values(["codigo_produto", "data_extracao"])
        .reset_index(drop=True)
    )


def agregar() -> None:
    df = ler_silver()
    if df.empty:
        logger.warning("[gold] silver vazia, nada a agregar")
        return

    GOLD_DIR.mkdir(parents=True, exist_ok=True)
    for nome, tabela in {
        "resumo_por_faixa": resumo_por_faixa(df),
        "historico_precos": historico_precos(df),
    }.items():
        output = GOLD_DIR / f"{nome}.parquet"
        tabela.to_parquet(output, index=False, engine="pyarrow")
        logger.info("[gold] %s | %d linhas -> %s", nome, len(tabela), output)
