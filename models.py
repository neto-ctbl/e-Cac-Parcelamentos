from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ResultadoParcelamento:
    cnpj: str = ""
    empresa: str = ""
    origem: str = ""
    tipo_parcelamento: str = ""
    tem_parcelamento: str = ""
    numero_protocolo: str = ""
    modalidade: str = ""
    situacao: str = ""
    data_adesao: str = ""
    data_consolidacao: str = ""
    data_situacao: str = ""
    total_parcelas: str = ""
    parcelas_pagas: str = ""
    parcelas_devedoras: str = ""
    parcelas_a_vencer: str = ""
    parcelas_em_aberto: str = ""
    ultima_competencia_paga: str = ""
    ultima_parcela_paga: str = ""
    competencia_atual_consulta: str = ""
    parcela_atual: str = ""
    parcela_atual_estimada: str = ""
    valor_parcela: str = ""
    valor_pago: str = ""
    valor_consolidado: str = ""
    saldo_devedor: str = ""
    saldo_devedor_atualizado: str = ""
    tem_parcela_atraso: str = ""
    valor_atraso: str = ""
    data_vencimento_parcela_atual: str = ""
    data_pagamento: str = ""
    criterio_calculo: str = ""
    status_consulta: str = ""
    observacoes: str = ""
    data_hora_consulta: str = field(default_factory=lambda: datetime.now().strftime("%d/%m/%Y %H:%M:%S"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DebitoParcelado:
    cnpj: str = ""
    empresa: str = ""
    tipo_parcelamento: str = ""
    numero_protocolo: str = ""
    tributo: str = ""
    codigo_receita: str = ""
    pa_competencia: str = ""
    processo: str = ""
    valor_principal: str = ""
    multa: str = ""
    juros: str = ""
    total: str = ""
    situacao: str = ""
    observacoes: str = ""
    data_hora_consulta: str = field(default_factory=lambda: datetime.now().strftime("%d/%m/%Y %H:%M:%S"))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
