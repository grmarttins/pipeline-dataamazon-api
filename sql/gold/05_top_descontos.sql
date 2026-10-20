-- Top 20 maiores descontos de cada dia
CREATE OR REPLACE TABLE gold.top_descontos AS
SELECT
    f.data,
    row_number() OVER (PARTITION BY f.data ORDER BY f.desconto_pct DESC) AS posicao,
    f.codigo_produto,
    d.titulo_produto,
    f.categoria,
    f.preco,
    f.preco_original,
    f.desconto_pct,
    f.avaliacao_media
FROM gold.fato_preco_diario f
JOIN gold.dim_produto d USING (codigo_produto)
WHERE f.desconto_pct IS NOT NULL
QUALIFY posicao <= 20;
