"""Cobrança das mensalidades.

Cada mensalidade é um pagamento avulso (Pix, cartão ou boleto) que libera
30 dias de acesso. Dois provedores:

- **simulado** (padrão, sem configuração): uma tela interna com os botões
  "Aprovar" e "Recusar", para testar o fluxo sem dinheiro.
- **mercadopago**: Checkout Pro. Ativado quando MP_ACCESS_TOKEN está no .env.

O pagamento só é aceito depois de conferido direto na API do Mercado Pago
(referência, status e valor), nunca pelos parâmetros que voltam na URL.
"""

from __future__ import annotations

import json
import secrets
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from . import config
from .contas import Conta
from .db import transacao

API = "https://api.mercadopago.com"


class ErroPagamento(RuntimeError):
    pass


@dataclass
class Pagamento:
    id: int
    referencia: str
    conta_id: int
    plano: str
    valor: Decimal
    provedor: str
    provedor_id: str | None
    link: str | None
    status: str
    criado_em: str
    aprovado_em: str | None

    @classmethod
    def de_linha(cls, r) -> "Pagamento":
        return cls(r["id"], r["referencia"], r["conta_id"], r["plano"], Decimal(r["valor"]), r["provedor"],
                   r["provedor_id"], r["link"], r["status"], r["criado_em"], r["aprovado_em"])

    @property
    def nome_plano(self) -> str:
        return config.PLANOS[self.plano].nome


# ---------------------------------------------------------------- Mercado Pago


def _mp(metodo: str, caminho: str, corpo: dict | None = None, idempotencia: str | None = None) -> dict:
    req = urllib.request.Request(API + caminho, method=metodo)
    req.add_header("Authorization", f"Bearer {config.mp_token()}")
    req.add_header("Content-Type", "application/json")
    if idempotencia:
        req.add_header("X-Idempotency-Key", idempotencia)
    dados = json.dumps(corpo).encode() if corpo is not None else None
    try:
        with urllib.request.urlopen(req, dados, timeout=20) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detalhe = e.read().decode(errors="replace")[:300]
        if e.code == 401:
            raise ErroPagamento("O Mercado Pago recusou a chave de acesso (MP_ACCESS_TOKEN). Confira o .env.") from None
        raise ErroPagamento(f"Mercado Pago respondeu {e.code}: {detalhe}") from None
    except urllib.error.URLError as e:
        raise ErroPagamento(f"Sem conexão com o Mercado Pago ({e.reason}). Tente de novo.") from None


def _local(url: str) -> bool:
    host = urllib.parse.urlparse(url).hostname or ""
    return host in {"localhost", "127.0.0.1", "0.0.0.0"} or host.endswith(".local")


def _criar_preferencia(conta: Conta, plano: config.Plano, ref: str) -> tuple[str, str]:
    corpo = {
        "items": [{
            "id": plano.codigo,
            "title": f"Conferente - plano {plano.nome} (30 dias)",
            "quantity": 1,
            "unit_price": float(plano.preco),
            "currency_id": "BRL",
        }],
        "payer": {"email": conta.email, "name": conta.responsavel},
        "external_reference": ref,
        "statement_descriptor": "CONFERENTE",
        "expiration_date_to": (datetime.now(timezone.utc) + timedelta(days=3)).isoformat(timespec="milliseconds"),
        "expires": True,
    }
    base = config.base_url()
    if not _local(base):  # o Mercado Pago não aceita endereços locais para retorno
        corpo["back_urls"] = {s: f"{base}/pagamento/retorno" for s in ("success", "pending", "failure")}
        corpo["auto_return"] = "approved"
        corpo["notification_url"] = f"{base}/pagamento/notificacao"
    r = _mp("POST", "/checkout/preferences", corpo, idempotencia=ref)
    return r["id"], r["init_point"]


def _consultar_mp(ref: str, valor: Decimal) -> tuple[str, str | None]:
    """Devolve (status, id do pagamento aprovado) consultando a API pela referência."""
    q = urllib.parse.urlencode({"external_reference": ref, "sort": "date_created", "criteria": "desc"})
    r = _mp("GET", f"/v1/payments/search?{q}")
    status = "pendente"
    for p in r.get("results", []):
        if p.get("external_reference") != ref:
            continue
        if p.get("status") == "approved":
            pago = Decimal(str(p.get("transaction_amount", "0")))
            if pago + Decimal("0.01") >= valor and p.get("currency_id") == "BRL":
                return "aprovado", str(p["id"])
        elif p.get("status") in {"rejected", "cancelled"} and status == "pendente":
            status = "recusado"
        elif p.get("status") in {"in_process", "pending", "authorized"}:
            status = "pendente"
    return status, None


# ---------------------------------------------------------------- operações


def criar_cobranca(conta: Conta, codigo_plano: str) -> Pagamento:
    plano = config.PLANOS.get(codigo_plano)
    if plano is None:
        raise ErroPagamento("Plano desconhecido.")
    if plano.codigo == "fundador" and conta.plano != "fundador":
        from .contas import vagas_fundador_restantes
        if vagas_fundador_restantes() <= 0:
            raise ErroPagamento("As vagas do plano Fundador acabaram. Escolha outro plano.")
    ref = f"CF-{conta.id}-{secrets.token_hex(6)}"
    provedor = config.modo_pagamento()
    if provedor == "mercadopago":
        provedor_id, link = _criar_preferencia(conta, plano, ref)
    else:
        provedor_id, link = None, f"/pagamento/simulado/{ref}"
    with transacao() as con:
        con.execute(
            "INSERT INTO pagamentos (referencia, conta_id, plano, valor, provedor, provedor_id, link) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ref, conta.id, plano.codigo, str(plano.preco), provedor, provedor_id, link),
        )
    return obter(ref)


def obter(ref: str) -> Pagamento | None:
    with transacao() as con:
        r = con.execute("SELECT * FROM pagamentos WHERE referencia = ?", (ref,)).fetchone()
    return Pagamento.de_linha(r) if r else None


def da_conta(conta_id: int) -> list[Pagamento]:
    with transacao() as con:
        rs = con.execute("SELECT * FROM pagamentos WHERE conta_id = ? ORDER BY id DESC LIMIT 24", (conta_id,)).fetchall()
    return [Pagamento.de_linha(r) for r in rs]


def _aprovar(ref: str, provedor_id: str | None) -> bool:
    """Marca como aprovado e soma 30 dias. Idempotente: só vale na primeira vez."""
    with transacao() as con:
        cur = con.execute(
            "UPDATE pagamentos SET status = 'aprovado', aprovado_em = datetime('now'), "
            "provedor_id = COALESCE(?, provedor_id) WHERE referencia = ? AND status != 'aprovado'",
            (provedor_id, ref),
        )
        if cur.rowcount == 0:
            return False
        p = con.execute("SELECT conta_id, plano FROM pagamentos WHERE referencia = ?", (ref,)).fetchone()
        atual = date.fromisoformat(con.execute("SELECT ativo_ate FROM contas WHERE id = ?", (p["conta_id"],)).fetchone()[0])
        inicio = max(atual, date.today())  # renovação antecipada soma ao fim do período atual
        novo = inicio + timedelta(days=config.DIAS_POR_PAGAMENTO)
        con.execute("UPDATE contas SET plano = ?, ativo_ate = ? WHERE id = ?", (p["plano"], novo.isoformat(), p["conta_id"]))
        return True


def _marcar(ref: str, status: str) -> None:
    with transacao() as con:
        con.execute("UPDATE pagamentos SET status = ? WHERE referencia = ? AND status = 'pendente'", (status, ref))


def atualizar(ref: str) -> Pagamento | None:
    """Consulta o provedor e atualiza o pagamento. Devolve o pagamento atualizado."""
    p = obter(ref)
    if p is None or p.status == "aprovado":
        return p
    if p.provedor == "mercadopago":
        status, pid = _consultar_mp(ref, p.valor)
        if status == "aprovado":
            _aprovar(ref, pid)
        elif status == "recusado":
            _marcar(ref, "recusado")
    return obter(ref)


def simular(ref: str, aprovar: bool) -> Pagamento | None:
    p = obter(ref)
    if p is None or p.provedor != "simulado":
        return None
    if aprovar:
        _aprovar(ref, f"SIM-{secrets.token_hex(4)}")
    else:
        _marcar(ref, "recusado")
    return obter(ref)


def cancelar_pendentes(conta_id: int) -> None:
    with transacao() as con:
        con.execute("UPDATE pagamentos SET status = 'cancelado' WHERE conta_id = ? AND status = 'pendente'", (conta_id,))
