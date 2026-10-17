"""Casos de borda de cada parte do sistema (auditoria de 17/10/2026)."""

import io
import json
import zipfile
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conferente.cli import main
from conferente.parser import ler_lote, ler_nota
from conferente.regras import conferir
from conferente.relatorio import gerar_html, processar

AMOSTRAS = Path(__file__).parent / "amostras"
NS = 'xmlns="http://www.portalfiscal.inf.br/nfe"'


def nota_xml(mod="55", crt="3", data="2026-09-10T10:00:00-03:00", dest=True, itens="", raiz_proc=True,
             chave="35260911222333000181550010000000011000000010", xprod="Produto", encoding="UTF-8"):
    det = itens or (f'<det nItem="1"><prod><cProd>1</cProd><xProd>{xprod}</xProd><NCM>22021000</NCM><CFOP>5102</CFOP>'
                    "<vProd>10.00</vProd></prod><imposto><IBSCBS><CST>000</CST><cClassTrib>000001</cClassTrib>"
                    "<gIBSCBS><vBC>10.00</vBC><gIBSUF><pIBSUF>0.1000</pIBSUF><vIBSUF>0.01</vIBSUF></gIBSUF>"
                    "<gIBSMun><pIBSMun>0.0000</pIBSMun><vIBSMun>0.00</vIBSMun></gIBSMun><vIBS>0.01</vIBS>"
                    "<gCBS><pCBS>0.9000</pCBS><vCBS>0.09</vCBS></gCBS></gIBSCBS></IBSCBS></imposto></det>")
    d = "<dest><CNPJ>99888777000166</CNPJ><xNome>Cliente</xNome></dest>" if dest else ""
    tag_data = f"<dhEmi>{data}</dhEmi>" if "T" in data else f"<dEmi>{data}</dEmi>"
    nfe = (f'<NFe {NS}><infNFe Id="NFe{chave}" versao="4.00"><ide><mod>{mod}</mod><serie>1</serie><nNF>1</nNF>{tag_data}</ide>'
           f"<emit><CNPJ>11222333000181</CNPJ><xNome>Loja</xNome><enderEmit><UF>SP</UF></enderEmit><CRT>{crt}</CRT></emit>{d}"
           f"{det}<total><ICMSTot><vNF>10.00</vNF></ICMSTot><IBSCBSTot><vBCIBSCBS>10.00</vBCIBSCBS><gIBS><vIBS>0.01</vIBS></gIBS>"
           "<gCBS><vCBS>0.09</vCBS></gCBS></IBSCBSTot></total></infNFe></NFe>")
    corpo = f'<nfeProc {NS} versao="4.00">{nfe}</nfeProc>' if raiz_proc else nfe
    return f'<?xml version="1.0" encoding="{encoding}"?>{corpo}'.encode(encoding.lower().replace("iso-8859-1", "latin-1"))


# ---------------------------------------------------------------- parser


def test_nfce_sem_destinatario_e_sem_nfeproc():
    n = ler_nota(nota_xml(mod="65", dest=False, raiz_proc=False))
    assert n.modelo == "65" and n.destinatario_doc == "" and conferir([n]) == []


def test_encoding_latin1_e_data_antiga():
    n = ler_nota(nota_xml(xprod="Açúcar", encoding="ISO-8859-1", data="2026-09-10"))
    assert n.itens[0].descricao == "Açúcar" and n.emissao == date(2026, 9, 10)


def test_evento_nao_e_nota():
    with pytest.raises(ValueError, match="não é uma NF-e"):
        ler_nota(b'<?xml version="1.0"?><procEventoNFe><evento/></procEventoNFe>')


def test_zip_com_pastas_e_arquivos_estranhos():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("janeiro/a.xml", nota_xml())
        z.writestr("janeiro/leia-me.txt", "nada")
        z.writestr("fevereiro/b.xml", nota_xml(chave="35260911222333000181550010000000021000000020"))
    notas, erros = ler_lote([("lote.zip", buf.getvalue())])
    assert len(notas) == 2 and erros == []


def test_zip_corrompido_e_duplicadas():
    notas, erros = ler_lote([("x.zip", b"PK nao e zip"), ("a.xml", nota_xml()), ("b.xml", nota_xml())])
    assert len(notas) == 1
    assert {e.motivo for e in erros} >= {"nota duplicada no lote (mesma chave)"}
    assert any(e.arquivo == "x.zip" for e in erros)


def test_arquivo_vazio():
    notas, erros = ler_lote([("vazio.xml", b"")])
    assert notas == [] and len(erros) == 1


# ---------------------------------------------------------------- regras


def test_simples_2027_sem_grupo_e_erro():
    item = ('<det nItem="1"><prod><cProd>1</cProd><xProd>Pao</xProd><NCM>19059090</NCM><CFOP>5102</CFOP>'
            "<vProd>10.00</vProd></prod><imposto/></det>")
    n = ler_nota(nota_xml(crt="1", data="2027-01-10T10:00:00-03:00", itens=item))
    a = conferir([n])
    assert [(x.codigo, x.severidade.value) for x in a] == [("CF001", "erro")]


def test_nota_2025_sem_grupo_e_so_informativa():
    item = ('<det nItem="1"><prod><cProd>1</cProd><xProd>X</xProd><NCM>1</NCM><CFOP>5102</CFOP>'
            "<vProd>10.00</vProd></prod><imposto/></det>")
    n = ler_nota(nota_xml(data="2025-12-10T10:00:00-03:00", itens=item))
    assert [(x.codigo, x.severidade.value) for x in conferir([n])] == [("CF001", "info")]


def test_nota_2027_sem_aliquota_cbs_definida_nao_quebra():
    n = ler_nota(nota_xml(data="2027-02-10T10:00:00-03:00"))
    codigos = [a.codigo for a in conferir([n])]
    assert "CF020" in codigos  # IBS de 2027 é 0,05% + 0,05%; a nota usa 0,1% + 0%


def test_isento_sem_valores_nao_gera_achado():
    item = ('<det nItem="1"><prod><cProd>1</cProd><xProd>Livro</xProd><NCM>49019900</NCM><CFOP>5102</CFOP>'
            "<vProd>10.00</vProd></prod><imposto><IBSCBS><CST>410</CST><cClassTrib>410008</cClassTrib></IBSCBS></imposto></det>")
    xml = nota_xml(itens=item).replace(b"<IBSCBSTot><vBCIBSCBS>10.00</vBCIBSCBS><gIBS><vIBS>0.01</vIBS></gIBS><gCBS><vCBS>0.09</vCBS></gCBS></IBSCBSTot>", b"")
    assert conferir([ler_nota(xml)]) == []


def test_relatorio_escapa_html_dos_xmls():
    n = ler_nota(nota_xml(xprod="&lt;script&gt;alert(1)&lt;/script&gt;", crt="9"))
    html = gerar_html(processar([n], []), "<b>Escritório</b>")
    assert "<script>alert(1)" not in html and "&lt;b&gt;Escritório" in html


def test_relatorio_lote_vazio_nao_quebra():
    html = gerar_html(processar([], []))
    assert "0 nota" in html


# ---------------------------------------------------------------- linha de comando


def test_cli_json_e_caminho_inexistente(tmp_path, capsys):
    j = tmp_path / "a.json"
    main(["conferir", str(AMOSTRAS), "-o", str(tmp_path / "r.html"), "--json", str(j), "--cbs-2027", "8,8"])
    dados = json.loads(j.read_text(encoding="utf-8"))
    assert dados and {"codigo", "severidade", "cnpj"} <= set(dados[0])
    assert main(["conferir", str(tmp_path / "nao-existe")]) == 2


# ---------------------------------------------------------------- sistema web


@pytest.fixture()
def web(tmp_path, monkeypatch):
    monkeypatch.setenv("CONFERENTE_DB", str(tmp_path / "a.db"))
    for k in ("MP_ACCESS_TOKEN", "PIX_CHAVE", "PIX_NOME", "PIX_CIDADE", "ADMIN_SENHA"):
        monkeypatch.setenv(k, "")
    from conferente.web.app import app
    with TestClient(app) as c:
        yield c


def entrar(c, email="ana@x.com.br"):
    return c.post("/cadastro", data=dict(escritorio="Esc", cnpj="11222333000181", responsavel="Ana",
                                          email=email, senha="senha-forte-1"), follow_redirects=False)


def test_pagina_inexistente_e_amigavel(web):
    r = web.get("/nao-existe")
    assert r.status_code == 404 and "text/html" in r.headers["content-type"] and "Página não encontrada" in r.text


def test_conferir_sem_arquivo_mostra_erro_na_tela(web):
    entrar(web)
    r = web.post("/conferir", data={"cbs_2027": ""})
    assert r.status_code == 400 and "text/html" in r.headers["content-type"] and "Escolha" in r.text


def test_limite_de_clientes_no_teste(web):
    entrar(web)
    from conferente import config
    arquivos = []
    for i in range(config.CNPJS_TESTE + 1):
        x = nota_xml(chave=f"352609{i:014d}550010000000011000000010"[:44]).replace(
            b"<CNPJ>11222333000181</CNPJ><xNome>Loja", f"<CNPJ>{i:014d}</CNPJ><xNome>Loja".encode())
        arquivos.append(("arquivos", (f"{i}.xml", x, "text/xml")))
    r = web.post("/conferir", files=arquivos)
    assert r.status_code == 400 and "11 clientes" in r.text


def test_plano_invalido_e_vagas_fundador(web):
    entrar(web)
    r = web.post("/assinar", data={"plano": "inexistente"}, follow_redirects=False)
    assert "erro=" in r.headers["location"]
    from conferente.db import transacao
    with transacao() as con:
        for i in range(20):
            con.execute("INSERT INTO contas (escritorio, cnpj, responsavel, email, senha_hash, plano, ativo_ate) "
                        "VALUES ('E', '1', 'R', ?, 'x', 'fundador', '2099-01-01')", (f"f{i}@x.com",))
    assert "Fundador" not in web.get("/").text.split('id="planos"')[1]
    r = web.post("/assinar", data={"plano": "fundador"}, follow_redirects=False)
    assert "vagas" in r.headers["location"].lower() or "acabaram" in web.get(r.headers["location"]).text


def test_cadastro_email_repetido_com_maiusculas(web):
    entrar(web)
    web.post("/sair")
    r = entrar(web, email="  ANA@X.com.br ")
    assert r.status_code == 400 and "Já existe" in r.text


def test_sair_invalida_sessao(web):
    entrar(web)
    cookie = web.cookies.get("conferente_sessao")
    web.post("/sair")
    web.cookies.set("conferente_sessao", cookie)
    assert web.get("/conta", follow_redirects=False).headers["location"] == "/entrar"


def test_simulado_bloqueado_fora_do_modo_simulado(web, monkeypatch):
    entrar(web)
    link = web.post("/assinar", data={"plano": "essencial"}, follow_redirects=False).headers["location"]
    monkeypatch.setenv("PIX_CHAVE", "a@b.com")
    web.post(link, data={"acao": "aprovar"})
    from conferente import pagamentos
    assert pagamentos.obter(link.rsplit("/", 1)[1]).status == "pendente"


def test_admin_avisa_pix_incompleto(web, monkeypatch):
    monkeypatch.setenv("PIX_CHAVE", "a@b.com")
    monkeypatch.setenv("ADMIN_SENHA", "s3nha-admin")
    web.post("/admin", data={"senha": "s3nha-admin"})
    assert "PIX_NOME" in web.get("/admin").text


def test_admin_confirmar_duas_vezes_nao_soma_duas_vezes(web, monkeypatch):
    monkeypatch.setenv("PIX_CHAVE", "a@b.com")
    monkeypatch.setenv("PIX_NOME", "Davi")
    monkeypatch.setenv("PIX_CIDADE", "Campinas")
    monkeypatch.setenv("ADMIN_SENHA", "s3nha-admin")
    entrar(web)
    ref = web.post("/assinar", data={"plano": "essencial"}, follow_redirects=False).headers["location"].rsplit("/", 1)[1]
    web.post("/admin", data={"senha": "s3nha-admin"})
    web.post(f"/admin/pagamento/{ref}", data={"acao": "confirmar"})
    from conferente import contas
    ate = contas.autenticar("ana@x.com.br", "senha-forte-1").ativo_ate
    web.post(f"/admin/pagamento/{ref}", data={"acao": "confirmar"})
    assert contas.autenticar("ana@x.com.br", "senha-forte-1").ativo_ate == ate
    assert ate == date.today() + timedelta(days=14 + 30)


def test_cookies_seguros(web):
    r = entrar(web)
    sc = r.headers["set-cookie"].lower()
    assert "httponly" in sc and "samesite=lax" in sc


def test_um_cnpj_uma_conta(web):
    entrar(web)
    web.post("/sair")
    r = entrar(web, email="outra@x.com.br")
    assert r.status_code == 400 and "Este CNPJ já tem uma conta" in r.text
