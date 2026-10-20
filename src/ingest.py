"""raw -> bronze: achata os produtos em tabela, adiciona metadados de ingestão. Sem limpeza."""
import json
import logging
from pathlib import Path

import pandas as pd

from src.config import BRONZE_DIR, CATEGORIAS, RAW_DIR, particao
from src.observabilidade import agora_utc

logger = logging.getLogger(__name__)


def _para_texto(val) -> str | None:
    """Bronze guarda tudo como texto; listas/dicts viram JSON."""
    if isinstance(val, (dict, list)):
        return json.dumps(val, ensure_ascii=False)
    if pd.isna(val):
        return None
    return str(val)


def salvar_bronze(df: pd.DataFrame, categoria: str, data: str) -> Path:
    df = df.map(_para_texto).astype("string")
    output = particao(BRONZE_DIR, categoria, data) / "produtos.parquet"
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output, index=False, engine="pyarrow")
    logger.info("[bronze] %s %s | %d registros -> %s", categoria, data, len(df), output)
    return output


def ingerir(categoria: str, data: str, run_id: str) -> Path | None:
    pasta = particao(RAW_DIR, categoria, data)
    arquivos = sorted(a for a in pasta.glob("page_*.json") if not a.name.endswith(".meta.json"))
    if not arquivos:
        logger.warning("[bronze] nenhum arquivo raw para %s %s", categoria, data)
        return None

    categoria_id, _ = CATEGORIAS[categoria]
    ingerido_em = agora_utc().isoformat()
    linhas = []
    for arquivo in arquivos:
        with open(arquivo, encoding="utf-8") as f:
            resposta = json.load(f)
        meta_path = arquivo.with_suffix(".meta.json")
        meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
        pagina = int(arquivo.stem.removeprefix("page_"))
        for produto in resposta.get("data", {}).get("products", []):
            linhas.append({
                **produto,
                "_categoria": categoria,
                "_categoria_id": categoria_id,
                "_pagina": pagina,
                "_data_extracao": data,
                "_arquivo_origem": str(arquivo.relative_to(RAW_DIR)),
                "_extraido_em": meta.get("requisitado_em"),
                "_ingerido_em": ingerido_em,
                "_run_id": run_id,
            })

    return salvar_bronze(pd.DataFrame(linhas), categoria, data)
