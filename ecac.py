from __future__ import annotations

from pathlib import Path

from playwright.sync_api import BrowserContext, Page, Playwright, TimeoutError as PlaywrightTimeoutError, sync_playwright

import config
from utils import click_if_visible, locator_visivel, page_text, pause_manual, snapshot


class ECAC:
    def __init__(self) -> None:
        self._pw: Playwright | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.aba_ecac: Page | None = None

    def iniciar(self) -> None:
        self._pw = sync_playwright().start()
        browser_type = self._pw.chromium
        config.USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.context = browser_type.launch_persistent_context(
            user_data_dir=str(config.USER_DATA_DIR),
            channel=config.BROWSER_CHANNEL,
            headless=config.HEADLESS,
            slow_mo=config.SLOW_MO_MS,
            no_viewport=True,
            args=["--start-maximized"],
        )
        if self.context.pages:
            self.page = self.context.pages[0]
        else:
            self.page = self.context.new_page()
        self.aba_ecac = self.page
        self.page.set_default_timeout(config.TIMEOUT_MS)

    def fechar(self) -> None:
        try:
            if self.context:
                self.context.close()
        finally:
            if self._pw:
                self._pw.stop()

    @property
    def p(self) -> Page:
        if not self.page:
            raise RuntimeError("Navegador não iniciado.")
        return self.page

    def set_page(self, page: Page) -> None:
        self.page = page
        self.page.set_default_timeout(config.TIMEOUT_MS)

    def garantir_aba_ecac(self) -> Page:
        if not self.context:
            raise RuntimeError("Contexto não iniciado.")
        for p in self.context.pages:
            url = p.url.lower()
            if "cav.receita.fazenda.gov.br" in url or "sinac.cav.receita.fazenda.gov.br" in url:
                self.aba_ecac = p
                self.set_page(p)
                return p
        if self.aba_ecac and not self.aba_ecac.is_closed():
            self.set_page(self.aba_ecac)
            return self.aba_ecac
        self.aba_ecac = self.context.new_page()
        self.set_page(self.aba_ecac)
        return self.aba_ecac

    def abrir_ecac(self) -> None:
        self.garantir_aba_ecac()
        self.p.goto(config.ECAC_URL, wait_until="domcontentloaded")

    def login_com_certificado(self) -> None:
        self.abrir_ecac()
        self.p.wait_for_load_state("domcontentloaded")

        # Tela inicial e-CAC: Entrar com Gov.br
        gov = self.p.locator("input[alt='Acesso Gov BR'], input[src*='gov-br']")
        if locator_visivel(gov, 6000):
            gov.first.click()
            self.p.wait_for_load_state("domcontentloaded")
        else:
            gov_texto = self.p.get_by_text("Entrar com gov.br", exact=False)
            if locator_visivel(gov_texto, 3000):
                gov_texto.first.click()
                self.p.wait_for_load_state("domcontentloaded")

        # Pode aparecer hCaptcha invisível/desafio. Não tentamos burlar.
        if "hcaptcha" in page_text(self.p).lower() and config.MANUAL_CAPTCHA:
            pause_manual("Se apareceu validação/hCaptcha do Gov.br, resolva manualmente na tela.")

        # Tela Gov.br: Seu certificado digital
        cert = self.p.locator("#login-certificate, button:has-text('Seu certificado digital')")
        if locator_visivel(cert, 15000):
            cert.first.click()
            if config.MANUAL_CERTIFICATE:
                pause_manual(
                    "Se o Chrome/Windows pedir o certificado, selecione MARCO ANTONIO CARVALHO NETO e confirme."
                )

        self.p.wait_for_load_state("domcontentloaded")
        self.aguardar_painel_ou_login()
        self.aba_ecac = self.p

    def aguardar_painel_ou_login(self) -> None:
        # Aguarda algum elemento típico do e-CAC. Se ainda estiver em tela intermediária, dá tempo.
        try:
            self.p.locator("#btn259, #btn266, input[alt='Acesso Gov BR']").first.wait_for(
                state="visible", timeout=45000
            )
        except PlaywrightTimeoutError:
            pass

    def sessao_expirada(self) -> bool:
        txt = page_text(self.p)
        url = self.p.url.lower()
        return (
            "logout realizado com sucesso" in txt.lower()
            or "voltar para a página de login" in txt.lower()
            or "/autenticacao/logout" in url
        )

    def relogar_se_expirado(self, cnpj_atual: str | None = None) -> bool:
        if not self.sessao_expirada():
            return False
        print("[SESSÃO] Sessão expirada/logout detectado. Refazendo login...")
        link = self.p.locator("a[href*='/autenticacao']")
        if locator_visivel(link, 3000):
            link.first.click()
        else:
            link_texto = self.p.get_by_text("Voltar para a página de login", exact=False)
            if locator_visivel(link_texto, 3000):
                link_texto.first.click()
        self.login_com_certificado()
        if cnpj_atual:
            from perfil import alterar_perfil_cnpj
            alterar_perfil_cnpj(self, cnpj_atual)
        return True

    def home(self) -> None:
        self.garantir_aba_ecac()
        if self.sessao_expirada():
            return
        if click_if_visible(self.p.locator("#linkHome, a[title*='Retornar à página inicial']"), 2500):
            self.p.wait_for_load_state("domcontentloaded")
            return
        # fallback: URL inicial do portal já autenticado
        try:
            self.p.goto("https://cav.receita.fazenda.gov.br/ecac/Default.aspx", wait_until="domcontentloaded")
        except Exception:
            pass

    def abrir_nova_aba_apos_clique(self, locator) -> Page:
        if not self.context:
            raise RuntimeError("Contexto não iniciado.")
        with self.context.expect_page(timeout=config.TIMEOUT_MS) as new_page_info:
            locator.click()
        nova = new_page_info.value
        nova.wait_for_load_state("domcontentloaded")
        self.set_page(nova)
        return nova

    def fechar_aba_atual_e_voltar_ecac(self) -> None:
        atual = self.p
        try:
            if self.aba_ecac and not self.aba_ecac.is_closed() and atual != self.aba_ecac:
                atual.close()
        except Exception:
            pass
        self.garantir_aba_ecac()

    def snapshot(self, nome: str) -> str:
        return snapshot(self.p, nome)
