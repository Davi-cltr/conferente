"""Versão web mínima: o escritório envia os XMLs e recebe o relatório.

Nada é gravado em disco: os arquivos são lidos em memória e descartados
ao fim da requisição (menos dado guardado = menos risco de LGPD).
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fastapi import FastAPI, Form, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse

from .. import __version__
from ..parser import ler_lote
from ..relatorio import _env, gerar_html, processar

LIMITE_ARQUIVOS = 3000
LIMITE_TOTAL = 200 * 1024 * 1024

app = FastAPI(title="Conferente", version=__version__, docs_url=None, redoc_url=None)


@app.get("/", response_class=HTMLResponse)
def inicio():
    return _env.get_template("upload.html").render(versao=__version__, erro=None)


@app.get("/saude", response_class=PlainTextResponse)
def saude():
    return "ok"


@app.post("/conferir", response_class=HTMLResponse)
async def conferir(arquivos: list[UploadFile], escritorio: str = Form(""), cbs_2027: str = Form("")):
    def erro(msg: str, status: int = 400):
        return HTMLResponse(_env.get_template("upload.html").render(versao=__version__, erro=msg), status_code=status)

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
    return gerar_html(processar(notas, erros, pCBS=pCBS), escritorio.strip()[:120])
