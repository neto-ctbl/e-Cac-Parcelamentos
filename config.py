from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
INPUT_FILE = Path(os.getenv("INPUT_FILE", "cnpjs.csv"))
if not INPUT_FILE.is_absolute():
    INPUT_FILE = BASE_DIR / INPUT_FILE

OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "saida"))
if not OUTPUT_DIR.is_absolute():
    OUTPUT_DIR = BASE_DIR / OUTPUT_DIR
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BROWSER_CHANNEL = os.getenv("BROWSER_CHANNEL", "chrome") or None
HEADLESS = os.getenv("HEADLESS", "false").strip().lower() in {"1", "true", "sim", "yes"}
SLOW_MO_MS = int(os.getenv("SLOW_MO_MS", "80"))
USER_DATA_DIR = Path(os.getenv("USER_DATA_DIR", ".pw-user-data"))
if not USER_DATA_DIR.is_absolute():
    USER_DATA_DIR = BASE_DIR / USER_DATA_DIR

MANUAL_CAPTCHA = os.getenv("MANUAL_CAPTCHA", "true").strip().lower() in {"1", "true", "sim", "yes"}
MANUAL_CERTIFICATE = os.getenv("MANUAL_CERTIFICATE", "true").strip().lower() in {"1", "true", "sim", "yes"}
TIMEOUT_MS = int(os.getenv("TIMEOUT_MS", "30000"))

ECAC_URL = "https://cav.receita.fazenda.gov.br/autenticacao/login"

STATUS_INATIVOS = [
    "encerrado", "encerrada", "encerrado por rescisão", "encerrado por rescisao",
    "encerrado a pedido", "não validado", "nao validado", "cancelado", "cancelada",
    "rescindido", "rescindida", "indeferido", "indeferida", "liquidado", "liquidada",
    "finalizado", "finalizada", "inativo", "inativa",
]
STATUS_ATIVOS = ["em parcelamento", "ativo", "ativa", "operante"]

@dataclass(frozen=True)
class ConsultaSimples:
    tipo: str
    id_aplicacao: str
    mensagem_sem_pedido: str

CONSULTAS_SIMPLES_ECAC = [
    ConsultaSimples(
        tipo="Parcelamento Simples Nacional",
        id_aplicacao="188",
        mensagem_sem_pedido="Não existe pedido de parcelamento para esse CNPJ.",
    ),
    ConsultaSimples(
        tipo="PERT-SN",
        id_aplicacao="10011",
        mensagem_sem_pedido="Não existe pedido de parcelamento PERT-SN para esse CNPJ.",
    ),
    ConsultaSimples(
        tipo="RELP-SN",
        id_aplicacao="10036",
        mensagem_sem_pedido="Não existe pedido de parcelamento RELP-SN para esse CNPJ.",
    ),
]
