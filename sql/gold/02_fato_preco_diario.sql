-- Fato: métricas de cada produto em cada dia de extração (1 linha por codigo_produto + data)
CREATE OR REPLACE TABLE gold.fato_preco_diario AS
SELECT
    codigo_produto,
    CAST(data_extracao AS DATE) AS data,
    categoria,
    faixa_preco,
    preco,
    preco_original,
    preco_minimo_oferta,
    desconto_pct,
    tem_desconto,
    avaliacao_media,
    quantidade_avaliacoes,
    quantidade_ofertas,
    volume_vendas_estimado,
    prime,
    mais_vendido,
    escolha_amazon,
    entrega_gratis
FROM silver.produtos;
