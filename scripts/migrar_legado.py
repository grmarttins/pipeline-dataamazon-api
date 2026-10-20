"""
Migração única: os JSONs antigos (data/bronze/Eletrônicos_AAAA-MM-DD.json) já vinham
enriquecidos, então entram direto como bronze na estrutura nova. Os originais e a silver
antiga são movidos para data/_legado/ (nada é apagado).

    python scripts/migrar_legado.py
"""
import json
import re
import shutil
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import BRONZE_DIR, CATEGORIAS, DATA_DIR, SILVER_DIR  # noqa: E402
from src.ingest import salvar_bronze  # noqa: E402

LEGADO_DIR = DATA_DIR / "_legado"
NOME_PARA_SLUG = {nome: slug for slug, (_, nome) in CATEGORIAS.items()}


def main():
    LEGADO_DIR.mkdir(parents=True, exist_ok=True)

    for arquivo in sorted(BRONZE_DIR.glob("*.json")):
        m = re.fullmatch(r"(.+)_(\d{4}-\d{2}-\d{2})", arquivo.stem)
        if not m or m.group(1) not in NOME_PARA_SLUG:
            print(f"ignorado: {arquivo.name}")
            continue
        categoria, data = NOME_PARA_SLUG[m.group(1)], m.group(2)

        with open(arquivo, encoding="utf-8") as f:
            df = pd.DataFrame(json.load(f))
        df = df.drop(columns=["_categoria_nome"], errors="ignore")
        # o legado gravava a hora da extração em horário local, sem fuso -> converte para UTC
        df["_extraido_em"] = (
            pd.to_datetime(df["_data_extracao"]).dt.tz_localize("America/Sao_Paulo").dt.tz_convert("UTC")
            .map(lambda t: t.isoformat())
        )
        df["_categoria"] = categoria
        df["_data_extracao"] = data
        df["_arquivo_origem"] = f"_legado/{arquivo.name}"
        df["_ingerido_em"] = None
        df["_run_id"] = "legado"

        salvar_bronze(df, categoria, data)
        shutil.move(arquivo, LEGADO_DIR / arquivo.name)

    for pasta in SILVER_DIR.glob("data_extracao=*"):
        shutil.move(pasta, LEGADO_DIR / f"silver_{pasta.name}")


if __name__ == "__main__":
    main()
