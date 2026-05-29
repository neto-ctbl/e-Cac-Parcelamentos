from __future__ import annotations

import re
from datetime import date

from playwright.sync_api import Page

from ecac import ECAC
from models import ResultadoParcelamento
from utils import (
    click_if_visible,
    extrair_valor_por_rotulo_texto,
    is_status_ativo,
    linhas_com_header,
    localizar_tabela_por_cabecalho,
    locator_visivel,
    page_text,
)


def navegar_pgfn(ecac: ECAC) -> Page:
    p = ecac.p
    ecac.home()
    ecac.relogar_se_expirado()
    p.locator("#btn259, li#btn259 a").first.click()
    p.locator("#btn255, li#btn255 a").first.click()
    link = p.locator("a[href*='PGFN/consultaDebitos/app.aspx']")
    link.first.wait_for(state="visible", timeout=20000)
    nova = ecac.abrir_nova_aba_apos_clique(link.first)
    return nova


def caiu_cadastro_regularize(page: Page) -> bool:
    txt = page_text(page).lower()
    return "/cadastro" in page.url.lower() or "você ainda não está cadastrado no regularize" in txt or "voce ainda nao esta cadastrado no regularize" in txt


def entrar_sispar(page: Page) -> None:
    click_if_visible(page.locator("button:has-text('Ciente')"), 5000)
    card = page.locator("text=Negociar Dívida")
    if locator_visivel(card, 15000):
        card.first.click()
    acessar = page.locator("button:has-text('Acessar')")
    if locator_visivel(acessar, 15000):
        acessar.first.click()
    emitir = page.locator("text=EMITIR GUIA")
    if locator_visivel(emitir, 15000):
        emitir.first.click()
    continuar = page.locator("button:has-text('Continuar')")
    if locator_visivel(continuar, 15000):
        continuar.first.click()
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2000)


def listar_negociacoes_pgfn(page: Page) -> list[dict[str, str]]:
    # PrimeFaces/SISPAR pode variar muito. Tentamos por tabelas com Situação/Negociação.
    tabela = localizar_tabela_por_cabecalho(page, ["Situação"])
    linhas = linhas_com_header(tabela)
    return linhas


def abrir_primeira_negociacao_ativa(page: Page, idx_linha: int) -> None:
    # Tenta clicar na linha/ícone de ação correspondente.
    rows = page.locator("table tr")
    try:
        rows.nth(idx_linha + 1).click()
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1000)
    except Exception:
        pass


def abrir_documento_arrecadacao(page: Page) -> None:
    emissao = page.locator("span:has-text('Emissão de Documento'), a:has-text('Emissão de Documento')")
    if locator_visivel(emissao, 10000):
        emissao.first.hover()
        page.wait_for_timeout(500)
    doc = page.locator("span:has-text('Documento de arrecadação'), a:has-text('Documento de arrecadação')")
    if locator_visivel(doc, 5000):
        doc.first.click()
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1000)
    botao = page.locator("span:has-text('Documento de Arrecadação')")
    if locator_visivel(botao, 5000):
        botao.first.click()
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1000)


def extrair_dados_pgfn(page: Page) -> ResultadoParcelamento:
    txt = page_text(page)
    tipo = extrair_valor_por_rotulo_texto(txt, ["Negociações", "Negociação"])
    modalidade = extrair_valor_por_rotulo_texto(txt, ["Modalidade"])
    nr_ref = extrair_valor_por_rotulo_texto(txt, ["Nr. Referência Conta", "Nr. Referencia Conta"])
    data_adesao = extrair_valor_por_rotulo_texto(txt, ["Data da Adesão", "Data da Adesao"])
    contribuinte = extrair_valor_por_rotulo_texto(txt, ["Contribuinte"])
    total_parcelas = extrair_valor_por_rotulo_texto(txt, ["Total de Parcelas"])
    valor_consolidado = extrair_valor_por_rotulo_texto(txt, ["Valor consolidado"])
    saldo_devedor = extrair_valor_por_rotulo_texto(txt, ["Saldo Devedor sem Juros", "Saldo Devedor"])

    empresa = ""
    cnpj = ""
    m = re.search(r"(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\s*-\s*(.+)", contribuinte)
    if m:
        cnpj = re.sub(r"\D", "", m.group(1))
        empresa = m.group(2).strip()

    # Tabela de prestações, se disponível.
    tabela = localizar_tabela_por_cabecalho(page, ["Prestação"])
    linhas = linhas_com_header(tabela)
    parcela_atual = ""
    valor_parcela = ""
    tem_atraso = "Não identificado"
    data_venc = ""
    hoje = date.today()
    for row in linhas:
        situacao_txt = " ".join(row.values()).lower()
        nr = next((v for k, v in row.items() if "prest" in k.lower() or "parcela" in k.lower()), "")
        venc = next((v for k, v in row.items() if "venc" in k.lower()), "")
        valor = next((v for k, v in row.items() if "valor" in k.lower()), "")
        pago = "pago" in situacao_txt or "título pago" in situacao_txt or "titulo pago" in situacao_txt
        if not pago and not parcela_atual:
            parcela_atual = nr
            valor_parcela = valor
            data_venc = venc
        if not pago and re.match(r"\d{2}/\d{2}/\d{4}", venc or ""):
            try:
                d, m, a = map(int, venc.split("/"))
                if date(a, m, d) < hoje:
                    tem_atraso = "Sim"
            except Exception:
                pass
    if tem_atraso == "Não identificado" and parcela_atual:
        tem_atraso = "Não"

    return ResultadoParcelamento(
        cnpj=cnpj,
        empresa=empresa,
        origem="PGFN/SISPAR",
        tipo_parcelamento=tipo or "Parcelamento PGFN",
        tem_parcelamento="Sim",
        numero_protocolo=nr_ref,
        modalidade=modalidade,
        situacao="Ativo",
        data_adesao=data_adesao,
        total_parcelas=total_parcelas,
        parcela_atual=parcela_atual,
        valor_parcela=valor_parcela,
        valor_consolidado=valor_consolidado,
        saldo_devedor=saldo_devedor,
        tem_parcela_atraso=tem_atraso,
        data_vencimento_parcela_atual=data_venc,
        criterio_calculo="Tabela de prestações do SISPAR/PGFN.",
        status_consulta="OK",
    )


def consultar_pgfn(ecac: ECAC, cnpj: str) -> list[ResultadoParcelamento]:
    print("[PGFN] Consultando...")
    resultados: list[ResultadoParcelamento] = []
    try:
        page = navegar_pgfn(ecac)
        if caiu_cadastro_regularize(page):
            resultados.append(ResultadoParcelamento(
                cnpj=cnpj,
                origem="PGFN/SISPAR",
                tipo_parcelamento="Parcelamento PGFN",
                tem_parcelamento="Não",
                status_consulta="Sem cadastro no Regularize",
                observacoes="Empresa direcionada para a tela de cadastro do Regularize.",
            ))
            return resultados

        entrar_sispar(page)
        if caiu_cadastro_regularize(page):
            resultados.append(ResultadoParcelamento(
                cnpj=cnpj,
                origem="PGFN/SISPAR",
                tipo_parcelamento="Parcelamento PGFN",
                tem_parcelamento="Não",
                status_consulta="Sem cadastro no Regularize",
                observacoes="Empresa direcionada para a tela de cadastro do Regularize.",
            ))
            return resultados

        negociacoes = listar_negociacoes_pgfn(page)
        ativos = [(i, n) for i, n in enumerate(negociacoes) if is_status_ativo(n.get("Situação", n.get("Situação da conta", "")))]
        if not negociacoes:
            # Tenta extrair direto se já caiu numa tela de resumo.
            txt = page_text(page)
            if "dados da negocia" in txt.lower() or "nr. referência conta" in txt.lower():
                resultados.append(extrair_dados_pgfn(page))
            else:
                resultados.append(ResultadoParcelamento(
                    cnpj=cnpj,
                    origem="PGFN/SISPAR",
                    tipo_parcelamento="Parcelamento PGFN",
                    tem_parcelamento="Não identificado",
                    status_consulta="Listagem PGFN não encontrada",
                    observacoes="Não foi possível localizar tabela de negociações no Regularize/SISPAR.",
                ))
            return resultados

        if not ativos:
            resultados.append(ResultadoParcelamento(
                cnpj=cnpj,
                origem="PGFN/SISPAR",
                tipo_parcelamento="Parcelamento PGFN",
                tem_parcelamento="Não",
                status_consulta="Sem negociação ativa",
                observacoes="Existem negociações, mas nenhuma ativa/operante.",
            ))
            return resultados

        for idx, neg in ativos:
            abrir_primeira_negociacao_ativa(page, idx)
            abrir_documento_arrecadacao(page)
            r = extrair_dados_pgfn(page)
            r.cnpj = r.cnpj or cnpj
            r.situacao = neg.get("Situação", neg.get("Situação da conta", r.situacao))
            if not r.numero_protocolo:
                r.numero_protocolo = neg.get("Negociação", neg.get("Número", ""))
            resultados.append(r)

    finally:
        ecac.fechar_aba_atual_e_voltar_ecac()
    return resultados
