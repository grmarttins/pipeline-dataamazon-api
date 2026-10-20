"""bronze -> silver: tipagem, limpeza, schema fixo, um registro por produto."""
import logging
import re
from pathlib import Path

import pandas as pd

from src.config import BRONZE_DIR, CATEGORIAS, SILVER_DIR, particao
from src.observabilidade import agora_utc

logger = logging.getLogger(__name__)

FAIXAS_BINS = [0, 50, 200, 500, 1500, float("inf")]
FAIXAS_LABELS = ["Até R$50", "R$50-200", "R$200-500", "R$500-1500", "Acima de R$1500"]

# coluna bronze -> coluna silver
RENOMEAR = {
    "asin":                        "codigo_produto",
    "product_title":               "titulo_produto",
    "product_price":               "preco",
    "product_original_price":      "preco_original",
    "product_minimum_offer_price": "preco_minimo_oferta",
    "product_star_rating":         "avaliacao_media",
    "product_num_ratings":         "quantidade_avaliacoes",
    "product_num_offers":          "quantidade_ofertas",
    "product_url":                 "url_produto",
    "product_photo":               "url_imagem",
    "is_prime":                    "prime",
    "is_best_seller":              "mais_vendido",
    "is_amazon_choice":            "escolha_amazon",
    "climate_pledge_friendly":     "sustentavel",
    "has_variations":              "tem_variacoes",
    "coupon_text":                 "cupom",
}

# schema fixo da silver: toda partição sai com exatamente estas colunas, nesta ordem
SCHEMA_SILVER = {
    "codigo_produto":         "string",
    "titulo_produto":         "string",
    "categoria":              "string",
    "preco":                  "Float64",
    "preco_original":         "Float64",
    "preco_minimo_oferta":    "Float64",
    "desconto_pct":           "Float64",
    "tem_desconto":           "boolean",
    "faixa_preco":            "string",
    "avaliacao_media":        "Float64",
    "quantidade_avaliacoes":  "Int64",
    "quantidade_ofertas":     "Int64",
    "volume_vendas_estimado": "Int64",
    "prime":                  "boolean",
    "mais_vendido":           "boolean",
    "escolha_amazon":         "boolean",
    "sustentavel":            "boolean",
    "tem_variacoes":          "boolean",
    "entrega_gratis":         "boolean",
    "plataforma":             "string",
    "cupom":                  "string",
    "url_produto":            "string",
    "url_imagem":             "string",
    "data_extracao":          "datetime64[us]",
    # linhagem (UTC): metadados, não entram na chave nem na deduplicação
    "extraido_em":            "datetime64[us, UTC]",
    "ingerido_em":            "datetime64[us, UTC]",
    "processado_em":          "datetime64[us, UTC]",
    "run_id":                 "string",
}


def parse_preco(val) -> float | None:
    if pd.isna(val):
        return None
    try:
        return float(re.sub(r"[R$\s.]", "", str(val)).replace(",", "."))
    except ValueError:
        logger.warning("parse_preco: valor inesperado '%s'", val)
        return None


def parse_volume(val) -> int | None:
    if pd.isna(val):
        return None
    numeros = re.findall(r"\d+", str(val).replace(".", "").replace(",", ""))
    if not numeros:
        return None
    n = int(numeros[0])
    if "mil" in str(val).lower():
        n *= 1000
    return n


def parse_bool(val) -> bool | None:
    if pd.isna(val):
        return None
    return str(val).strip().lower() == "true"


def parse_entrega_gratis(val) -> bool:
    if pd.isna(val):
        return False
    return "GRÁTIS" in str(val).upper()


def transform(df: pd.DataFrame, run_id: str) -> pd.DataFrame:
    df = df.rename(columns=RENOMEAR)

    # garante que colunas opcionais da API existam, mesmo vazias
    for col in list(RENOMEAR.values()) + ["sales_volume", "delivery", "book_format", "_extraido_em", "_ingerido_em"]:
        if col not in df.columns:
            df[col] = pd.NA

    for col in ["preco", "preco_original", "preco_minimo_oferta"]:
        df[col] = df[col].apply(parse_preco)
    for col in ["prime", "mais_vendido", "escolha_amazon", "sustentavel", "tem_variacoes"]:
        df[col] = df[col].apply(parse_bool)
    for col in ["avaliacao_media", "quantidade_avaliacoes", "quantidade_ofertas"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["desconto_pct"] = ((df["preco_original"] - df["preco"]) / df["preco_original"] * 100).round(1)
    df["tem_desconto"] = df["preco_original"].notna()
    df["faixa_preco"] = pd.cut(df["preco"], bins=FAIXAS_BINS, labels=FAIXAS_LABELS).astype("string")
    df["volume_vendas_estimado"] = df["sales_volume"].apply(parse_volume)
    df["entrega_gratis"] = df["delivery"].apply(parse_entrega_gratis)
    df["plataforma"] = df["book_format"].fillna("Geral").astype(str).str.strip()
    df["categoria"] = df["_categoria"].map(lambda c: CATEGORIAS.get(c, (None, c))[1])
    df["data_extracao"] = pd.to_datetime(df["_data_extracao"], errors="coerce")
    df["extraido_em"] = pd.to_datetime(df["_extraido_em"], errors="coerce", utc=True)
    df["ingerido_em"] = pd.to_datetime(df["_ingerido_em"], errors="coerce", utc=True)
    df["processado_em"] = agora_utc()
    df["run_id"] = run_id

    # mesmo produto pode aparecer em mais de uma página: fica a primeira ocorrência
    df = df.dropna(subset=["codigo_produto"]).drop_duplicates(subset=["codigo_produto"])

    return df[list(SCHEMA_SILVER)].astype(SCHEMA_SILVER).reset_index(drop=True)


def transformar(categoria: str, data: str, run_id: str) -> Path | None:
    origem = particao(BRONZE_DIR, categoria, data) / "produtos.parquet"
    if not origem.exists():
        logger.warning("[silver] bronze inexistente: %s", origem)
        return None

    df = transform(pd.read_parquet(origem), run_id)
    output = particao(SILVER_DIR, categoria, data) / "produtos.parquet"
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output, index=False, engine="pyarrow")
    logger.info("[silver] %s %s | %d registros -> %s", categoria, data, len(df), output)
    return output
