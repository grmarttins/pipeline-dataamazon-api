-- Resumo por categoria, dia e faixa de preço
CREATE OR REPLACE TABLE gold.resumo_por_faixa AS
SELECT
    categoria,
    data,
    faixa_preco,
    count(*)                                AS qtd_produtos,
    round(avg(preco), 2)                    AS preco_medio,
    round(avg(desconto_pct), 2)             AS desconto_medio_pct,
    round(avg(CAST(tem_desconto AS INT)), 2) AS pct_com_desconto,
    round(avg(avaliacao_media), 2)          AS avaliacao_media
FROM gold.fato_preco_diario
GROUP BY categoria, data, faixa_preco;
