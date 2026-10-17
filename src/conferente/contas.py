"""Contas de escritório: cadastro, senha, sessão e situação da assinatura."""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from . import config
from .db import transacao

SESSAO_DIAS = 30


def _agora() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ---------------------------------------------------------------- validações


def so_digitos(texto: str) -> str:
    return re.sub(r"\D", "", texto or "")


def cnpj_valido(cnpj: str) -> bool:
    d = so_digitos(cnpj)
    if len(d) != 14 or d == d[0] * 14:
        return False

    def digito(base: str, pesos: list[int]) -> str:
        r = sum(int(n) * p for n, p in zip(base, pesos)) % 11
        return "0" if r < 2 else str(11 - r)

    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    dv1 = digito(d[:12], p1)
    dv2 = digito(d[:12] + dv1, [6] + p1)
    return d[12:] == dv1 + dv2


def email_valido(email: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email or "")) and len(email) <= 200


# ---------------------------------------------------------------- senha


def hash_senha(senha: str) -> str:
    sal = secrets.token_bytes(16)
    h = hashlib.scrypt(senha.encode(), salt=sal, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$" + base64.b64encode(sal).decode() + "$" + base64.b64encode(h).decode()


def confere_senha(senha: str, guardado: str) -> bool:
    try:
        _, sal, h = guardado.split("$")
        calc = hashlib.scrypt(senha.encode(), salt=base64.b64decode(sal), n=2**14, r=8, p=1, dklen=32)
        return hmac.compare_digest(calc, base64.b64decode(h))
    except Exception:
        return False


# ---------------------------------------------------------------- conta


@dataclass
class Conta:
    id: int
    escritorio: str
    cnpj: str
    responsavel: str
    email: str
    whatsapp: str
    plano: str
    ativo_ate: date

    @classmethod
    def de_linha(cls, r) -> "Conta":
        return cls(r["id"], r["escritorio"], r["cnpj"], r["responsavel"], r["email"], r["whatsapp"],
                   r["plano"], date.fromisoformat(r["ativo_ate"]))

    @property
    def ativa(self) -> bool:
        return self.ativo_ate >= date.today()

    @property
    def dias_restantes(self) -> int:
        return (self.ativo_ate - date.today()).days

    @property
    def em_teste(self) -> bool:
        return self.plano == "teste"

    @property
    def nome_plano(self) -> str:
        return "Teste grátis" if self.em_teste else config.PLANOS[self.plano].nome

    @property
    def limite_cnpjs(self) -> int:
        return config.CNPJS_TESTE if self.em_teste else config.PLANOS[self.plano].cnpjs


class ErroCadastro(ValueError):
    pass


def criar_conta(escritorio, cnpj, responsavel, email, whatsapp, senha) -> Conta:
    escritorio, responsavel = (escritorio or "").strip(), (responsavel or "").strip()
    email = (email or "").strip().lower()
    cnpj = so_digitos(cnpj)
    if not escritorio or len(escritorio) > 120:
        raise ErroCadastro("Informe o nome do escritório.")
    if not cnpj_valido(cnpj):
        raise ErroCadastro("O CNPJ informado não é válido. Confira os números.")
    if not responsavel or len(responsavel) > 120:
        raise ErroCadastro("Informe o nome do responsável.")
    if not email_valido(email):
        raise ErroCadastro("Informe um e-mail válido.")
    if len(senha or "") < 8:
        raise ErroCadastro("A senha precisa ter pelo menos 8 caracteres.")
    ativo_ate = date.today() + timedelta(days=config.DIAS_TESTE)
    with transacao() as con:
        if con.execute("SELECT 1 FROM contas WHERE email = ?", (email,)).fetchone():
            raise ErroCadastro("Já existe uma conta com este e-mail. Use “Entrar”.")
        cur = con.execute(
            "INSERT INTO contas (escritorio, cnpj, responsavel, email, whatsapp, senha_hash, ativo_ate) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (escritorio, cnpj, responsavel, email, so_digitos(whatsapp)[:13], hash_senha(senha), ativo_ate.isoformat()),
        )
        return obter(cur.lastrowid, con)


def obter(conta_id: int, con=None) -> Conta | None:
    if con is None:
        with transacao() as c:
            return obter(conta_id, c)
    r = con.execute("SELECT * FROM contas WHERE id = ?", (conta_id,)).fetchone()
    return Conta.de_linha(r) if r else None


def autenticar(email: str, senha: str) -> Conta | None:
    with transacao() as con:
        r = con.execute("SELECT * FROM contas WHERE email = ?", ((email or "").strip().lower(),)).fetchone()
    if r is None:
        confere_senha(senha or "", hash_senha("x"))  # tempo parecido com o de uma conta existente
        return None
    return Conta.de_linha(r) if confere_senha(senha or "", r["senha_hash"]) else None


# ---------------------------------------------------------------- sessão


def abrir_sessao(conta_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expira = _agora() + timedelta(days=SESSAO_DIAS)
    with transacao() as con:
        con.execute("DELETE FROM sessoes WHERE expira_em < ?", (_agora().isoformat(),))
        con.execute("INSERT INTO sessoes VALUES (?, ?, ?)", (token, conta_id, expira.isoformat()))
    return token


def conta_da_sessao(token: str | None) -> Conta | None:
    if not token:
        return None
    with transacao() as con:
        r = con.execute(
            "SELECT c.* FROM sessoes s JOIN contas c ON c.id = s.conta_id WHERE s.token = ? AND s.expira_em > ?",
            (token, _agora().isoformat()),
        ).fetchone()
    return Conta.de_linha(r) if r else None


def fechar_sessao(token: str | None) -> None:
    if token:
        with transacao() as con:
            con.execute("DELETE FROM sessoes WHERE token = ?", (token,))


def vagas_fundador_restantes() -> int:
    with transacao() as con:
        n = con.execute("SELECT COUNT(*) FROM contas WHERE plano = 'fundador'").fetchone()[0]
    return max(0, config.VAGAS_FUNDADOR - n)


def todas() -> list[Conta]:
    with transacao() as con:
        rs = con.execute("SELECT * FROM contas ORDER BY id DESC").fetchall()
    return [Conta.de_linha(r) for r in rs]
