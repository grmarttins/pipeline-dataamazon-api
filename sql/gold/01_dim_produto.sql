-- Dimensão de produto: atributos mais recentes de cada produto (1 linha por codigo_produto)
CREATE OR REPLACE TABLE gold.dim_produto AS
SELECT
    codigo_produto,
    titulo_produto,
    categoria,
    plataforma,
    url_produto,
    url_imagem,
    CAST(data_extracao AS DATE) AS ultima_extracao
FROM silver.produtos
QUALIFY row_number() OVER (PARTITION BY codigo_produto ORDER BY data_extracao DESC) = 1;
