import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / "config" / ".env"

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
BRONZE_DIR = DATA_DIR / "bronze"
SILVER_DIR = DATA_DIR / "silver"
WAREHOUSE_PATH = DATA_DIR / "warehouse.duckdb"

# slug usado nas pastas -> (id da categoria na Amazon, nome de exibição)
CATEGORIAS = {
    "eletronicos": ("204547342011", "Eletrônicos"),
    # "informatica": ("16209062011", "Informática"),
    # "acessorios":  ("16209067011", "Acessórios"),
    # "casa":        ("16225007011", "Casa"),
    # "livros":      ("20169275011", "Livros"),
    # "esportes":    ("17264859011", "Esportes"),
}


def particao(camada_dir: Path, categoria: str, data: str) -> Path:
    """Pasta particionada estilo Hive: <camada>/categoria=<slug>/data_extracao=<AAAA-MM-DD>"""
    return camada_dir / f"categoria={categoria}" / f"data_extracao={data}"


def listar_particoes(camada_dir: Path) -> list[tuple[str, str]]:
    particoes = []
    for pasta in sorted(camada_dir.glob("categoria=*/data_extracao=*")):
        categoria = pasta.parent.name.split("=", 1)[1]
        data = pasta.name.split("=", 1)[1]
        particoes.append((categoria, data))
    return particoes
