import logging
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pyarrow.parquet as pq

from src.config import WAREHOUSE_PATH

logger = logging.getLogger(__name__)

DDL_EXECUCOES = """
    CREATE SCHEMA IF NOT EXISTS ops;
    CREATE TABLE IF NOT EXISTS ops.execucoes (
        run_id      VARCHAR,
        etapa       VARCHAR,
        categoria   VARCHAR,
        data        DATE,
        inicio      TIMESTAMPTZ,
        fim         TIMESTAMPTZ,
        duracao_s   DOUBLE,
        registros   BIGINT,
        status      VARCHAR,
        erro        VARCHAR
    );
"""


def agora_utc() -> datetime:
    return datetime.now(timezone.utc)


def novo_run_id() -> str:
    """Ex.: 20261020T210001Z-3f9a1c (ordenável por tempo e único)."""
    return f"{agora_utc():%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:6]}"


def contar_linhas(parquet: Path | None) -> int | None:
    return pq.read_metadata(parquet).num_rows if parquet else None


def _registrar(linha: dict) -> None:
    WAREHOUSE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(WAREHOUSE_PATH)) as con:
        con.execute(DDL_EXECUCOES)
        con.execute(
            "INSERT INTO ops.execucoes VALUES ($run_id, $etapa, $categoria, $data, $inicio, $fim, "
            "$duracao_s, $registros, $status, $erro)",
            linha,
        )


@contextmanager
def etapa(run_id: str, nome: str, categoria: str | None = None, data: str | None = None):
    """Mede a etapa e grava em ops.execucoes, mesmo se falhar. Preencha info["registros"] no bloco."""
    info = {"registros": None}
    inicio, t0 = agora_utc(), time.perf_counter()
    status, erro = "ok", None
    try:
        yield info
    except Exception as e:
        status, erro = "erro", f"{type(e).__name__}: {e}"
        raise
    finally:
        duracao = round(time.perf_counter() - t0, 3)
        _registrar({
            "run_id": run_id, "etapa": nome, "categoria": categoria, "data": data,
            "inicio": inicio, "fim": agora_utc(), "duracao_s": duracao,
            "registros": info["registros"], "status": status, "erro": erro,
        })
        logger.info("[ops] %s %s %s | %s | %.3fs | %s registros",
                    nome, categoria or "", data or "", status, duracao, info["registros"])
