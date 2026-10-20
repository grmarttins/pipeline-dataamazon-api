-- Saúde do pipeline por partição: frescor dos dados e latência entre camadas.
-- É VIEW (não tabela) para o frescor ser calculado no momento da consulta.
CREATE OR REPLACE VIEW gold.saude_pipeline AS
SELECT
    categoria_slug                                          AS categoria,
    CAST(data_extracao AS DATE)                             AS data,
    count(*)                                                AS registros,
    max(extraido_em)                                        AS extraido_em,
    max(ingerido_em)                                        AS ingerido_em,
    max(processado_em)                                      AS processado_em,
    max(carregado_em)                                       AS carregado_em,
    round(epoch(max(ingerido_em)   - max(extraido_em)), 1)  AS latencia_ingestao_s,
    round(epoch(max(processado_em) - max(ingerido_em)), 1)  AS latencia_processamento_s,
    round(epoch(max(carregado_em)  - max(processado_em)), 1) AS latencia_carga_s,
    round(epoch(max(carregado_em)  - max(extraido_em)), 1)  AS latencia_total_s,
    round(epoch(now() - max(extraido_em)) / 3600, 1)        AS frescor_horas,
    any_value(run_id)                                       AS ultimo_run_id
FROM silver.produtos
GROUP BY ALL;
