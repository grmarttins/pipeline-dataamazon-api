-- Vitrine: cada produto em cada data de extração, posicionado em grade (5 cartas por linha)
-- para cada ordenação do Power BI. Cada (data, ordenação, categoria) tem a própria linha/coluna,
-- assim a grade nunca fica com buracos e o filtro de data troca a grade inteira.
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
