"""Aplicação web: site, cadastro, conta, pagamento e conferência.

Os XMLs enviados são lidos em memória e descartados ao fim da requisição.
Contas e pagamentos ficam no SQLite local (dados/conferente.db).
"""

from __future__ import annotations

import json
import urllib.parse
from contextlib import asynccontextmanager
from decimal import Decimal, InvalidOperation

from fastapi import FastAPI, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse

from .. import __version__, config, contas, db, pagamentos
from ..parser import ler_lote
from ..relatorio import _env, gerar_html, processar

LIMITE_ARQUIVOS = 3000
LIMITE_TOTAL = 200 * 1024 * 1024
COOKIE = "conferente_sessao"


@asynccontextmanager
async def _ciclo(app):
    db.iniciar()
    yield


app = FastAPI(title="Conferente", version=__version__, docs_url=None, redoc_url=None, lifespan=_ciclo)


# ---------------------------------------------------------------- utilidades


def _conta(request: Request):
    return contas.conta_da_sessao(request.cookies.get(COOKIE))


def _pagina(nome: str, request: Request, status: int = 200, **ctx) -> HTMLResponse:
    ctx.setdefault("conta", _conta(request))
    ctx.update(modo=config.modo_pagamento(), versao=__version__, dias_teste=config.DIAS_TESTE,
               cnpjs_teste=config.CNPJS_TESTE)
    return HTMLResponse(_env.get_template(nome).render(**ctx), status_code=status)


def _ir(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def _com_sessao(resp: RedirectResponse, token: str) -> RedirectResponse:
    resp.set_cookie(COOKIE, token, max_age=contas.SESSAO_DIAS * 86400, httponly=True, samesite="lax",
                    secure=config.base_url().startswith("https://"))
    return resp


def _pagamento_da_conta(ref: str, conta) -> pagamentos.Pagamento | None:
    p = pagamentos.obter(ref)
    return p if (p and conta and p.conta_id == conta.id) else None


# ---------------------------------------------------------------- site e acesso


@app.get("/", response_class=HTMLResponse)
def site(request: Request):
    return _pagina("site.html", request, planos=list(config.PLANOS.values()),
                   vagas_fundador=contas.vagas_fundador_restantes())


@app.get("/saude", response_class=PlainTextResponse)
def saude():
    return "ok"


@app.get("/cadastro", response_class=HTMLResponse)
def cadastro_form(request: Request, plano: str = ""):
    if _conta(request):
        return _ir("/conta")
    return _pagina("cadastro.html", request, erro=None, dados={}, plano=plano if plano in config.PLANOS else "")


@app.post("/cadastro")
def cadastro(request: Request, escritorio: str = Form(""), cnpj: str = Form(""), responsavel: str = Form(""),
             email: str = Form(""), whatsapp: str = Form(""), senha: str = Form(""), plano: str = Form("")):
    try:
        conta = contas.criar_conta(escritorio, cnpj, responsavel, email, whatsapp, senha)
    except contas.ErroCadastro as e:
        dados = dict(escritorio=escritorio, cnpj=cnpj, responsavel=responsavel, email=email, whatsapp=whatsapp)
        return _pagina("cadastro.html", request, status=400, erro=str(e), dados=dados, plano=plano)
    destino = "/conta?bemvindo=1" + (f"&plano={plano}" if plano in config.PLANOS else "")
    return _com_sessao(_ir(destino), contas.abrir_sessao(conta.id))


@app.get("/entrar", response_class=HTMLResponse)
def entrar_form(request: Request):
    if _conta(request):
        return _ir("/conta")
    return _pagina("entrar.html", request, erro=None, email="")


@app.post("/entrar")
def entrar(request: Request, email: str = Form(""), senha: str = Form("")):
    conta = contas.autenticar(email, senha)
    if conta is None:
        return _pagina("entrar.html", request, status=400, erro="E-mail ou senha incorretos.", email=email)
    return _com_sessao(_ir("/conta" if not conta.ativa else "/app"), contas.abrir_sessao(conta.id))


@app.post("/sair")
def sair(request: Request):
    contas.fechar_sessao(request.cookies.get(COOKIE))
    resp = _ir("/")
    resp.delete_cookie(COOKIE)
    return resp


# ---------------------------------------------------------------- conta e pagamento


@app.get("/conta", response_class=HTMLResponse)
def conta_pagina(request: Request, bemvindo: int = 0, plano: str = "", resultado: str = "", erro: str = ""):
    conta = _conta(request)
    if conta is None:
        return _ir("/entrar")
    lista = pagamentos.da_conta(conta.id)
    pendente = next((p for p in lista if p.status == "pendente"), None)
    if pendente and pendente.provedor == "mercadopago":
        try:
            pendente = pagamentos.atualizar(pendente.referencia)
            if pendente.status != "pendente":
                return _ir(f"/conta?resultado={pendente.status}")
        except pagamentos.ErroPagamento:
            pass
    msgs = []
    if bemvindo:
        msgs.append(("ok", f"Conta criada. Você tem {config.DIAS_TESTE} dias grátis para conferir notas de até "
                           f"{config.CNPJS_TESTE} clientes."))
    if resultado == "aprovado":
        msgs.append(("ok", f"Pagamento aprovado. Seu acesso vai até {conta.ativo_ate:%d/%m/%Y}."))
    elif resultado == "recusado":
        msgs.append(("erro", "O pagamento foi recusado. Tente de novo ou use outra forma de pagamento."))
    elif resultado == "pendente":
        msgs.append(("aviso", "Ainda não recebemos a confirmação deste pagamento. Pix costuma confirmar em segundos; boleto, em até 2 dias úteis."))
    if erro:
        msgs.append(("erro", erro[:300]))
    if not conta.ativa:
        msgs.append(("aviso", "Seu acesso venceu. Escolha um plano abaixo para continuar conferindo notas."))
    return _pagina("conta.html", request, conta=conta, mensagens=msgs, pagamentos=lista,
                   pendente=pendente if pendente and pendente.status == "pendente" else None,
                   planos=list(config.PLANOS.values()), vagas_fundador=contas.vagas_fundador_restantes(),
                   sugerido=plano if plano in config.PLANOS else ("" if not conta.em_teste else "fundador"))


@app.post("/assinar")
def assinar(request: Request, plano: str = Form("")):
    conta = _conta(request)
    if conta is None:
        return _ir("/entrar")
    pagamentos.cancelar_pendentes(conta.id)
    try:
        p = pagamentos.criar_cobranca(conta, plano)
    except pagamentos.ErroPagamento as e:
        return _ir("/conta?erro=" + urllib.parse.quote(str(e)))
    return _ir(p.link if p.provedor == "simulado" else "/conta")


@app.get("/pagamento/{ref}/situacao")
def situacao(request: Request, ref: str):
    p = _pagamento_da_conta(ref, _conta(request))
    if p is None:
        return JSONResponse({"erro": "não encontrado"}, status_code=404)
    try:
        p = pagamentos.atualizar(ref)
    except pagamentos.ErroPagamento:
        pass
    return {"status": p.status}


@app.post("/pagamento/{ref}/verificar")
def verificar(request: Request, ref: str):
    p = _pagamento_da_conta(ref, _conta(request))
    if p is None:
        return _ir("/conta")
    try:
        p = pagamentos.atualizar(ref)
    except pagamentos.ErroPagamento as e:
        return _ir("/conta?erro=" + urllib.parse.quote(str(e)))
    return _ir(f"/conta?resultado={p.status}")


@app.post("/pagamento/{ref}/cancelar")
def cancelar(request: Request, ref: str):
    conta = _conta(request)
    if _pagamento_da_conta(ref, conta):
        pagamentos.cancelar_pendentes(conta.id)
    return _ir("/conta")


@app.get("/pagamento/retorno")
def retorno(request: Request, external_reference: str = ""):
    """Volta do Mercado Pago (só quando o sistema está num endereço público)."""
    if external_reference:
        try:
            pagamentos.atualizar(external_reference)
        except pagamentos.ErroPagamento:
            pass
        p = pagamentos.obter(external_reference)
        if p:
            return _ir(f"/conta?resultado={p.status}")
    return _ir("/conta")


@app.post("/pagamento/notificacao")
async def notificacao(request: Request):
    """Aviso do Mercado Pago. Não confia no conteúdo: busca o pagamento na API e confere."""
    try:
        corpo = json.loads((await request.body()) or b"{}")
        pid = str((corpo.get("data") or {}).get("id") or request.query_params.get("data.id") or "")
        if pid.isdigit() and config.modo_pagamento() == "mercadopago":
            info = pagamentos._mp("GET", f"/v1/payments/{pid}")
            ref = info.get("external_reference")
            if ref and pagamentos.obter(ref):
                pagamentos.atualizar(ref)
    except Exception:
        pass
    return PlainTextResponse("ok")


@app.get("/pagamento/simulado/{ref}", response_class=HTMLResponse)
def simulado_form(request: Request, ref: str):
    p = _pagamento_da_conta(ref, _conta(request))
    if p is None or p.provedor != "simulado":
        return _ir("/conta")
    return _pagina("simulado.html", request, pagamento=p)


@app.post("/pagamento/simulado/{ref}")
def simulado(request: Request, ref: str, acao: str = Form("")):
    p = _pagamento_da_conta(ref, _conta(request))
    if p is None or p.provedor != "simulado" or config.modo_pagamento() != "simulado":
        return _ir("/conta")
    p = pagamentos.simular(ref, aprovar=(acao == "aprovar"))
    return _ir(f"/conta?resultado={p.status}")


# ---------------------------------------------------------------- conferência


@app.get("/app", response_class=HTMLResponse)
def app_pagina(request: Request):
    conta = _conta(request)
    if conta is None:
        return _ir("/entrar")
    if not conta.ativa:
        return _ir("/conta")
    return _pagina("upload.html", request, conta=conta, erro=None)


@app.post("/conferir", response_class=HTMLResponse)
async def conferir(request: Request, arquivos: list[UploadFile], cbs_2027: str = Form("")):
    conta = _conta(request)
    if conta is None:
        return _ir("/entrar")
    if not conta.ativa:
        return _ir("/conta")

    def erro(msg: str, status: int = 400):
        return _pagina("upload.html", request, status=status, conta=conta, erro=msg)

    if len(arquivos) > LIMITE_ARQUIVOS:
        return erro(f"Envie no máximo {LIMITE_ARQUIVOS} arquivos por vez (ou junte-os em um .zip).")
    pCBS = None
    if cbs_2027.strip():
        try:
            pCBS = Decimal(cbs_2027.replace(",", ".").replace("%", "").strip())
        except InvalidOperation:
            return erro("A alíquota da CBS precisa ser um número, por exemplo 8,8.")
        if not (0 <= pCBS <= 30):
            return erro("A alíquota da CBS deve estar entre 0 e 30%.")

    lidos, total = [], 0
    for f in arquivos:
        dados = await f.read()
        total += len(dados)
        if total > LIMITE_TOTAL:
            return erro("O envio passou de 200 MB. Divida em lotes menores.", 413)
        lidos.append((f.filename or "sem-nome.xml", dados))

    notas, erros = ler_lote(lidos)
    if not notas:
        return erro("Nenhuma NF-e válida foi encontrada nos arquivos enviados.")
    clientes = {n.emitente_cnpj for n in notas}
    if len(clientes) > conta.limite_cnpjs:
        return erro(f"Este lote tem notas de {len(clientes)} clientes, e o seu plano confere até "
                    f"{conta.limite_cnpjs} por vez. Divida o lote ou mude de plano em Minha conta.")
    return gerar_html(processar(notas, erros, pCBS=pCBS), conta.escritorio, voltar="/app")
