-- Dimensão de produto: atributos mais recentes de cada produto (1 linha por codigo_produto)
-- + em quantas extrações ele apareceu (para filtrar quem tem histórico para comparar)
CREATE OR REPLACE TABLE gold.dim_produto AS
SELECT
    codigo_produto,
    titulo_produto,
    categoria,
    plataforma,
    url_produto,
    url_imagem,
    CAST(data_extracao AS DATE) AS ultima_extracao,
    count(DISTINCT data_extracao) OVER (PARTITION BY codigo_produto) AS qtd_extracoes,
    CASE WHEN count(DISTINCT data_extracao) OVER (PARTITION BY codigo_produto) > 1
         THEN 'Com comparação' ELSE 'Só 1 extração' END AS comparacao
FROM silver.produtos
QUALIFY row_number() OVER (PARTITION BY codigo_produto ORDER BY data_extracao DESC) = 1;
