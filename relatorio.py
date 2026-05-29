from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

import config
from models import DebitoParcelado, ResultadoParcelamento


class Relatorio:
    def __init__(self) -> None:
        self.resultados: list[ResultadoParcelamento] = []
        self.debitos: list[DebitoParcelado] = []
        self.erros: list[dict] = []

    def add_resultado(self, resultado: ResultadoParcelamento) -> None:
        self.resultados.append(resultado)

    def add_resultados(self, resultados: Iterable[ResultadoParcelamento]) -> None:
        self.resultados.extend(resultados)

    def add_debitos(self, debitos: Iterable[DebitoParcelado]) -> None:
        self.debitos.extend(debitos)

    def add_erro(self, cnpj: str, etapa: str, erro: Exception | str, screenshot: str = "") -> None:
        self.erros.append({
            "cnpj": cnpj,
            "etapa": etapa,
            "erro": str(erro),
            "screenshot": screenshot,
            "data_hora": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        })

    def salvar(self, nome_base: str = "parcelamentos_ecac") -> dict[str, Path]:
        config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        xlsx = config.OUTPUT_DIR / f"{nome_base}.xlsx"
        js = config.OUTPUT_DIR / f"{nome_base}.json"

        resultados_dict = [r.to_dict() for r in self.resultados]
        debitos_dict = [d.to_dict() for d in self.debitos]

        with pd.ExcelWriter(xlsx, engine="openpyxl") as writer:
            pd.DataFrame(resultados_dict).to_excel(writer, sheet_name="Parcelamentos", index=False)
            pd.DataFrame(debitos_dict).to_excel(writer, sheet_name="Debitos Parcelados", index=False)
            pd.DataFrame(self.erros).to_excel(writer, sheet_name="Erros", index=False)

        payload = {
            "gerado_em": datetime.now().isoformat(timespec="seconds"),
            "resultados": resultados_dict,
            "debitos": debitos_dict,
            "erros": self.erros,
        }
        js.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"xlsx": xlsx, "json": js}
