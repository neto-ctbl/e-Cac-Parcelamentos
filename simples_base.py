from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from playwright.sync_api import Page

import config
from ecac import ECAC
from models import ResultadoParcelamento
from utils import (
    click_if_visible,
    diferenca_meses,
    extrair_data,
    extrair_mm_aaaa,
    extrair_moeda,
    extrair_valor_por_rotulo_texto,
    hoje_competencia,
    is_status_ativo,
    linhas_com_header,
    localizar_tabela_por_cabecalho,
    locator_visivel,
    moeda_para_float,
    page_text,
    pause_manual,
)


@dataclass(frozen=True)
class ConsultaSimplesConfig:
    tipo: str
    id_aplicacao: str
    mensagem_sem_pedido: str


def abrir_servico_simples(ecac: ECAC, cfg: ConsultaSimplesConfig) -> None:
    p = ecac.p
    ecac.home()
    ecac.relogar_se_expirado()
    p.locator("#btn266, li#btn266 a").first.click()
    link = p.locator(f"a[href*='Aplicacao.aspx?id={cfg.id_aplicacao}']")
    link.first.wait_for(state="visible", timeout=20000)
    link.first.click()
    p.wait_for_load_state("domcontentloaded")


def resolver_captcha_consulta(p: Page) -> None:
    modal = p.locator(".ui-dialog:has-text('Consulta Pedidos de Parcelamento'), #hcaptcha, iframe[src*='hcaptcha']")
    if locator_visivel(modal, 5000):
        pause_manual("Resolva o hCaptcha da consulta de pedidos de parcelamento na tela.")
        cont = p.locator(".ui-dialog button:has-text('Continuar'), button:has-text('Continuar')")
        click_if_visible(cont, 3000)
        p.wait_for_load_state("domcontentloaded")
        p.wait_for_timeout(1500)


def tratar_popup_sem_pedido(p: Page) -> str:
    msg = p.locator("#popup_message")
    if locator_visivel(msg, 3000):
        texto = msg.first.inner_text().strip()
        click_if_visible(p.locator("#popup_ok"), 2000)
        return texto
    return ""


def clicar_consulta_pedidos(ecac: ECAC) -> None:
    p = ecac.p
    p.locator("#ctl00_contentPlaceH_linkButtonConsulta, a[name='ConsultarPedido']").first.click()
    resolver_captcha_consulta(p)


def listar_pedidos(page: Page) -> list[dict[str, str]]:
    tabela = localizar_tabela_por_cabecalho(page, ["Número", "Data do pedido", "Situação"])
    return linhas_com_header(tabela)


def clicar_linha_pedido_ativo(page: Page, indice_ativo: int) -> None:
    # Índice é dentro das linhas de dados visíveis da tabela.
    rows = page.locator("#ctl00_contentPlaceH_wcParc_gdv tr, table.dataGrid tr")
    # pula cabeçalho
    rows.nth(indice_ativo + 1).click()
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1000)


def extrair_dados_tela_detalhe(page: Page) -> dict[str, str]:
    txt = page_text(page)
    dados: dict[str, str] = {}
    dados["empresa"] = extrair_valor_por_rotulo_texto(txt, ["Nome Empresarial", "Nome empresarial", "Nome/Nome empresarial"])
    dados["data_adesao"] = extrair_valor_por_rotulo_texto(txt, ["Data do pedido"])
    dados["situacao"] = extrair_valor_por_rotulo_texto(txt, ["Situação"])
    dados["data_situacao"] = extrair_valor_por_rotulo_texto(txt, ["Data da situação"])
    dados["valor_consolidado"] = extrair_valor_por_rotulo_texto(txt, ["Valor total consolidado", "Valor consolidado da dívida", "Total consolidado"])
    dados["total_parcelas"] = extrair_valor_por_rotulo_texto(txt, ["Quantidade de parcelas", "Total de parcelas"])
    dados["parcelas_remanescentes"] = extrair_valor_por_rotulo_texto(txt, ["Parcelas remanescentes", "Parcelas remanescentes da entrada"])
    dados["valor_parcela"] = extrair_valor_por_rotulo_texto(txt, ["Parcela básica", "Parcela básica da entrada"])
    dados["data_consolidacao"] = extrair_valor_por_rotulo_texto(txt, ["Data da consolidação"])

    # Fallback por tabelas específicas.
    for tabela in localizar_tabela_por_cabecalho(page, ["Mês da parcela", "Vencimento do DAS", "Data de arrecadação"]),:
        pass
    return dados


def obter_demonstrativo_pagamentos(page: Page) -> list[dict[str, str]]:
    tabela = localizar_tabela_por_cabecalho(page, ["Mês da parcela", "Vencimento", "Valor pago"])
    return linhas_com_header(tabela)


def clicar_ultima_parcela_demonstrativo(page: Page, qtd_linhas: int) -> None:
    if qtd_linhas <= 0:
        return
    # Procura a tabela do demonstrativo e clica na primeira célula da última linha de dados.
    page.evaluate(
        """
        () => {
            const tables = Array.from(document.querySelectorAll('table'));
            const tbl = tables.find(t => /Mês da parcela|Mes da parcela/i.test(t.innerText) && /Valor pago/i.test(t.innerText));
            if (!tbl) return;
            const rows = Array.from(tbl.querySelectorAll('tr')).filter(r => r.querySelectorAll('td').length);
            const last = rows[rows.length - 1];
            if (!last) return;
            const target = last.querySelector('a, td');
            if (target) target.click();
        }
        """
    )
    page.wait_for_load_state("domcontentloaded")
    page.wait_for_timeout(1000)


def extrair_extrato_das(page: Page) -> dict[str, str]:
    txt = page_text(page)
    dados: dict[str, str] = {}
    dados["empresa"] = extrair_valor_por_rotulo_texto(txt, ["Nome empresarial", "Nome Empresarial"])
    dados["cnpj"] = extrair_valor_por_rotulo_texto(txt, ["CNPJ Matriz"])
    dados["mes_parcela"] = extrair_valor_por_rotulo_texto(txt, ["Mês da parcela"])
    dados["valor_das"] = extrair_valor_por_rotulo_texto(txt, ["Valor do DAS gerado"])
    dados["numero_das"] = extrair_valor_por_rotulo_texto(txt, ["Nº do DAS", "No do DAS"])
    dados["numero_parcelamento_parcela"] = extrair_valor_por_rotulo_texto(
        txt, ["Nº do parcelamento/Nº da parcela", "No do parcelamento/No da parcela"]
    )
    dados["data_vencimento"] = extrair_valor_por_rotulo_texto(txt, ["Data de vencimento"])
    dados["data_pagamento"] = extrair_valor_por_rotulo_texto(txt, ["Data do Pagamento"])
    dados["valor_pago"] = extrair_valor_por_rotulo_texto(txt, ["Valor Pago"])

    if not dados["numero_parcelamento_parcela"]:
        m = re.search(r"(\d{3,})\s*/\s*(\d{1,3})", txt)
        if m:
            dados["numero_parcelamento_parcela"] = f"{m.group(1)}/{m.group(2)}"
    return dados


def calcular_parcela_por_demonstrativo(ultima_comp: str, ultima_parcela: str) -> dict[str, str]:
    comp_atual = hoje_competencia()
    try:
        up = int(re.sub(r"\D", "", ultima_parcela or "0"))
    except ValueError:
        up = 0
    diff = diferenca_meses(ultima_comp, comp_atual) if ultima_comp and up else 0
    if diff < 0:
        diff = 0
    parcela_atual = up + diff if up else ""
    atraso = "Não"
    if diff >= 2:
        atraso = "Sim"
    elif diff == 1:
        # Conservador: competência anterior sem pagamento; pode já estar vencida dependendo do dia.
        atraso = "Verificar"
    return {
        "competencia_atual": comp_atual,
        "parcelas_em_aberto": str(diff),
        "parcela_atual_estimada": str(parcela_atual) if parcela_atual else "",
        "tem_atraso": atraso,
        "criterio": "Última parcela paga no Demonstrativo + diferença de meses até a competência atual.",
    }


def consultar_parcelamento_simples(ecac: ECAC, cnpj: str, cfg: ConsultaSimplesConfig) -> list[ResultadoParcelamento]:
    print(f"[{cfg.tipo}] Consultando...")
    resultados: list[ResultadoParcelamento] = []
    p = ecac.p

    abrir_servico_simples(ecac, cfg)
    clicar_consulta_pedidos(ecac)

    msg = tratar_popup_sem_pedido(p)
    if msg:
        resultados.append(ResultadoParcelamento(
            cnpj=cnpj,
            origem="e-CAC",
            tipo_parcelamento=cfg.tipo,
            tem_parcelamento="Não",
            status_consulta="Sem pedido",
            observacoes=msg,
        ))
        return resultados

    pedidos = listar_pedidos(p)
    if not pedidos:
        resultados.append(ResultadoParcelamento(
            cnpj=cnpj,
            origem="e-CAC",
            tipo_parcelamento=cfg.tipo,
            tem_parcelamento="Não identificado",
            status_consulta="Tabela de pedidos não encontrada",
            observacoes="Não foi possível localizar a tabela de pedidos após a consulta.",
        ))
        return resultados

    ativos = [(idx, ped) for idx, ped in enumerate(pedidos) if is_status_ativo(ped.get("Situação", ""))]
    if not ativos:
        resultados.append(ResultadoParcelamento(
            cnpj=cnpj,
            origem="e-CAC",
            tipo_parcelamento=cfg.tipo,
            tem_parcelamento="Não",
            status_consulta="Sem pedido ativo",
            observacoes="Existem pedidos, mas nenhum em situação Em parcelamento.",
        ))
        return resultados

    for idx, pedido in ativos:
        # Se houver múltiplos ativos, precisamos garantir que estamos na listagem novamente.
        if idx != ativos[0][0]:
            ecac.home()
            abrir_servico_simples(ecac, cfg)
            clicar_consulta_pedidos(ecac)
        clicar_linha_pedido_ativo(p, idx)

        dados = extrair_dados_tela_detalhe(p)
        demonstrativo = obter_demonstrativo_pagamentos(p)
        ultima = demonstrativo[-1] if demonstrativo else {}
        ultima_comp = ""
        valor_pago = ""
        data_pagamento = ""
        data_vencimento = ""
        for k, v in ultima.items():
            nk = k.lower()
            if "mês" in nk or "mes" in nk:
                ultima_comp = extrair_mm_aaaa(v)
            elif "valor" in nk:
                valor_pago = v
            elif "arrecada" in nk or "pagamento" in nk:
                data_pagamento = v
            elif "venc" in nk:
                data_vencimento = v

        extrato = {}
        if demonstrativo:
            clicar_ultima_parcela_demonstrativo(p, len(demonstrativo))
            extrato = extrair_extrato_das(p)
            # Volta para a tela de detalhe para próximo pedido/saída.
            click_if_visible(p.locator("#linkVoltar, a:has-text('Voltar'), input[value='Retornar']"), 1000)

        num_parc = ""
        ultima_parcela = ""
        npp = extrato.get("numero_parcelamento_parcela", "")
        if "/" in npp:
            num_parc, ultima_parcela = [x.strip() for x in npp.split("/", 1)]
        else:
            num_parc = pedido.get("Número", "")

        calc = calcular_parcela_por_demonstrativo(ultima_comp or extrato.get("mes_parcela", ""), ultima_parcela)

        resultados.append(ResultadoParcelamento(
            cnpj=cnpj,
            empresa=extrato.get("empresa") or dados.get("empresa", ""),
            origem="e-CAC",
            tipo_parcelamento=cfg.tipo,
            tem_parcelamento="Sim",
            numero_protocolo=num_parc or pedido.get("Número", ""),
            situacao=pedido.get("Situação", dados.get("situacao", "")),
            data_adesao=pedido.get("Data do pedido", dados.get("data_adesao", "")),
            data_consolidacao=dados.get("data_consolidacao", ""),
            data_situacao=pedido.get("Data da situação", dados.get("data_situacao", "")),
            total_parcelas=dados.get("total_parcelas", ""),
            parcelas_em_aberto=calc["parcelas_em_aberto"],
            ultima_competencia_paga=ultima_comp or extrato.get("mes_parcela", ""),
            ultima_parcela_paga=ultima_parcela,
            competencia_atual_consulta=calc["competencia_atual"],
            parcela_atual=calc["parcela_atual_estimada"],
            parcela_atual_estimada=calc["parcela_atual_estimada"],
            valor_parcela=extrato.get("valor_das") or dados.get("valor_parcela", ""),
            valor_pago=extrato.get("valor_pago") or valor_pago,
            valor_consolidado=dados.get("valor_consolidado", ""),
            tem_parcela_atraso=calc["tem_atraso"],
            data_vencimento_parcela_atual=extrato.get("data_vencimento") or data_vencimento,
            data_pagamento=extrato.get("data_pagamento") or data_pagamento,
            criterio_calculo=calc["criterio"],
            status_consulta="OK",
            observacoes=f"Última competência paga no demonstrativo: {ultima_comp or extrato.get('mes_parcela', '')}",
        ))

    return resultados
