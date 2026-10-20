"""
    python main.py                 # extrai hoje e processa todas as camadas
    python main.py --pages 3       # extrai 3 páginas por categoria
    python main.py --reprocessar   # sem chamar a API: refaz silver e banco a partir da bronze
"""
import argparse
import logging
from datetime import date

from src.config import BRONZE_DIR, CATEGORIAS, listar_particoes
from src.extract import extrair
from src.ingest import ingerir
from src.load import carregar
from src.observabilidade import contar_linhas, etapa, novo_run_id
from src.transform import transformar

logger = logging.getLogger(__name__)


def processar(run_id: str, categoria: str, data: str, processadas: list) -> None:
    with etapa(run_id, "transform", categoria, data) as info:
        silver = transformar(categoria, data, run_id)
        info["registros"] = contar_linhas(silver)
    if silver:
        processadas.append((categoria, data))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--delay", type=float, default=3.0)
    parser.add_argument("--reprocessar", action="store_true")
    args = parser.parse_args()

    run_id = novo_run_id()
    logger.info("run_id: %s", run_id)

    with etapa(run_id, "pipeline"):
        processadas = []
        if args.reprocessar:
            for categoria, data in listar_particoes(BRONZE_DIR):
                processar(run_id, categoria, data, processadas)
        else:
            hoje = date.today().isoformat()
            for categoria in CATEGORIAS:
                with etapa(run_id, "extract", categoria, hoje) as info:
                    paginas = extrair(categoria, hoje, run_id, pages=args.pages, delay=args.delay)
                    info["registros"] = len(paginas)
                if not paginas:
                    continue
                with etapa(run_id, "ingest", categoria, hoje) as info:
                    info["registros"] = contar_linhas(ingerir(categoria, hoje, run_id))
                processar(run_id, categoria, hoje, processadas)

        carregar(processadas, run_id)


if __name__ == "__main__":
    main()
