"""
Cartas SVG da vitrine do Power BI. O Power BI não carrega imagens externas dentro de um SVG,
por isso a miniatura vai embutida em base64 e a carta inteira vira um data URI (ImageUrl).
"""
import base64
import io
import logging
import re
from html import escape, unescape
from urllib.parse import quote

import duckdb
import requests
from PIL import Image

from src.observabilidade import agora_utc

logger = logging.getLogger(__name__)

LARGURA, ALTURA = 220, 300
LIMITE_URI = 30_000  # o Power BI trunca textos de imagem acima de ~32 mil caracteres
TAMANHO_MINIATURA = "_AC_SX300_"
# ASCII imprimível exceto % e # (que têm significado em URI); o resto é percent-encoded
SEGUROS_URI = "".join(c for c in map(chr, range(32, 127)) if c not in "%#")


def url_miniatura(url: str) -> str:
    """https://.../I/41NIiIKbCgL._AC_UL960_QL65_.jpg -> https://.../I/41NIiIKbCgL._AC_SX300_.jpg"""
    return re.sub(r"\._[^/]*_\.(jpg|jpeg|png)$", rf".{TAMANHO_MINIATURA}.\1", url)


def reduzir_imagem(conteudo: bytes, caixa: tuple[int, int] = (300, 250), qualidade: int = 72) -> bytes:
    """Caixa com 2x a área exibida, para a imagem ficar nítida."""
    img = Image.open(io.BytesIO(conteudo))
    if img.mode != "RGB":  # PNG com transparência -> fundo branco
        fundo = Image.new("RGB", img.size, "white")
        fundo.paste(img, mask=img.convert("RGBA").split()[-1])
        img = fundo
    img.thumbnail(caixa)
    saida = io.BytesIO()
    img.save(saida, "JPEG", quality=qualidade, optimize=True)
    return saida.getvalue()


def baixar_imagens(con: duckdb.DuckDBPyConnection) -> int:
    con.execute("""
        CREATE TABLE IF NOT EXISTS silver.imagens (
            codigo_produto VARCHAR PRIMARY KEY,
            url_imagem     VARCHAR,
            mime           VARCHAR,
            imagem_base64  VARCHAR,
            bytes          INTEGER,
            baixado_em     TIMESTAMPTZ
        )
    """)
    # compara só com a URL mais recente: a foto muda entre extrações e, comparando com
    # todas, os mesmos produtos seriam baixados de novo em toda execução
    pendentes = con.execute("""
        WITH atual AS (
            SELECT DISTINCT ON (codigo_produto) codigo_produto, url_imagem
            FROM silver.produtos
            WHERE url_imagem IS NOT NULL
            ORDER BY codigo_produto, data_extracao DESC
        )
        SELECT a.codigo_produto, a.url_imagem
        FROM atual a
        LEFT JOIN silver.imagens i USING (codigo_produto)
        WHERE i.codigo_produto IS NULL OR i.url_imagem <> a.url_imagem
    """).fetchall()

    baixadas = 0
    with requests.Session() as s:
        for codigo, url in pendentes:
            try:
                r = s.get(url_miniatura(url), timeout=15)
                r.raise_for_status()
            except requests.RequestException as e:
                logger.warning("[imagens] falha em %s: %s", codigo, e)
                continue
            imagem = reduzir_imagem(r.content)
            con.execute(
                "INSERT OR REPLACE INTO silver.imagens VALUES (?, ?, ?, ?, ?, ?)",
                [codigo, url, "image/jpeg", base64.b64encode(imagem).decode(), len(imagem), agora_utc()],
            )
            baixadas += 1
    logger.info("[imagens] %d baixadas, %d pendentes", baixadas, len(pendentes))
    return baixadas


def _brl(valor: float) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _quebrar_titulo(titulo: str, por_linha: int = 30, linhas: int = 2) -> list[str]:
    palavras, saida, atual = titulo.split(), [], ""
    for p in palavras:
        if len(atual) + len(p) + 1 > por_linha and atual:
            saida.append(atual)
            atual = p
        else:
            atual = f"{atual} {p}".strip()
    saida.append(atual)
    if len(saida) > linhas:
        saida = saida[:linhas]
        saida[-1] = saida[-1][: por_linha - 1].rstrip() + "…"
    return saida


def montar_card(p: dict, com_imagem: bool = True) -> str:
    t = 'font-family="Segoe UI, Calibri, sans-serif"'
    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{LARGURA}" height="{ALTURA}" viewBox="0 0 {LARGURA} {ALTURA}">',
        # fundo opaco: o Power BI pinta de preto as áreas transparentes da imagem
        f'<rect width="{LARGURA}" height="{ALTURA}" fill="rgb(250,250,252)"/>',
        f'<rect x="4" y="4" width="{LARGURA - 8}" height="{ALTURA - 8}" rx="12" fill="white" stroke="rgb(220,225,230)"/>',
    ]
    if com_imagem and p["imagem_base64"]:
        partes.append(
            f'<image x="22" y="16" width="{LARGURA - 44}" height="150" preserveAspectRatio="xMidYMid meet" '
            f'href="data:{p["mime"]};base64,{p["imagem_base64"]}"/>'
        )
    else:
        partes.append(f'<rect x="22" y="16" width="{LARGURA - 44}" height="150" rx="8" fill="rgb(240,241,244)"/>')

    if p["desconto_pct"]:
        partes.append('<rect x="14" y="14" width="50" height="22" rx="11" fill="rgb(192,91,91)"/>')
        partes.append(f'<text x="39" y="29.5" {t} font-size="11" font-weight="700" fill="white" '
                      f'text-anchor="middle">-{p["desconto_pct"]:.0f}%</text>')

    for i, linha in enumerate(_quebrar_titulo(unescape(p["titulo_produto"] or ""))):
        partes.append(f'<text x="18" y="{190 + i * 16}" {t} font-size="12" fill="rgb(48,70,95)">{escape(linha)}</text>')

    partes.append(f'<line x1="18" y1="220" x2="{LARGURA - 18}" y2="220" stroke="rgb(225,231,236)"/>')

    if p["preco_original"]:
        partes.append(f'<text x="18" y="240" {t} font-size="11" fill="rgb(132,142,153)" '
                      f'text-decoration="line-through">{_brl(p["preco_original"])}</text>')
    if p["preco"] is not None:
        partes.append(f'<text x="18" y="268" {t} font-size="20" font-weight="700" fill="rgb(48,70,95)">{_brl(p["preco"])}</text>')

    if p["avaliacao_media"] is not None:
        nota = f'{p["avaliacao_media"]:.1f}'.replace(".", ",")
        partes.append(f'<text x="{LARGURA - 18}" y="252" {t} font-size="14" font-weight="700" fill="rgb(181,149,37)" '
                      f'text-anchor="end">★ {nota}</text>')
    if p["quantidade_avaliacoes"]:
        qtd = f'{p["quantidade_avaliacoes"]:,}'.replace(",", ".")
        partes.append(f'<text x="{LARGURA - 18}" y="268" {t} font-size="10" fill="rgb(132,142,153)" '
                      f'text-anchor="end">({qtd})</text>')

    partes.append("</svg>")
    # SVG como texto (base64 incharia 33%). Um '%' sem escape (ex.: selo "-74%") quebra a
    # decodificação da URI e corta o resto da carta
    return "data:image/svg+xml;utf8," + quote("".join(partes), safe=SEGUROS_URI)


def gerar_cards(con: duckdb.DuckDBPyConnection) -> int:
    """Uma carta por produto e data, reaproveitada nas três ordenações."""
    df = con.execute("SELECT * FROM gold.vitrine ORDER BY data, ordem_ordenacao, categoria, posicao").df()
    df = df.astype(object).where(df.notna(), None)
    cache, linhas = {}, []
    for p in df.to_dict("records"):
        chave = (p["codigo_produto"], p["data"])
        if chave not in cache:
            card = montar_card(p)
            if len(card) > LIMITE_URI:
                logger.warning("[vitrine] card de %s grande demais (%d), sem imagem", p["codigo_produto"], len(card))
                card = montar_card(p, com_imagem=False)
            cache[chave] = card
        linhas.append((p["data"], p["ordenacao"], p["ordem_ordenacao"], p["codigo_produto"], p["categoria"],
                       p["posicao"], p["linha"], p["coluna"], cache[chave]))

    con.execute("""
        CREATE OR REPLACE TABLE gold.vitrine_cards (
            data DATE, ordenacao VARCHAR, ordem_ordenacao INTEGER, codigo_produto VARCHAR, categoria VARCHAR,
            posicao INTEGER, linha INTEGER, coluna INTEGER, card_svg VARCHAR
        )
    """)
    con.executemany("INSERT INTO gold.vitrine_cards VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)", linhas)
    logger.info("[vitrine] %d cartas, %d posições na grade", len(cache), len(linhas))
    return len(cache)
