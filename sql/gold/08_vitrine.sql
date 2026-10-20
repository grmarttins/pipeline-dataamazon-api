-- Posições de grade (5 por linha) pré-calculadas para cada (data, ordenação, categoria):
-- a matriz do Power BI não fica com buracos ao trocar filtro ou ordenação.
CREATE OR REPLACE TABLE gold.vitrine AS
WITH ordenacoes(ordenacao, ordem_ordenacao) AS (
    VALUES ('Maior desconto', 1), ('Maior preço', 2), ('Menor preço', 3)
),
ranqueado AS (
    SELECT
        o.ordenacao,
        o.ordem_ordenacao,
        u.categoria,
        u.codigo_produto,
        u.titulo_produto,
        u.preco,
        u.preco_original,
        u.desconto_pct,
        u.avaliacao_media,
        u.quantidade_avaliacoes,
        u.url_produto,
        CAST(u.data_extracao AS DATE) AS data,
        i.mime,
        i.imagem_base64,
        row_number() OVER (
            PARTITION BY u.data_extracao, o.ordenacao, u.categoria
            ORDER BY
                CASE o.ordenacao WHEN 'Maior desconto' THEN -coalesce(u.desconto_pct, -1)
                                 WHEN 'Maior preço'    THEN -u.preco
                                 ELSE u.preco END NULLS LAST,
                u.quantidade_avaliacoes DESC NULLS LAST,
                u.codigo_produto
        ) AS posicao
    FROM silver.produtos u
    CROSS JOIN ordenacoes o
    LEFT JOIN silver.imagens i USING (codigo_produto)
)
SELECT
    *,
    (posicao - 1) // 5 + 1 AS linha,
    (posicao - 1) % 5 + 1  AS coluna
FROM ranqueado;
