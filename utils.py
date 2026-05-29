from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Locator, Page, TimeoutError as PlaywrightTimeoutError

import config


def normalizar_texto(texto: str | None) -> str:
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(ch for ch in texto if not unicodedata.combining(ch))
    texto = re.sub(r"\s+", " ", texto).strip().lower()
    return texto


def normalizar_cnpj(valor: Any) -> str:
    digitos = re.sub(r"\D", "", str(valor or ""))
    if not digitos:
        return ""
    return digitos.zfill(14)[-14:]


def formatar_cnpj(cnpj: str) -> str:
    cnpj = normalizar_cnpj(cnpj)
    return f"{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}" if len(cnpj) == 14 else cnpj


def hoje_competencia() -> str:
    hoje = date.today()
    return f"{hoje.month:02d}/{hoje.year}"


def diferenca_meses(comp_inicial: str, comp_final: str) -> int:
    mi, ai = map(int, re.findall(r"\d+", comp_inicial)[:2])
    mf, af = map(int, re.findall(r"\d+", comp_final)[:2])
    return (af - ai) * 12 + (mf - mi)


def extrair_mm_aaaa(texto: str) -> str:
    m = re.search(r"(0[1-9]|1[0-2])/(20\d{2})", texto or "")
    return m.group(0) if m else ""


def extrair_data(texto: str) -> str:
    m = re.search(r"\b\d{2}/\d{2}/\d{4}\b", texto or "")
    return m.group(0) if m else ""


def extrair_moeda(texto: str) -> str:
    m = re.search(r"(?:R\$|BRL)?\s*[-+]?\d{1,3}(?:\.\d{3})*,\d{2}", texto or "")
    return m.group(0).strip() if m else ""


def moeda_para_float(valor: str) -> float:
    if not valor:
        return 0.0
    limpo = re.sub(r"[^0-9,.-]", "", valor)
    if "," in limpo:
        limpo = limpo.replace(".", "").replace(",", ".")
    try:
        return float(limpo)
    except ValueError:
        return 0.0


def is_status_inativo(status: str) -> bool:
    s = normalizar_texto(status)
    return any(x in s for x in config.STATUS_INATIVOS)


def is_status_ativo(status: str) -> bool:
    s = normalizar_texto(status)
    return any(x in s for x in config.STATUS_ATIVOS) and not is_status_inativo(status)


def aguardar(page: Page, ms: int = 500) -> None:
    page.wait_for_timeout(ms)


def locator_visivel(locator: Locator, timeout: int = 1000) -> bool:
    try:
        locator.first.wait_for(state="visible", timeout=timeout)
        return True
    except Exception:
        return False


def click_if_visible(locator: Locator, timeout: int = 1000) -> bool:
    try:
        locator.first.wait_for(state="visible", timeout=timeout)
        locator.first.click()
        return True
    except Exception:
        return False


def inner_text_safe(locator: Locator, timeout: int = 1000) -> str:
    try:
        locator.first.wait_for(state="attached", timeout=timeout)
        return locator.first.inner_text(timeout=timeout).strip()
    except Exception:
        return ""


def page_text(page: Page) -> str:
    try:
        return page.locator("body").inner_text(timeout=3000)
    except Exception:
        return ""


def pause_manual(mensagem: str) -> None:
    print("\n" + "=" * 80)
    print(mensagem)
    print("=" * 80)
    input("Quando terminar na tela, pressione ENTER aqui para continuar...")


def extrair_valor_por_rotulo_texto(texto: str, rotulos: list[str]) -> str:
    """Extrai valor em páginas antigas em que label e valor aparecem em linhas próximas."""
    if not texto:
        return ""
    linhas = [ln.strip() for ln in texto.splitlines() if ln.strip()]
    linhas_norm = [normalizar_texto(ln).rstrip(":") for ln in linhas]
    for rotulo in rotulos:
        rn = normalizar_texto(rotulo).rstrip(":")
        for i, ln in enumerate(linhas_norm):
            if ln == rn or ln.startswith(rn + ":"):
                original = linhas[i]
                if ":" in original:
                    depois = original.split(":", 1)[1].strip()
                    if depois:
                        return depois
                for j in range(i + 1, min(i + 4, len(linhas))):
                    prox = linhas[j].strip()
                    if prox and normalizar_texto(prox).rstrip(":") not in linhas_norm[:i+1]:
                        return prox
    return ""


def tabelas_html_para_linhas(page: Page) -> list[list[list[str]]]:
    """Retorna todas as tabelas como listas de linhas/células."""
    return page.evaluate(
        """
        () => Array.from(document.querySelectorAll('table')).map(tbl =>
            Array.from(tbl.querySelectorAll('tr')).map(tr =>
                Array.from(tr.querySelectorAll('th,td')).map(td => (td.innerText || '').trim())
            ).filter(r => r.length)
        )
        """
    )


def localizar_tabela_por_cabecalho(page: Page, cabecalhos: list[str]) -> list[list[str]]:
    alvo = [normalizar_texto(x) for x in cabecalhos]
    for tabela in tabelas_html_para_linhas(page):
        if not tabela:
            continue
        header = [normalizar_texto(c) for c in tabela[0]]
        if all(any(a in h for h in header) for a in alvo):
            return tabela
    return []


def linhas_com_header(tabela: list[list[str]]) -> list[dict[str, str]]:
    if not tabela or len(tabela) < 2:
        return []
    header = [re.sub(r"\s+", " ", h).strip() for h in tabela[0]]
    linhas = []
    for row in tabela[1:]:
        d: dict[str, str] = {}
        for idx, h in enumerate(header):
            d[h] = row[idx].strip() if idx < len(row) else ""
        if any(d.values()):
            linhas.append(d)
    return linhas


def salvar_debug_html(page: Page, nome: str) -> str:
    path = config.OUTPUT_DIR / f"{nome}.html"
    try:
        path.write_text(page.content(), encoding="utf-8")
        return str(path)
    except Exception:
        return ""


def snapshot(page: Page, nome: str) -> str:
    path = config.OUTPUT_DIR / f"{nome}.png"
    try:
        page.screenshot(path=str(path), full_page=True)
        return str(path)
    except Exception:
        return ""
