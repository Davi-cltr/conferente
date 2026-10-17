"""Configuração lida de configuracao.txt (ou .env) na raiz do projeto, ou de variáveis de ambiente.

Exemplo (veja configuracao-exemplo.txt):

    MP_ACCESS_TOKEN=APP_USR-...      # vazio = modo simulado, sem Mercado Pago
    BASE_URL=http://127.0.0.1:8000
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def _carregar_env(caminho: Path) -> None:
    if not caminho.is_file():
        return
    for linha in caminho.read_text(encoding="utf-8-sig")  # Bloco de Notas pode salvar com BOM.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        os.environ.setdefault(chave.strip(), valor.split(" #")[0].strip().strip('"').strip("'"))


_carregar_env(RAIZ / "configuracao.txt")
_carregar_env(RAIZ / ".env")


@dataclass(frozen=True)
class Plano:
    codigo: str
    nome: str
    preco: Decimal
    cnpjs: int
    destaque: str = ""


PLANOS: dict[str, Plano] = {
    p.codigo: p
    for p in (
        Plano("fundador", "Fundador", Decimal("300.00"), 150, "Preço travado por 12 meses · 20 vagas"),
        Plano("essencial", "Essencial", Decimal("290.00"), 50),
        Plano("escritorio", "Escritório", Decimal("490.00"), 150),
        Plano("ampliado", "Ampliado", Decimal("890.00"), 400),
    )
}
VAGAS_FUNDADOR = 20
DIAS_POR_PAGAMENTO = 30
DIAS_TESTE = int(os.environ.get("DIAS_TESTE", "14"))
CNPJS_TESTE = 10


def mp_token() -> str:
    return os.environ.get("MP_ACCESS_TOKEN", "").strip()


def base_url() -> str:
    return os.environ.get("BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def caminho_banco() -> Path:
    p = Path(os.environ.get("CONFERENTE_DB", RAIZ / "dados" / "conferente.db"))
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def modo_pagamento() -> str:
    return "mercadopago" if mp_token() else "simulado"
