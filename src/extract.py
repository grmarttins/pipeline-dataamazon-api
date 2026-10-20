"""API -> raw: grava a resposta da API exatamente como veio, um arquivo por página."""
import json
import logging
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import CATEGORIAS, ENV_PATH, RAW_DIR, particao

logger = logging.getLogger(__name__)
load_dotenv(ENV_PATH)

BASE_URL = "https://real-time-amazon-data.p.rapidapi.com/products-by-category"


# Exceções
class APIKeyError(Exception):
    """Chave da API ausente ou inválida"""

class APIRateLimitError(Exception):
    """Limite de requisições excedido (429)"""

class APIResponseError(Exception):
    """Erro de resposta da API"""


def acessar_chave_api() -> dict:
    api_key = os.getenv("API_KEY")
    if not api_key:
        raise APIKeyError("API_KEY não encontrada no .env.")
    return {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": "real-time-amazon-data.p.rapidapi.com",
    }


@retry(  # type: ignore[call-overload]
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=5, max=60),
    retry=retry_if_exception_type((APIRateLimitError, APIResponseError, requests.Timeout)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def _fazer_request(params: dict, timeout: int = 20) -> dict:
    response = requests.get(BASE_URL, headers=acessar_chave_api(), params=params, timeout=timeout)

    if response.status_code == 429:
        logger.warning("Rate limit atingido. Tenacity fará o backoff.")
        raise APIRateLimitError("Rate limit 429")

    if response.status_code in (401, 403):
        raise APIKeyError(f"Chave inválida ou sem permissão ({response.status_code})")

    if response.status_code >= 500:
        raise APIResponseError(f"Erro no servidor: {response.status_code}")

    if response.status_code != 200:
        raise APIResponseError(f"Status inesperado: {response.status_code}")

    try:
        return response.json()
    except json.JSONDecodeError as e:
        raise APIResponseError(f"Resposta não é JSON válido: {e}") from e


def extrair_pagina(categoria: str, page: int) -> dict:
    categoria_id, _ = CATEGORIAS[categoria]
    params = {
        "category_id": categoria_id,
        "page": str(page),
        "country": "BR",
        "sort_by": "RELEVANCE",
        "product_condition": "ALL",
        "is_prime": "false",
        "deals_and_discounts": "NONE",
    }
    return _fazer_request(params)


def salvar_raw(resposta: dict, categoria: str, data: str, page: int) -> Path:
    output = particao(RAW_DIR, categoria, data) / f"page_{page}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(resposta, f, indent=2, ensure_ascii=False)
    return output


def extrair(categoria: str, data: str, pages: int = 1, delay: float = 3.0) -> list[Path]:
    arquivos = []
    for page in range(1, pages + 1):
        try:
            resposta = extrair_pagina(categoria, page)
        except APIKeyError:
            logger.error("Chave inválida — abortando.")
            raise
        except (APIRateLimitError, APIResponseError, requests.Timeout) as e:
            logger.error("Falha após retries na página %d: %s", page, e)
            continue

        arquivo = salvar_raw(resposta, categoria, data, page)
        n = len(resposta.get("data", {}).get("products", []))
        logger.info("[raw] %s página %d | %d produtos -> %s", categoria, page, n, arquivo)
        arquivos.append(arquivo)
        time.sleep(delay)

    return arquivos
