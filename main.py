"""
Pipeline: API -> raw -> bronze -> silver -> DuckDB (silver.produtos + gold.*)

    python main.py                 # extrai hoje (todas as categorias) e processa
    python main.py --pages 3       # extrai 3 páginas por categoria
    python main.py --reprocessar   # não chama a API; refaz silver e banco a partir de toda a bronze
"""
import argparse
from datetime import date

from src.config import BRONZE_DIR, CATEGORIAS, listar_particoes
from src.extract import extrair
from src.ingest import ingerir
from src.load import carregar
from src.transform import transformar


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--delay", type=float, default=3.0)
    parser.add_argument("--reprocessar", action="store_true")
    args = parser.parse_args()

    processadas = []
    if args.reprocessar:
        for categoria, data in listar_particoes(BRONZE_DIR):
            if transformar(categoria, data):
                processadas.append((categoria, data))
    else:
        hoje = date.today().isoformat()
        for categoria in CATEGORIAS:
            if extrair(categoria, hoje, pages=args.pages, delay=args.delay):
                ingerir(categoria, hoje)
                if transformar(categoria, hoje):
                    processadas.append((categoria, hoje))

    carregar(processadas)


if __name__ == "__main__":
    main()
