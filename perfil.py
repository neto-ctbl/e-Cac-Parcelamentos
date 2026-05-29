from __future__ import annotations

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from ecac import ECAC
from utils import formatar_cnpj, locator_visivel, normalizar_cnpj, page_text, pause_manual


def alterar_perfil_cnpj(ecac: ECAC, cnpj: str) -> None:
    cnpj_limpo = normalizar_cnpj(cnpj)
    if len(cnpj_limpo) != 14:
        raise ValueError(f"CNPJ inválido: {cnpj}")

    ecac.garantir_aba_ecac()
    p = ecac.p
    ecac.relogar_se_expirado()

    print(f"[PERFIL] Alterando perfil para {formatar_cnpj(cnpj_limpo)}")

    btn = p.locator("text=Alterar perfil de acesso")
    btn.first.wait_for(state="visible", timeout=30000)
    btn.first.click()

    campo = p.locator("#txtNIPapel2")
    try:
        campo.wait_for(state="visible", timeout=15000)
    except PlaywrightTimeoutError:
        # Às vezes abre em modal/aba com atraso.
        raise RuntimeError("Campo de CNPJ do perfil PJ não apareceu.")

    campo.fill(cnpj_limpo)
    p.locator("#formPJ input.submit[value='Alterar'], #formPJ input[type='button'][value='Alterar']").first.click()

    # O botão chama validaCaptcha('formPJ'), podendo aparecer validação invisível.
    txt = page_text(p).lower()
    if "hcaptcha" in txt or "captcha" in txt:
        pause_manual("Se apareceu captcha ao alterar perfil, resolva manualmente.")

    p.wait_for_load_state("domcontentloaded")
    p.wait_for_timeout(1500)

    # Validação leve: o CNPJ formatado/limpo pode aparecer no cabeçalho ou a página inicial carregar.
    txt2 = page_text(p)
    if "opção indisponível" in txt2.lower() or "opcao indisponivel" in txt2.lower():
        raise RuntimeError(f"Opção indisponível para esse procurador/CNPJ: {formatar_cnpj(cnpj_limpo)}")

    print(f"[PERFIL] Perfil alterado/solicitado para {formatar_cnpj(cnpj_limpo)}")
