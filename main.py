from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

import config
from ecac import ECAC
from perfil import alterar_perfil_cnpj
from pgfn import consultar_pgfn
from relatorio import Relatorio
from simples_base import ConsultaSimplesConfig, consultar_parcelamento_simples
from simplificado import consultar_simplificado
from utils import normalizar_cnpj


def ler_cnpjs(caminho: str | Path) -> list[str]:
    path = Path(caminho)
    if not path.exists():
        raise FileNotFoundError(f"Arquivo de CNPJs não encontrado: {path}")

    if path.suffix.lower() in [".xlsx", ".xlsm", ".xls"]:
        df = pd.read_excel(path, dtype=str)
    else:
        df = pd.read_csv(path, dtype=str, sep=None, engine="python")

    if df.empty:
        return []

    col = "CNPJ" if "CNPJ" in df.columns else df.columns[0]
    cnpjs: list[str] = []
    for val in df[col].dropna().tolist():
        cnpj = normalizar_cnpj(val)
        if cnpj and cnpj not in cnpjs:
            cnpjs.append(cnpj)
    return cnpjs


def main() -> int:
    cnpjs = ler_cnpjs(config.INPUT_FILE)
    if not cnpjs:
        print("Nenhum CNPJ encontrado no arquivo de entrada.")
        return 1

    print(f"[INÍCIO] {len(cnpjs)} CNPJ(s) carregado(s).")
    print(f"[ENTRADA] {config.INPUT_FILE}")
    print(f"[SAÍDA] {config.OUTPUT_DIR}")
    print("[MODO] Playwright + Chrome instalado. Captchas/certificado são manuais quando aparecerem.")

    rel = Relatorio()
    ecac = ECAC()
    ecac.iniciar()

    try:
        ecac.login_com_certificado()

        for pos, cnpj in enumerate(cnpjs, start=1):
            etapa_atual = "Alterar perfil"
            print("=" * 90)
            print(f"[CNPJ {pos}/{len(cnpjs)}] {cnpj}")
            try:
                alterar_perfil_cnpj(ecac, cnpj)

                etapa_atual = "PGFN/SISPAR"
                rel.add_resultados(consultar_pgfn(ecac, cnpj))
                rel.salvar("parcelamentos_ecac_parcial")

                for cfg in config.CONSULTAS_SIMPLES_ECAC:
                    etapa_atual = cfg.tipo
                    rel.add_resultados(consultar_parcelamento_simples(
                        ecac,
                        cnpj,
                        ConsultaSimplesConfig(
                            tipo=cfg.tipo,
                            id_aplicacao=cfg.id_aplicacao,
                            mensagem_sem_pedido=cfg.mensagem_sem_pedido,
                        ),
                    ))
                    rel.salvar("parcelamentos_ecac_parcial")

                etapa_atual = "Parcelamento Simplificado"
                resultados_simplificado, debitos_simplificado = consultar_simplificado(ecac, cnpj)
                rel.add_resultados(resultados_simplificado)
                rel.add_debitos(debitos_simplificado)
                rel.salvar("parcelamentos_ecac_parcial")

            except KeyboardInterrupt:
                raise
            except Exception as e:
                screenshot = ""
                try:
                    screenshot = ecac.snapshot(f"erro_{cnpj}_{etapa_atual.replace(' ', '_').replace('/', '_')}")
                except Exception:
                    pass
                print(f"[ERRO] {cnpj} | {etapa_atual}: {e}")
                rel.add_erro(cnpj, etapa_atual, e, screenshot)
                rel.salvar("parcelamentos_ecac_parcial")
                try:
                    ecac.garantir_aba_ecac()
                    ecac.home()
                except Exception:
                    pass

        arquivos = rel.salvar("parcelamentos_ecac")
        print("[FIM] Consulta finalizada.")
        print(f"Excel: {arquivos['xlsx']}")
        print(f"JSON:  {arquivos['json']}")
        return 0

    except KeyboardInterrupt:
        print("\n[INTERROMPIDO] Execução interrompida pelo usuário.")
        rel.salvar("parcelamentos_ecac_interrompido")
        return 130
    finally:
        input("Pressione ENTER para fechar o navegador...")
        ecac.fechar()


if __name__ == "__main__":
    raise SystemExit(main())
