from __future__ import annotations

import re
from datetime import date

from playwright.sync_api import Page

from ecac import ECAC
from models import DebitoParcelado, ResultadoParcelamento
from utils import (
    click_if_visible,
    extrair_valor_por_rotulo_texto,
    is_status_ativo,
    linhas_com_header,
    localizar_tabela_por_cabecalho,
    locator_visivel,
    moeda_para_float,
    page_text,
)


def abrir_simplificado(ecac: ECAC) -> None:
    p = ecac.p
    ecac.home()
    ecac.relogar_se_expirado()
    p.locator("#btn259, li#btn259 a").first.click()
    link = p.locator("a[href*='Aplicacao.aspx?id=10014']")
    link.first.wait_for(state="visible", timeout=20000)
    link.first.click()
    p.wait_for_load_state("domcontentloaded")
    entrar = p.locator("a[href*='/siefpar-inter/consultar-parcelamento/consultar-parcelamento']")
    entrar.first.wait_for(state="visible", timeout=30000)
    entrar.first.click()
    p.wait_for_load_state("domcontentloaded")
    p.wait_for_timeout(2000)


def clicar_consultar(page: Page) -> None:
    page.locator("button:has-text('Consultar')").first.click()
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(2000)


def mensagem_sem_negociacao(page: Page) -> str:
    msg = page.locator(".ui-messages-detail:has-text('Não existem negociações')")
    if locator_visivel(msg, 4000):
        return msg.first.inner_text().strip()
    return ""


def listar_negociacoes(page: Page) -> list[dict[str, str]]:
    tabela = localizar_tabela_por_cabecalho(page, ["Negociação", "Data do requerimento", "Situação"])
    return linhas_com_header(tabela)


def abrir_menu_extrato(page: Page, idx_linha: int) -> None:
    # Botão hamburguer da mesma linha ativa. Fallback clica no n-ésimo botão.
    botoes = page.locator("button.icone.hamburguer, button:has(.ui-button-text:has-text('ui-btn'))")
    botoes.nth(idx_linha).click()
    page.wait_for_timeout(500)
    page.locator("span.ui-menuitem-text:has-text('Extrato'), a:has-text('Extrato')").first.click()
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1500)


def extrair_identificacao_extrato(page: Page) -> dict[str, str]:
    txt = page_text(page)
    return {
        "cnpj": extrair_valor_por_rotulo_texto(txt, ["CNPJ/CPF"]),
        "empresa": extrair_valor_por_rotulo_texto(txt, ["Nome/Nome empresarial"]),
        "modalidade": extrair_valor_por_rotulo_texto(txt, ["Modalidade"]),
        "negociacao": extrair_valor_por_rotulo_texto(txt, ["Negociação"]),
        "data_consolidacao": extrair_valor_por_rotulo_texto(txt, ["Data da consolidação"]),
        "situacao": extrair_valor_por_rotulo_texto(txt, ["Situação"]),
        "divida_consolidacao": extrair_valor_por_rotulo_texto(txt, ["Dívida na data da consolidação (BRL)", "Divida na data da consolidacao"]),
        "pagamentos": extrair_valor_por_rotulo_texto(txt, ["Pagamentos (BRL)"]),
        "saldo_devedor": extrair_valor_por_rotulo_texto(txt, ["Saldo devedor"]),
        "juros": extrair_valor_por_rotulo_texto(txt, ["Juros incidentes"]),
        "saldo_devedor_atualizado": extrair_valor_por_rotulo_texto(txt, ["Saldo devedor em"]),
    }


def abrir_demonstrativo_parcelas(page: Page) -> None:
    page.locator("button:has-text('Demonstrativo de parcelas')").first.click()
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1500)


def extrair_resumo_parcelas(page: Page) -> dict[str, str]:
    txt = page_text(page)
    return {
        "total_parcelas": extrair_valor_por_rotulo_texto(txt, ["Total de parcelas"]),
        "parcelas_devedoras": extrair_valor_por_rotulo_texto(txt, ["Parcelas devedoras"]),
        "parcelas_pagas_parcialmente": extrair_valor_por_rotulo_texto(txt, ["Parcelas pagas parcialmente"]),
        "parcelas_pagas": extrair_valor_por_rotulo_texto(txt, ["Parcelas pagas"]),
        "parcelas_em_analise": extrair_valor_por_rotulo_texto(txt, ["Parcelas em análise", "Parcelas em analise"]),
        "parcelas_dispensa": extrair_valor_por_rotulo_texto(txt, ["Parcelas com dispensa de recolhimento"]),
        "parcelas_a_vencer": extrair_valor_por_rotulo_texto(txt, ["Parcelas a vencer"]),
        "valor_parcelas_devedoras": extrair_valor_por_rotulo_texto(txt, ["Valor parcelas devedoras"]),
    }


def extrair_tabela_parcelas(page: Page) -> list[dict[str, str]]:
    tabela = localizar_tabela_por_cabecalho(page, ["Parcela", "Vencimento", "Situação"])
    return linhas_com_header(tabela)


def calcular_simplificado(parcelas: list[dict[str, str]], resumo: dict[str, str]) -> dict[str, str]:
    hoje = date.today()
    primeira_aberta = None
    tem_atraso = "Não"
    valor_atraso = resumo.get("valor_parcelas_devedoras", "")

    if moeda_para_float(valor_atraso) > 0:
        tem_atraso = "Sim"

    for row in parcelas:
        situacao = next((v for k, v in row.items() if "situa" in k.lower()), "")
        parcela = next((v for k, v in row.items() if k.lower().strip() == "parcela" or "parcela" in k.lower()), "")
        venc = next((v for k, v in row.items() if "venc" in k.lower()), "")
        valor = next((v for k, v in row.items() if "valor origin" in k.lower() or "saldo atualizado" in k.lower()), "")
        s = situacao.lower()
        if "paga" not in s and primeira_aberta is None:
            primeira_aberta = {"parcela": parcela, "vencimento": venc, "valor": valor, "situacao": situacao}
        if "devedor" in s:
            tem_atraso = "Sim"
        elif "paga" not in s and re.match(r"\d{2}/\d{2}/\d{4}", venc or ""):
            try:
                d, m, a = map(int, venc.split("/"))
                if date(a, m, d) < hoje:
                    tem_atraso = "Sim"
            except Exception:
                pass

    return {
        "parcela_atual": (primeira_aberta or {}).get("parcela", ""),
        "data_vencimento": (primeira_aberta or {}).get("vencimento", ""),
        "valor_parcela": (primeira_aberta or {}).get("valor", ""),
        "situacao_parcela_atual": (primeira_aberta or {}).get("situacao", ""),
        "tem_atraso": tem_atraso,
        "valor_atraso": valor_atraso,
    }


def voltar_extrato(page: Page) -> None:
    click_if_visible(page.locator("#linkVoltar, a[aria-label*='Voltar'], a:has-text('Voltar')"), 3000)
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1000)


def abrir_consultar_debitos(page: Page) -> None:
    page.locator("button:has-text('Consultar débitos'), button:has-text('Consultar debitos')").first.click()
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1500)


def extrair_debitos(page: Page, cnpj: str, empresa: str, tipo: str, negociacao: str) -> list[DebitoParcelado]:
    tabela = localizar_tabela_por_cabecalho(page, ["CPF/CNPJ"])
    if not tabela:
        tabela = localizar_tabela_por_cabecalho(page, ["Tributo"])
    linhas = linhas_com_header(tabela)
    debitos: list[DebitoParcelado] = []
    for row in linhas:
        debitos.append(DebitoParcelado(
            cnpj=cnpj,
            empresa=empresa,
            tipo_parcelamento=tipo,
            numero_protocolo=negociacao,
            tributo=row.get("Tributo", ""),
            codigo_receita=row.get("Código de receita", row.get("Codigo de receita", "")),
            pa_competencia=row.get("PA", row.get("Competência", row.get("Competencia", ""))),
            processo=row.get("Processo", ""),
            valor_principal=row.get("Principal", row.get("Valor principal", "")),
            multa=row.get("Multa", ""),
            juros=row.get("Juros", ""),
            total=row.get("Total", ""),
            situacao=row.get("Situação", row.get("Situacao", "")),
            observacoes="Extraído da tela Consultar débitos do SIEFPAR.",
        ))
    return debitos


def consultar_simplificado(ecac: ECAC, cnpj: str) -> tuple[list[ResultadoParcelamento], list[DebitoParcelado]]:
    print("[Parcelamento Simplificado] Consultando...")
    resultados: list[ResultadoParcelamento] = []
    debitos: list[DebitoParcelado] = []
    p = ecac.p

    abrir_simplificado(ecac)
    clicar_consultar(p)

    msg = mensagem_sem_negociacao(p)
    if msg:
        resultados.append(ResultadoParcelamento(
            cnpj=cnpj,
            origem="e-CAC/SIEFPAR",
            tipo_parcelamento="Parcelamento Simplificado",
            tem_parcelamento="Não",
            status_consulta="Sem negociação",
            observacoes=msg,
        ))
        return resultados, debitos

    negociacoes = listar_negociacoes(p)
    ativos = [(i, n) for i, n in enumerate(negociacoes) if is_status_ativo(n.get("Situação", ""))]
    if not ativos:
        resultados.append(ResultadoParcelamento(
            cnpj=cnpj,
            origem="e-CAC/SIEFPAR",
            tipo_parcelamento="Parcelamento Simplificado",
            tem_parcelamento="Não",
            status_consulta="Sem negociação ativa",
            observacoes="Não existem negociações ativas/operantes com os critérios informados.",
        ))
        return resultados, debitos

    for idx, neg in ativos:
        # Se for múltipla negociação, retorna à consulta entre uma e outra.
        if idx != ativos[0][0]:
            abrir_simplificado(ecac)
            clicar_consultar(p)
        abrir_menu_extrato(p, idx)
        ident = extrair_identificacao_extrato(p)
        abrir_demonstrativo_parcelas(p)
        resumo = extrair_resumo_parcelas(p)
        parcelas = extrair_tabela_parcelas(p)
        calc = calcular_simplificado(parcelas, resumo)

        negociacao = ident.get("negociacao") or neg.get("Negociação", "")
        empresa = ident.get("empresa") or ""
        modalidade = ident.get("modalidade") or neg.get("Modalidade", "") or "Parcelamento Simplificado"

        resultados.append(ResultadoParcelamento(
            cnpj=cnpj,
            empresa=empresa,
            origem="e-CAC/SIEFPAR",
            tipo_parcelamento="Parcelamento Simplificado",
            tem_parcelamento="Sim",
            numero_protocolo=negociacao,
            modalidade=modalidade,
            situacao=ident.get("situacao") or neg.get("Situação", ""),
            data_adesao=neg.get("Data do requerimento", ""),
            data_consolidacao=ident.get("data_consolidacao", ""),
            total_parcelas=resumo.get("total_parcelas", ""),
            parcelas_pagas=resumo.get("parcelas_pagas", ""),
            parcelas_devedoras=resumo.get("parcelas_devedoras", ""),
            parcelas_a_vencer=resumo.get("parcelas_a_vencer", ""),
            parcelas_em_aberto=str(sum(int(x or 0) for x in [
                re.sub(r"\D", "", resumo.get("parcelas_devedoras", "0")) or "0",
                re.sub(r"\D", "", resumo.get("parcelas_a_vencer", "0")) or "0",
                re.sub(r"\D", "", resumo.get("parcelas_pagas_parcialmente", "0")) or "0",
            ])),
            parcela_atual=calc["parcela_atual"],
            valor_parcela=calc["valor_parcela"],
            valor_pago=ident.get("pagamentos", ""),
            valor_consolidado=ident.get("divida_consolidacao", ""),
            saldo_devedor=ident.get("saldo_devedor", ""),
            saldo_devedor_atualizado=ident.get("saldo_devedor_atualizado", ""),
            tem_parcela_atraso=calc["tem_atraso"],
            valor_atraso=calc["valor_atraso"],
            data_vencimento_parcela_atual=calc["data_vencimento"],
            criterio_calculo="Primeira parcela do demonstrativo com situação diferente de Paga; atraso por Parcelas devedoras ou vencimento expirado.",
            status_consulta="OK",
            observacoes=f"Situação da parcela atual: {calc['situacao_parcela_atual']}",
        ))

        voltar_extrato(p)
        try:
            abrir_consultar_debitos(p)
            debitos.extend(extrair_debitos(p, cnpj, empresa, "Parcelamento Simplificado", negociacao))
        except Exception:
            # Débitos são auxiliares; não devem derrubar a consulta principal.
            pass

    return resultados, debitos
