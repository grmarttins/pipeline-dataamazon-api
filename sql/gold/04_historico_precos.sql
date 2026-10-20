CREATE OR REPLACE TABLE gold.historico_precos AS
SELECT
    codigo_produto,
    data,
    preco,
    lag(preco) OVER w                       AS preco_anterior,
    round(preco - lag(preco) OVER w, 2)     AS variacao,
    round((preco / lag(preco) OVER w - 1) * 100, 1) AS variacao_pct
FROM gold.fato_preco_diario
WINDOW w AS (PARTITION BY codigo_produto ORDER BY data);
