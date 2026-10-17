from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conferente.cli import main
from conferente.parser import ler_nota, ler_pasta
from conferente.regras import conferir
from conferente.relatorio import gerar_html, processar
from conferente.simulacao import simular
from conferente.web.app import app

AMOSTRAS = Path(__file__).parent / "amostras"


@pytest.fixture(scope="session", autouse=True)
def gerar():
    import runpy

    runpy.run_path(str(Path(__file__).parent / "gerar_amostras.py"), run_name="__main__")


def codigos(nome):
    nota = ler_nota((AMOSTRAS / nome).read_bytes(), nome)
    return sorted(a.codigo for a in conferir([nota]))


def test_parser_le_grupo_ibscbs():
    n = ler_nota((AMOSTRAS / "mercado_ok.xml").read_bytes())
    assert n.emitente_cnpj == "11222333000181" and n.crt == "3"
    assert len(n.chave) == 44
    arroz = n.itens[0].ibscbs
    assert (arroz.cst, arroz.cclasstrib) == ("200", "200003")
    assert arroz.cbs.reducao.pRedAliq == Decimal("100")
    assert n.totais_ibscbs.vCBS is not None


def test_nota_correta_nao_gera_achados():
    assert codigos("mercado_ok.xml") == []


def test_reducao_nao_aplicada():
    assert "CF030" in codigos("mercado_erro_reducao.xml")


def test_calculo_e_total_errados():
    assert codigos("clinica_erro_calculo.xml") == ["CF012", "CF050"]


def test_grupo_ausente_e_cst_incompativel():
    assert codigos("loja_sem_grupo.xml") == ["CF001", "CF003"]


def test_imune_com_valor_e_aliquota_do_ano():
    assert codigos("loja_imune_com_valor.xml") == ["CF020", "CF040", "CF060"]


def test_simples_em_2026_e_apenas_informativo():
    nota = ler_nota((AMOSTRAS / "padaria_simples.xml").read_bytes())
    achados = conferir([nota])
    assert [(a.codigo, a.severidade.value) for a in achados] == [("CF001", "info")]


def test_lote_detecta_ncm_inconsistente_e_arquivo_corrompido():
    notas, erros = ler_pasta(AMOSTRAS)
    assert len(notas) == 6
    assert [e.arquivo for e in erros] == ["corrompido.xml"]
    assert sum(a.codigo == "CF060" for a in conferir(notas)) == 2  # mesmo NCM, classificações diferentes


def test_xxe_nao_e_resolvido():
    xml = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><infNFe>&e;</infNFe>'
    with pytest.raises(ValueError):
        ler_nota(xml)


def test_simulacao_sem_cbs_definida_calcula_so_ibs():
    notas, _ = ler_pasta(AMOSTRAS)
    sim = simular(notas)
    assert not sim.disponivel and sim.pIBS == Decimal("0.10")
    sim = simular(notas, pCBS=Decimal("8.8"))
    clinica = next(c for c in sim.clientes if c.cnpj == "22333444000172")
    assert clinica.cbs_2027 == Decimal("12.32")  # 350 x 8,8% x (1 - 60%)


def test_relatorio_html_e_cli(tmp_path):
    notas, erros = ler_pasta(AMOSTRAS)
    html = gerar_html(processar(notas, erros), "Escritório Teste")
    assert "Escritório Teste" in html and "CF030" in html
    saida = tmp_path / "r.html"
    assert main(["conferir", str(AMOSTRAS), "-o", str(saida)]) == 1  # 1 = há erros
    assert saida.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_web_upload():
    c = TestClient(app)
    assert c.get("/").status_code == 200
    arquivos = [("arquivos", (p.name, p.read_bytes(), "text/xml")) for p in sorted(AMOSTRAS.glob("*.xml"))]
    r = c.post("/conferir", files=arquivos, data={"escritorio": "Teste", "cbs_2027": "8,8"})
    assert r.status_code == 200 and "Simulação 2027" in r.text
    r = c.post("/conferir", files=[("arquivos", ("x.xml", b"nada", "text/xml"))])
    assert r.status_code == 400
