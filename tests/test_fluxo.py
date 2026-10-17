"""Fluxo completo no modo simulado: site → cadastro → pagamento → conferência."""

from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

AMOSTRAS = Path(__file__).parent / "amostras"
CNPJ_OK = "11.222.333/0001-81"


@pytest.fixture()
def cliente(tmp_path, monkeypatch):
    monkeypatch.setenv("CONFERENTE_DB", str(tmp_path / "teste.db"))
    monkeypatch.setenv("MP_ACCESS_TOKEN", "")
    from conferente.web.app import app
    with TestClient(app) as c:
        yield c


def cadastrar(c, email="ana@contabil.com.br", **extra):
    dados = dict(escritorio="Contábil Teste", cnpj=CNPJ_OK, responsavel="Ana", email=email,
                 whatsapp="19999999999", senha="senha-forte-1", **extra)
    return c.post("/cadastro", data=dados, follow_redirects=False)


def xmls():
    return [("arquivos", (p.name, p.read_bytes(), "text/xml")) for p in sorted(AMOSTRAS.glob("*.xml"))]


def test_cnpj():
    from conferente.contas import cnpj_valido
    assert cnpj_valido(CNPJ_OK) and not cnpj_valido("11.222.333/0001-82") and not cnpj_valido("11111111111111")


def test_site_e_paginas_publicas(cliente):
    r = cliente.get("/")
    assert r.status_code == 200 and "Planos" in r.text and "Fundador" in r.text
    assert cliente.get("/cadastro").status_code == 200
    assert cliente.get("/entrar").status_code == 200
    assert cliente.get("/app", follow_redirects=False).headers["location"] == "/entrar"


def test_cadastro_invalido(cliente):
    r = cliente.post("/cadastro", data=dict(escritorio="X", cnpj="123", responsavel="A",
                                             email="a@b.com", senha="12345678"))
    assert r.status_code == 400 and "CNPJ" in r.text
    r = cadastrar(cliente)
    cliente.post("/sair")
    r = cadastrar(cliente)
    assert r.status_code == 400 and "Já existe" in r.text


def test_fluxo_completo(cliente):
    r = cadastrar(cliente, plano="escritorio")
    assert r.status_code == 303 and r.headers["location"].startswith("/conta?bemvindo=1")
    conta = cliente.get("/conta")
    assert "Teste grátis" in conta.text and "Escolha seu plano" in conta.text

    # período de teste: confere até 10 clientes
    r = cliente.post("/conferir", files=xmls(), data={"cbs_2027": "8,8"})
    assert r.status_code == 200 and "Simulação 2027" in r.text

    # pagamento recusado não muda nada
    r = cliente.post("/assinar", data={"plano": "escritorio"}, follow_redirects=False)
    link = r.headers["location"]
    assert link.startswith("/pagamento/simulado/CF-")
    ref = link.rsplit("/", 1)[1]
    assert "Pagamento em andamento" in cliente.get("/conta").text
    assert cliente.get(f"/pagamento/{ref}/situacao").json() == {"status": "pendente"}
    r = cliente.post(link, data={"acao": "recusar"}, follow_redirects=False)
    assert r.headers["location"] == "/conta?resultado=recusado"
    assert "Recusado" in cliente.get("/conta?resultado=recusado").text

    # pagamento aprovado: plano muda e soma 30 dias ao fim do teste
    from conferente import contas
    antes = contas.autenticar("ana@contabil.com.br", "senha-forte-1").ativo_ate
    link = cliente.post("/assinar", data={"plano": "escritorio"}, follow_redirects=False).headers["location"]
    r = cliente.post(link, data={"acao": "aprovar"}, follow_redirects=False)
    assert r.headers["location"] == "/conta?resultado=aprovado"
    depois = contas.autenticar("ana@contabil.com.br", "senha-forte-1")
    assert depois.plano == "escritorio" and depois.ativo_ate == antes + timedelta(days=30)
    pagina = cliente.get("/conta?resultado=aprovado").text
    assert "Pagamento aprovado" in pagina and "Pago" in pagina

    # aprovar de novo não soma outra vez
    cliente.post(link, data={"acao": "aprovar"})
    assert contas.autenticar("ana@contabil.com.br", "senha-forte-1").ativo_ate == depois.ativo_ate


def test_acesso_vencido_bloqueia_conferencia(cliente):
    cadastrar(cliente)
    from conferente.db import transacao
    with transacao() as con:
        con.execute("UPDATE contas SET ativo_ate = ?", ((date.today() - timedelta(days=1)).isoformat(),))
    assert cliente.get("/app", follow_redirects=False).headers["location"] == "/conta"
    r = cliente.post("/conferir", files=xmls(), follow_redirects=False)
    assert r.headers["location"] == "/conta"
    assert "Seu acesso venceu" in cliente.get("/conta").text


def test_outra_conta_nao_ve_pagamento(cliente):
    cadastrar(cliente)
    link = cliente.post("/assinar", data={"plano": "essencial"}, follow_redirects=False).headers["location"]
    ref = link.rsplit("/", 1)[1]
    cliente.post("/sair")
    cadastrar(cliente, email="outro@x.com.br")
    assert cliente.get(f"/pagamento/{ref}/situacao").status_code == 404
    r = cliente.post(link, data={"acao": "aprovar"}, follow_redirects=False)
    assert r.headers["location"] == "/conta"


def test_login(cliente):
    cadastrar(cliente)
    cliente.post("/sair")
    r = cliente.post("/entrar", data={"email": "ana@contabil.com.br", "senha": "errada!!"})
    assert r.status_code == 400 and "incorretos" in r.text
    r = cliente.post("/entrar", data={"email": "ANA@contabil.com.br", "senha": "senha-forte-1"}, follow_redirects=False)
    assert r.headers["location"] == "/app"


def test_mercadopago_confere_valor(monkeypatch, tmp_path):
    """O pagamento só é aceito se a API do Mercado Pago confirmar referência, status e valor."""
    monkeypatch.setenv("CONFERENTE_DB", str(tmp_path / "mp.db"))
    monkeypatch.setenv("MP_ACCESS_TOKEN", "APP_USR-teste")
    from conferente import contas, db, pagamentos
    db.iniciar()
    conta = contas.criar_conta("Esc", CNPJ_OK, "Ana", "mp@x.com.br", "", "senha-forte-1")
    chamadas = []

    def falso(metodo, caminho, corpo=None, idempotencia=None):
        chamadas.append((metodo, caminho, corpo))
        if caminho == "/checkout/preferences":
            assert "back_urls" not in corpo  # endereço local: sem retorno automático
            return {"id": "PREF1", "init_point": "https://www.mercadopago.com.br/checkout/v1/redirect?pref_id=PREF1"}
        ref = caminho.split("external_reference=")[1].split("&")[0]
        return {"results": [{"id": 1, "external_reference": ref, "status": "approved",
                             "transaction_amount": valor_pago, "currency_id": "BRL"}]}

    monkeypatch.setattr(pagamentos, "_mp", falso)
    valor_pago = 1.00  # pago a menos: não libera
    p = pagamentos.criar_cobranca(conta, "essencial")
    assert p.link.startswith("https://www.mercadopago.com.br/")
    assert pagamentos.atualizar(p.referencia).status == "pendente"
    valor_pago = 290.00
    assert pagamentos.atualizar(p.referencia).status == "aprovado"
    assert contas.obter(conta.id).plano == "essencial"
