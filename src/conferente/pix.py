"""Pix "copia e cola" estático (BR Code), com valor e identificador da cobrança.

Segue o Manual de Padrões para Iniciação do Pix (Banco Central): campos no
formato EMV (ID de 2 dígitos + tamanho de 2 dígitos + valor), terminando com
CRC16-CCITT (polinômio 0x1021, valor inicial 0xFFFF).
"""

from __future__ import annotations

import re
import unicodedata
from decimal import Decimal


def _campo(id_: str, valor: str) -> str:
    if len(valor) > 99:
        raise ValueError(f"campo {id_} grande demais")
    return f"{id_}{len(valor):02d}{valor}"


def _sem_acento(texto: str) -> str:
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9 .\-]", "", t).strip()


def crc16(dados: str) -> str:
    crc = 0xFFFF
    for b in dados.encode():
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
            crc &= 0xFFFF
    return f"{crc:04X}"


def normalizar_chave(chave: str) -> str:
    """Telefone vira +55DDDNÚMERO; CPF/CNPJ só dígitos; e-mail e chave aleatória ficam como estão."""
    c = (chave or "").strip()
    if "@" in c:
        return c.lower()
    if re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", c):
        return c.lower()
    if c.startswith("+"):
        return "+" + re.sub(r"\D", "", c)
    return re.sub(r"\D", "", c)


def txid(referencia: str) -> str:
    """Identificador aceito pelo Pix: só letras e números, até 25 caracteres."""
    return re.sub(r"[^A-Za-z0-9]", "", referencia)[:25] or "***"


def copia_e_cola(chave: str, nome: str, cidade: str, valor: Decimal | None = None,
                 identificador: str = "***", descricao: str = "") -> str:
    conta = _campo("00", "br.gov.bcb.pix") + _campo("01", normalizar_chave(chave))
    if descricao:
        conta += _campo("02", _sem_acento(descricao)[:40])
    payload = (
        _campo("00", "01")
        + _campo("26", conta)
        + _campo("52", "0000")
        + _campo("53", "986")
        + (_campo("54", f"{valor:.2f}") if valor is not None else "")
        + _campo("58", "BR")
        + _campo("59", _sem_acento(nome)[:25] or "RECEBEDOR")
        + _campo("60", _sem_acento(cidade)[:15] or "BRASIL")
        + _campo("62", _campo("05", identificador))
        + "6304"
    )
    return payload + crc16(payload)
