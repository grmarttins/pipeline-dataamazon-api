-- Duração de cada etapa por execução do pipeline (base: ops.execucoes)
CREATE OR REPLACE VIEW gold.duracao_etapas AS
SELECT
    run_id,
    min(inicio) OVER (PARTITION BY run_id)  AS inicio_execucao,
    etapa,
    categoria,
    data,
    inicio,
    fim,
    duracao_s,
    registros,
    round(registros / nullif(duracao_s, 0)) AS registros_por_s,
    status,
    erro
FROM ops.execucoes;
