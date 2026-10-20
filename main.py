"""
Pipeline: API -> raw -> bronze -> silver -> gold

    python main.py                 # extrai hoje (todas as categorias) e processa
    python main.py --pages 3       # extrai 3 páginas por categoria
    python main.py --reprocessar   # não chama a API; refaz silver/gold de todas as partições bronze
"""
import argparse
from datetime import date

from src.aggregate import agregar
from src.config import BRONZE_DIR, CATEGORIAS, listar_particoes
from src.extract import extrair
from src.ingest import ingerir
from src.transform import transformar


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--delay", type=float, default=3.0)
    parser.add_argument("--reprocessar", action="store_true")
    args = parser.parse_args()

    if args.reprocessar:
        for categoria, data in listar_particoes(BRONZE_DIR):
            transformar(categoria, data)
    else:
        hoje = date.today().isoformat()
        for categoria in CATEGORIAS:
            if extrair(categoria, hoje, pages=args.pages, delay=args.delay):
                ingerir(categoria, hoje)
                transformar(categoria, hoje)

    agregar()


if __name__ == "__main__":
    main()
