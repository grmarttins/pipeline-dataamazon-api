"""
Todas as tasks escrevem no DuckDB (ao menos em ops.execucoes), que aceita um único processo
escrevendo por vez. O pool "duckdb" (1 vaga) serializa esse acesso; o mapeamento por
categoria continua declarado.
"""
import re
from datetime import timedelta

import pendulum
from airflow.sdk import dag, task

from src.config import BRONZE_DIR, CATEGORIAS, listar_particoes
from src.observabilidade import contar_linhas, etapa

FUSO = pendulum.timezone("America/Sao_Paulo")
PADRAO = {"owner": "dataeng", "retries": 1, "retry_delay": timedelta(minutes=5), "pool": "duckdb"}


def _run_id(context) -> str:
    return re.sub(r"[^A-Za-z0-9T_-]", "", context["run_id"])[:60]


def _hoje() -> str:
    return pendulum.now(FUSO).to_date_string()


@task
def extrair(categoria: str, **context) -> dict | None:
    from src.extract import extrair as extrair_api

    run_id, data = _run_id(context), _hoje()
    with etapa(run_id, "extract", categoria, data) as info:
        paginas = extrair_api(categoria, data, run_id, pages=1, delay=3.0)
        info["registros"] = len(paginas)
    return {"categoria": categoria, "data": data} if paginas else None


@task
def ingerir(particao: dict | None, **context) -> dict | None:
    from src.ingest import ingerir as ingerir_raw

    if not particao:
        return None
    with etapa(_run_id(context), "ingest", particao["categoria"], particao["data"]) as info:
        info["registros"] = contar_linhas(ingerir_raw(particao["categoria"], particao["data"], _run_id(context)))
    return particao


@task
def transformar(particao: dict | None, **context) -> dict | None:
    from src.transform import transformar as transformar_bronze

    if not particao:
        return None
    with etapa(_run_id(context), "transform", particao["categoria"], particao["data"]) as info:
        silver = transformar_bronze(particao["categoria"], particao["data"], _run_id(context))
        info["registros"] = contar_linhas(silver)
    return particao if silver else None


@task
def carregar(particoes: list[dict | None], **context) -> None:
    from src.load import carregar as carregar_warehouse

    validas = [(p["categoria"], p["data"]) for p in particoes if p]
    carregar_warehouse(validas, _run_id(context))


@task
def listar_bronze() -> list[dict]:
    return [{"categoria": c, "data": d} for c, d in listar_particoes(BRONZE_DIR)]


@dag(
    dag_id="pipeline_amazon_diario",
    description="Extrai produtos da API e atualiza todas as camadas",
    schedule="0 9 * * *",
    start_date=pendulum.datetime(2026, 10, 1, tz=FUSO),
    catchup=False,
    is_paused_upon_creation=True,  # cota baixa no plano free da API: disparo manual
    max_active_runs=1,
    default_args=PADRAO,
    tags=["amazon", "medallion", "duckdb"],
)
def pipeline_amazon_diario():
    particoes = transformar.expand(particao=ingerir.expand(particao=extrair.expand(categoria=list(CATEGORIAS))))
    carregar(particoes)


@dag(
    dag_id="pipeline_amazon_reprocessar",
    description="Refaz silver, banco e gold a partir da bronze, sem chamar a API",
    schedule=None,
    start_date=pendulum.datetime(2026, 10, 1, tz=FUSO),
    catchup=False,
    max_active_runs=1,
    default_args={**PADRAO, "retries": 0},
    tags=["amazon", "medallion", "duckdb", "reprocessamento"],
)
def pipeline_amazon_reprocessar():
    carregar(transformar.expand(particao=listar_bronze()))


pipeline_amazon_diario()
pipeline_amazon_reprocessar()
