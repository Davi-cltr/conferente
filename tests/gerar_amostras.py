"""Gera XMLs de NF-e fictícios para testes e demonstração.

Todos os CNPJs, nomes e chaves são inventados. A estrutura segue o leiaute
da NF-e 4.00 com o grupo IBSCBS da NT 2025.002.

    python tests/gerar_amostras.py
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

NS = "http://www.portalfiscal.inf.br/nfe"
AQUI = Path(__file__).parent


def r2(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def esfera(tag, ptag, vtag, aliq, vbc, red=None, valor=None):
    efet = aliq if red is None else aliq * (1 - Decimal(red) / 100)
    v = r2(vbc * efet / 100) if valor is None else Decimal(valor)
    gred = ""
    if red is not None:
        gred = f"<gRed><pRedAliq>{Decimal(red):.4f}</pRedAliq><pAliqEfet>{efet:.4f}</pAliqEfet></gRed>"
    return f"<{tag}><{ptag}>{aliq:.4f}</{ptag}>{gred}<{vtag}>{v:.2f}</{vtag}></{tag}>", v


def item(n, desc, ncm, vprod, cst="000", cclass="000001", red=None, cbs_valor=None,
         p_cbs=Decimal("0.9"), p_uf=Decimal("0.1"), p_mun=Decimal("0"), sem_grupo=False, forcar_valores=False):
    vprod = Decimal(vprod)
    imposto = ""
    tot = {"vBC": Decimal(0), "vIBS": Decimal(0), "vCBS": Decimal(0), "vUF": Decimal(0), "vMun": Decimal(0)}
    if not sem_grupo:
        if cst in {"410", "400", "550"} and not forcar_valores:
            imposto = f"<IBSCBS><CST>{cst}</CST><cClassTrib>{cclass}</cClassTrib></IBSCBS>"
        else:
            uf, vuf = esfera("gIBSUF", "pIBSUF", "vIBSUF", p_uf, vprod, red)
            mun, vmun = esfera("gIBSMun", "pIBSMun", "vIBSMun", p_mun, vprod, red if p_mun else None)
            cbs, vcbs = esfera("gCBS", "pCBS", "vCBS", p_cbs, vprod, red, cbs_valor)
            imposto = (f"<IBSCBS><CST>{cst}</CST><cClassTrib>{cclass}</cClassTrib><gIBSCBS>"
                       f"<vBC>{vprod:.2f}</vBC>{uf}{mun}<vIBS>{vuf + vmun:.2f}</vIBS>{cbs}</gIBSCBS></IBSCBS>")
            tot = {"vBC": vprod, "vIBS": vuf + vmun, "vCBS": vcbs, "vUF": vuf, "vMun": vmun}
    pis, cof = r2(vprod * Decimal("0.0165")), r2(vprod * Decimal("0.076"))
    xml = (f'<det nItem="{n}"><prod><cProd>{n:04d}</cProd><cEAN>SEM GTIN</cEAN><xProd>{desc}</xProd>'
           f"<NCM>{ncm}</NCM><CFOP>5102</CFOP><uCom>UN</uCom><qCom>1.0000</qCom><vUnCom>{vprod:.2f}</vUnCom>"
           f"<vProd>{vprod:.2f}</vProd><indTot>1</indTot></prod><imposto>"
           f"<PIS><PISAliq><CST>01</CST><vBC>{vprod:.2f}</vBC><pPIS>1.6500</pPIS><vPIS>{pis:.2f}</vPIS></PISAliq></PIS>"
           f"<COFINS><COFINSAliq><CST>01</CST><vBC>{vprod:.2f}</vBC><pCOFINS>7.6000</pCOFINS><vCOFINS>{cof:.2f}</vCOFINS></COFINSAliq></COFINS>"
           f"{imposto}</imposto></det>")
    return xml, vprod, pis, cof, tot


def nota(numero, cnpj, nome, crt, data, itens, quebrar_total=False):
    dets, vnf, vpis, vcof = [], Decimal(0), Decimal(0), Decimal(0)
    t = {"vBC": Decimal(0), "vIBS": Decimal(0), "vCBS": Decimal(0), "vUF": Decimal(0), "vMun": Decimal(0)}
    for i in itens:
        x, v, p, c, tt = i
        dets.append(x)
        vnf += v
        vpis += p
        vcof += c
        for k in t:
            t[k] += tt[k]
    if quebrar_total:
        t["vCBS"] += Decimal("1.00")
    tot_ibscbs = ""
    if t["vBC"]:
        tot_ibscbs = (f"<IBSCBSTot><vBCIBSCBS>{t['vBC']:.2f}</vBCIBSCBS><gIBS>"
                      f"<gIBSUF><vDif>0.00</vDif><vDevTrib>0.00</vDevTrib><vIBSUF>{t['vUF']:.2f}</vIBSUF></gIBSUF>"
                      f"<gIBSMun><vDif>0.00</vDif><vDevTrib>0.00</vDevTrib><vIBSMun>{t['vMun']:.2f}</vIBSMun></gIBSMun>"
                      f"<vIBS>{t['vIBS']:.2f}</vIBS><vCredPres>0.00</vCredPres><vCredPresCondSus>0.00</vCredPresCondSus></gIBS>"
                      f"<gCBS><vDif>0.00</vDif><vDevTrib>0.00</vDevTrib><vCBS>{t['vCBS']:.2f}</vCBS>"
                      f"<vCredPres>0.00</vCredPres><vCredPresCondSus>0.00</vCredPresCondSus></gCBS></IBSCBSTot>")
    chave = f"35{data[2:4]}{data[5:7]}{cnpj}55001{int(numero):09d}1{int(numero):08d}0"[:44].ljust(44, "0")
    return (f'<?xml version="1.0" encoding="UTF-8"?><nfeProc xmlns="{NS}" versao="4.00"><NFe xmlns="{NS}">'
            f'<infNFe Id="NFe{chave}" versao="4.00"><ide><cUF>35</cUF><natOp>Venda</natOp><mod>55</mod>'
            f"<serie>1</serie><nNF>{numero}</nNF><dhEmi>{data}T10:00:00-03:00</dhEmi><tpNF>1</tpNF></ide>"
            f"<emit><CNPJ>{cnpj}</CNPJ><xNome>{nome}</xNome><enderEmit><xMun>Campinas</xMun><UF>SP</UF></enderEmit>"
            f"<CRT>{crt}</CRT></emit><dest><CNPJ>99888777000166</CNPJ><xNome>Cliente Final Ficticio Ltda</xNome></dest>"
            f"{''.join(dets)}<total><ICMSTot><vProd>{vnf:.2f}</vProd><vPIS>{vpis:.2f}</vPIS>"
            f"<vCOFINS>{vcof:.2f}</vCOFINS><vNF>{vnf:.2f}</vNF></ICMSTot>{tot_ibscbs}</total></infNFe></NFe></nfeProc>")


MERCADO = ("11222333000181", "Mercadinho Bom Preco Ltda", "3")
CLINICA = ("22333444000172", "Clinica Saude Viva Ltda", "3")
PADARIA = ("33444555000163", "Padaria Pao Quente ME", "1")
LOJA = ("44555666000154", "Loja Casa e Cia Ltda", "3")

AMOSTRAS = {
    # Tudo certo
    "mercado_ok.xml": nota(1001, *MERCADO, "2026-09-10", [
        item(1, "Arroz tipo 1 5kg", "10063021", "27.90", "200", "200003", red=100),
        item(2, "Detergente liquido 500ml", "34022000", "3.49", "200", "200035", red=60),
        item(3, "Refrigerante 2L", "22021000", "9.99"),
        item(4, "Sabonete 90g", "34011190", "2.79"),
    ]),
    # Detergente classificado com redução de 60%, mas o emissor não aplicou; sabonete classificado diferente da outra nota
    "mercado_erro_reducao.xml": nota(1002, *MERCADO, "2026-09-12", [
        item(1, "Detergente liquido 500ml", "34022000", "3.49", "200", "200035"),
        item(2, "Sabonete 90g", "34011190", "2.79", "200", "200035", red=60),
    ]),
    # Clínica: CBS digitada errada e total da nota divergente
    "clinica_erro_calculo.xml": nota(501, *CLINICA, "2026-09-15", [
        item(1, "Consulta medica", "00000000", "350.00", "200", "200029", red=60, cbs_valor="3.15"),
    ], quebrar_total=True),
    # Loja: item sem IBS/CBS após 03/08/2026 e cClassTrib que não bate com o CST
    "loja_sem_grupo.xml": nota(77, *LOJA, "2026-09-20", [
        item(1, "Jogo de panelas", "73239300", "189.90", sem_grupo=True),
        item(2, "Toalha de banho", "63026000", "49.90", "000", "200035"),
    ]),
    # Loja: livro (imune) com imposto destacado e alíquota de CBS do ano errada
    "loja_imune_com_valor.xml": nota(78, *LOJA, "2026-09-21", [
        item(1, "Livro de receitas", "49019900", "79.90", p_cbs=Decimal("8.8")),
        item(2, "Livro infantil", "49019900", "39.90", "410", "410008", forcar_valores=True),
    ]),
    # Padaria do Simples: em 2026 ainda não precisa (informativo)
    "padaria_simples.xml": nota(3001, *PADARIA, "2026-09-25", [
        item(1, "Pao frances kg", "19059090", "18.90", sem_grupo=True),
    ]),
}

if __name__ == "__main__":
    destino = AQUI / "amostras"
    destino.mkdir(exist_ok=True)
    for nome, xml in AMOSTRAS.items():
        (destino / nome).write_text(xml, encoding="utf-8")
    (destino / "corrompido.xml").write_text("<nfeProc><NFe>incompleto", encoding="utf-8")
    print(f"{len(AMOSTRAS) + 1} arquivos em {destino}")
