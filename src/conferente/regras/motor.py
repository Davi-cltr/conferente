"""Motor de regras de conferência de IBS/CBS.

Cada regra é uma função pequena, com código fixo (CFxxx), que recebe a nota
(ou o lote) e devolve achados. As regras não "adivinham" a classificação
correta de um produto: elas apontam inconsistências que o contador confirma.

Para incluir uma regra nova: escreva a função, decore com @regra e
documente em docs/regras.md com a fonte legal.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from importlib import resources
from typing import Callable

from ..modelos import Achado, Item, NotaFiscal, Severidade, TributoEsfera

CEM = Decimal("100")
CENTAVO = Decimal("0.01")


def _json(pacote: str, nome: str) -> dict:
    return json.loads(resources.files(pacote).joinpath(nome).read_text("utf-8"))


@dataclass
class Contexto:
    tabela: dict = field(default_factory=lambda: _json("conferente.tabelas", "cclasstrib.json"))
    parametros: dict = field(default_factory=lambda: _json("conferente.regras", "parametros.json"))

    @property
    def tolerancia(self) -> Decimal:
        return Decimal(str(self.parametros.get("tolerancia_centavos", "0.01")))

    def aliquotas(self, ano: int) -> dict | None:
        return self.parametros["aliquotas"].get(str(ano))

    def cst(self, codigo: str | None) -> dict | None:
        return self.tabela["cst"].get(codigo or "")

    def classe(self, codigo: str | None) -> dict | None:
        return self.tabela["cclasstrib"].get(codigo or "")


RegraNota = Callable[[NotaFiscal, Contexto], list[Achado]]
RegraLote = Callable[[list[NotaFiscal], Contexto], list[Achado]]
REGRAS_NOTA: list[RegraNota] = []
REGRAS_LOTE: list[RegraLote] = []


def regra(fn):
    REGRAS_NOTA.append(fn)
    return fn


def regra_lote(fn):
    REGRAS_LOTE.append(fn)
    return fn


def _r2(v: Decimal) -> Decimal:
    return v.quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _brl(v: Decimal | None) -> str:
    if v is None:
        return "—"
    s = f"{v:,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(v: Decimal | None) -> str:
    if v is None:
        return "—"
    return f"{v.normalize():f}".replace(".", ",") + "%"


def _incidencia(item: Item, ctx: Contexto) -> str | None:
    c = ctx.cst(item.ibscbs.cst if item.ibscbs else None)
    return c["incidencia"] if c else None


def _obrigatorio(nota: NotaFiscal, ctx: Contexto) -> tuple[bool, str]:
    for grupo in ctx.parametros["obrigatoriedade"].values():
        if nota.crt in grupo["crt"]:
            inicio = date.fromisoformat(grupo["inicio"])
            return nota.emissao >= inicio, grupo["inicio"]
    return False, ""


# ---------------------------------------------------------------- presença


@regra
def cf001_grupo_ausente(nota, ctx):
    faltando = [i for i in nota.itens if i.ibscbs is None]
    if not faltando:
        return []
    obrig, inicio = _obrigatorio(nota, ctx)
    if obrig:
        return [
            Achado(
                "CF001",
                Severidade.ERRO,
                f"IBS/CBS não informado em {len(faltando)} de {len(nota.itens)} itens",
                f"Para {nota.regime}, o grupo IBSCBS é obrigatório nas notas emitidas desde "
                f"{date.fromisoformat(inicio):%d/%m/%Y}. A SEFAZ adiou a rejeição automática (regra UB12-10), "
                "mas a obrigação legal continua valendo e a nota pode ser questionada depois.",
                nota=nota,
                o_que_fazer="Pedir ao cliente que atualize o emissor e preencha CST, cClassTrib e valores de IBS/CBS.",
            )
        ]
    return [
        Achado(
            "CF001",
            Severidade.INFO,
            "Nota ainda sem IBS/CBS (dentro do prazo)",
            f"Para {nota.regime}, a obrigação começa em "
            f"{date.fromisoformat(inicio):%d/%m/%Y}." if inicio else "Regime não identificado (CRT ausente).",
            nota=nota,
            o_que_fazer="Usar esta nota na simulação de 2027 e preparar o cadastro de produtos do cliente.",
        )
    ]


# ---------------------------------------------------------------- códigos


@regra
def cf002_cst_cclasstrib(nota, ctx):
    out = []
    for item in nota.itens:
        g = item.ibscbs
        if g is None:
            continue
        if not g.cst or ctx.cst(g.cst) is None:
            out.append(Achado(
                "CF002", Severidade.ERRO, f"CST de IBS/CBS inválido: {g.cst or '(vazio)'}",
                "O CST precisa ser um dos códigos da tabela oficial (000, 200, 410, 510...).",
                nota, item, "Corrigir o CST no cadastro do produto no emissor.",
            ))
            continue
        if not g.cclasstrib or len(g.cclasstrib) != 6 or not g.cclasstrib.isdigit():
            out.append(Achado(
                "CF003", Severidade.ERRO, f"cClassTrib com formato inválido: {g.cclasstrib or '(vazio)'}",
                "O cClassTrib tem 6 dígitos e os 3 primeiros repetem o CST.",
                nota, item, "Corrigir a classificação tributária do produto.",
            ))
            continue
        if g.cclasstrib[:3] != g.cst:
            out.append(Achado(
                "CF003", Severidade.ERRO,
                f"cClassTrib {g.cclasstrib} não pertence ao CST {g.cst}",
                "Os 3 primeiros dígitos do cClassTrib devem ser iguais ao CST. "
                "Um dos dois está errado, e isso muda alíquota, redução e crédito.",
                nota, item, "Conferir qual dos dois códigos reflete a operação e corrigir o outro.",
            ))
            continue
        if ctx.classe(g.cclasstrib) is None:
            out.append(Achado(
                "CF004", Severidade.AVISO, f"cClassTrib {g.cclasstrib} não está na tabela de referência",
                "O código tem formato válido, mas não consta da tabela embutida nesta versão. "
                "Pode ser um código novo (a tabela muda por informe técnico) ou um erro de digitação.",
                nota, item, "Confirmar o código na tabela vigente do Portal Nacional da NF-e.",
            ))
    return out


# ---------------------------------------------------------------- contas


def _aliq_efetiva(esf: TributoEsfera) -> Decimal | None:
    if esf.reducao is not None:
        return esf.reducao.pAliqEfet
    return esf.aliquota


def _conferir_esfera(nome, esf: TributoEsfera, vbc, nota, item, ctx, codigo):
    out = []
    if esf.aliquota is None or esf.valor is None or vbc is None:
        return out
    if esf.reducao is not None:
        esperado_efet = esf.aliquota * (1 - esf.reducao.pRedAliq / CEM)
        if abs(esperado_efet - esf.reducao.pAliqEfet) > Decimal("0.0001"):
            out.append(Achado(
                "CF014", Severidade.ERRO,
                f"Alíquota efetiva de {nome} não bate com a redução",
                f"{_pct(esf.aliquota)} com redução de {_pct(esf.reducao.pRedAliq)} dá "
                f"{_pct(esperado_efet.quantize(Decimal('0.0001')))}, mas a nota informa "
                f"{_pct(esf.reducao.pAliqEfet)}.",
                nota, item, "Revisar o cálculo do emissor para itens com redução de alíquota.",
            ))
    efet = _aliq_efetiva(esf)
    esperado = _r2(vbc * efet / CEM)
    dif = esf.valor - esperado
    if abs(dif) > ctx.tolerancia:
        out.append(Achado(
            codigo, Severidade.ERRO, f"Valor de {nome} diferente do cálculo",
            f"Base {_brl(vbc)} × {_pct(efet)} = {_brl(esperado)}; a nota destaca {_brl(esf.valor)} "
            f"(diferença de {_brl(dif)}).",
            nota, item, "Verificar arredondamento e base de cálculo no emissor.", impacto=dif,
        ))
    return out


@regra
def cf010_calculos_item(nota, ctx):
    out = []
    for item in nota.itens:
        g = item.ibscbs
        if g is None or not g.tem_grupo_valores:
            continue
        out += _conferir_esfera("IBS estadual", g.ibs_uf, g.vBC, nota, item, ctx, "CF010")
        out += _conferir_esfera("IBS municipal", g.ibs_mun, g.vBC, nota, item, ctx, "CF011")
        out += _conferir_esfera("CBS", g.cbs, g.vBC, nota, item, ctx, "CF012")
        if g.vIBS is not None and g.ibs_uf.valor is not None and g.ibs_mun.valor is not None:
            soma = g.ibs_uf.valor + g.ibs_mun.valor
            if abs(g.vIBS - soma) > ctx.tolerancia:
                out.append(Achado(
                    "CF013", Severidade.ERRO, "vIBS diferente da soma IBS estadual + municipal",
                    f"{_brl(g.ibs_uf.valor)} + {_brl(g.ibs_mun.valor)} = {_brl(soma)}, mas vIBS = {_brl(g.vIBS)}.",
                    nota, item, "Corrigir o total de IBS do item.", impacto=g.vIBS - soma,
                ))
    return out


@regra
def cf020_aliquotas_do_ano(nota, ctx):
    params = ctx.aliquotas(nota.emissao.year)
    if params is None:
        return []
    out = []
    for item in nota.itens:
        g = item.ibscbs
        if g is None or not g.tem_grupo_valores or _incidencia(item, ctx) != "tributado":
            continue
        if g.cst in {"220", "221"}:  # alíquota fixa por regime específico
            continue
        for nome, esf, chave in (
            ("CBS", g.cbs, "pCBS"), ("IBS estadual", g.ibs_uf, "pIBSUF"), ("IBS municipal", g.ibs_mun, "pIBSMun"),
        ):
            esperado = params.get(chave)
            if esperado is None or esf.aliquota is None:
                continue
            esperado = Decimal(str(esperado))
            if abs(esf.aliquota - esperado) > Decimal("0.0001"):
                out.append(Achado(
                    "CF020", Severidade.ERRO,
                    f"Alíquota de {nome} fora do padrão de {nota.emissao.year}",
                    f"Em {nota.emissao.year} a alíquota de {nome} é {_pct(esperado)}; a nota usa {_pct(esf.aliquota)}. "
                    "Reduções de alíquota vão no grupo gRed, não na alíquota cheia.",
                    nota, item, f"Ajustar a alíquota de {nome} no emissor.",
                ))
    return out


# ---------------------------------------------------------------- reduções


def _reducao_esperada(classe: dict, esfera: str) -> Decimal:
    chave = "reducao_cbs" if esfera == "CBS" else "reducao_ibs"
    v = classe.get(chave, classe.get("reducao", 0))
    return Decimal(str(v))


@regra
def cf030_reducoes(nota, ctx):
    out = []
    for item in nota.itens:
        g = item.ibscbs
        if g is None or not g.tem_grupo_valores or _incidencia(item, ctx) != "tributado":
            continue
        classe = ctx.classe(g.cclasstrib)
        if classe is None or (g.cclasstrib or "")[:3] != g.cst:
            continue
        divergencias = []  # (nome, esperada, informada, impacto)
        for nome, esf, tipo in (("CBS", g.cbs, "CBS"), ("IBS estadual", g.ibs_uf, "IBS"), ("IBS municipal", g.ibs_mun, "IBS")):
            if esf.aliquota is None or esf.aliquota == 0:
                continue
            esperada = _reducao_esperada(classe, tipo)
            informada = esf.reducao.pRedAliq if esf.reducao else Decimal("0")
            efet = _aliq_efetiva(esf) or Decimal("0")
            if (esperada == 100 and efet == 0) or abs(esperada - informada) <= Decimal("0.0001"):
                continue
            impacto = None
            if g.vBC is not None and esf.valor is not None:
                impacto = esf.valor - _r2(g.vBC * esf.aliquota * (1 - esperada / CEM) / CEM)
            divergencias.append((nome, esperada, informada, impacto))
        if not divergencias:
            continue
        nomes = " e ".join(d[0] for d in divergencias)
        esperada, informada = divergencias[0][1], divergencias[0][2]
        impactos = [d[3] for d in divergencias if d[3] is not None]
        impacto = sum(impactos, Decimal("0")) if impactos else None
        desc = f"A classificação {g.cclasstrib} ({classe['descricao']}) prevê redução de {_pct(esperada)}"
        if esperada > informada:
            titulo = f"Redução de {_pct(esperada)} não aplicada ({nomes})"
            expl = (f"{desc}, mas a nota aplicou {_pct(informada)}: o cliente está destacando imposto a mais"
                    + (f" ({_brl(impacto)} neste item, nas alíquotas de teste)" if impacto else "")
                    + ". Hoje é um erro de cadastro; com as alíquotas cheias, vira preço mais alto ou imposto pago a mais.")
            fazer = "Aplicar a redução no cadastro do produto (grupo gRed com o pRedAliq correto)."
        else:
            titulo = f"Redução de {_pct(informada)} sem previsão na classificação ({nomes})"
            expl = (f"{desc}, mas a nota aplicou {_pct(informada)}: imposto destacado a menos"
                    + (f" ({_brl(-impacto)} neste item, nas alíquotas de teste)" if impacto else "")
                    + ", com risco de autuação e de glosa do crédito do comprador.")
            fazer = "Confirmar se o produto tem direito à redução; se tiver, corrigir o cClassTrib; se não, retirar a redução."
        out.append(Achado("CF030", Severidade.ERRO, titulo, expl, nota, item, fazer, impacto))
    return out


@regra
def cf040_sem_incidencia(nota, ctx):
    out = []
    for item in nota.itens:
        g = item.ibscbs
        if g is None:
            continue
        inc = _incidencia(item, ctx)
        if inc == "sem_tributo":
            valores = [v for v in (g.ibs_uf.valor, g.ibs_mun.valor, g.cbs.valor) if v]
            if valores:
                out.append(Achado(
                    "CF040", Severidade.ERRO, f"Imposto destacado em item com CST {g.cst} ({ctx.cst(g.cst)['descricao']})",
                    f"O CST indica que não há IBS/CBS a pagar, mas o item destaca {_brl(sum(valores))}.",
                    nota, item, "Remover os valores ou corrigir o CST.", impacto=sum(valores),
                ))
        elif inc == "tributado" and not g.tem_grupo_valores:
            out.append(Achado(
                "CF005", Severidade.ERRO, f"CST {g.cst} tributado sem base e valores",
                "O item informa um CST com tributo, mas não traz o grupo gIBSCBS (base, alíquotas e valores).",
                nota, item, "Preencher base de cálculo e valores de IBS/CBS.",
            ))
        elif inc == "diferido" and g.tem_grupo_valores and not (
            g.ibs_uf.tem_diferimento or g.cbs.tem_diferimento
        ):
            out.append(Achado(
                "CF041", Severidade.AVISO, "CST de diferimento sem grupo de diferimento",
                "O CST 510 indica diferimento, mas o item não traz o grupo gDif com o percentual diferido.",
                nota, item, "Conferir se o diferimento foi informado corretamente.",
            ))
    return out


@regra
def cf070_base_maior_que_operacao(nota, ctx):
    out = []
    for item in nota.itens:
        g = item.ibscbs
        if g is None or g.vBC is None:
            continue
        teto = item.vProd + item.vFrete + item.vSeg + item.vOutro - item.vDesc
        if g.vBC - teto > ctx.tolerancia:
            out.append(Achado(
                "CF070", Severidade.AVISO, "Base de IBS/CBS maior que o valor da operação",
                f"A base informada ({_brl(g.vBC)}) supera produto + frete + seguro + outros − desconto ({_brl(teto)}). "
                "Em geral a base não inclui tributos que estão sendo substituídos.",
                nota, item, "Conferir a composição da base no emissor.",
            ))
    return out


# ---------------------------------------------------------------- totais


@regra
def cf050_totais(nota, ctx):
    itens = [i.ibscbs for i in nota.itens if i.ibscbs and i.ibscbs.tem_grupo_valores]
    if not itens:
        return []
    t = nota.totais_ibscbs
    if t is None:
        return [Achado(
            "CF050", Severidade.ERRO, "Itens com IBS/CBS, mas sem o total da nota",
            "Os itens trazem IBS/CBS, mas o grupo IBSCBSTot do total da nota não foi informado.",
            nota, None, "Corrigir o emissor para totalizar IBS/CBS.",
        )]

    def soma(f):
        vals = [f(g) for g in itens]
        return sum((v for v in vals if v is not None), Decimal("0"))

    out = []
    for nome, informado, calculado in (
        ("base de cálculo", t.vBCIBSCBS, soma(lambda g: g.vBC)),
        ("IBS", t.vIBS, soma(lambda g: g.vIBS)),
        ("CBS", t.vCBS, soma(lambda g: g.cbs.valor)),
    ):
        if informado is None:
            continue
        if abs(informado - calculado) > ctx.tolerancia:
            out.append(Achado(
                "CF050", Severidade.ERRO, f"Total de {nome} da nota diferente da soma dos itens",
                f"Soma dos itens: {_brl(calculado)}; total informado: {_brl(informado)}.",
                nota, None, "Corrigir a totalização no emissor.", impacto=informado - calculado,
            ))
    return out


# ---------------------------------------------------------------- lote


@regra_lote
def cf060_ncm_com_classificacoes_diferentes(notas, ctx):
    mapa: dict[tuple[str, str], dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    nomes: dict[str, str] = {}
    for n in notas:
        nomes[n.emitente_cnpj] = n.emitente_nome
        for i in n.itens:
            if i.ibscbs and i.ibscbs.cclasstrib and i.ncm:
                mapa[(n.emitente_cnpj, i.ncm)][i.ibscbs.cclasstrib].append(f"NF {n.numero} item {i.numero}")
    out = []
    for (cnpj, ncm), classes in sorted(mapa.items()):
        if len(classes) < 2:
            continue
        detalhes = "; ".join(f"{c}: {', '.join(locs[:3])}{'…' if len(locs) > 3 else ''}" for c, locs in classes.items())
        out.append(Achado(
            "CF060", Severidade.AVISO,
            f"NCM {ncm} com {len(classes)} classificações diferentes em {nomes[cnpj]}",
            "O mesmo NCM foi classificado com cClassTrib diferentes pelo mesmo emitente. Pode ser correto "
            f"(produtos distintos no mesmo NCM), mas costuma indicar cadastro inconsistente. {detalhes}.",
            None, None, "Revisar o cadastro de produtos desse NCM com o cliente.",
        ))
    return out


# ---------------------------------------------------------------- execução


def conferir(notas: list[NotaFiscal], ctx: Contexto | None = None) -> list[Achado]:
    ctx = ctx or Contexto()
    achados: list[Achado] = []
    for nota in notas:
        for r in REGRAS_NOTA:
            achados += r(nota, ctx)
    for r in REGRAS_LOTE:
        achados += r(notas, ctx)
    ordem = {Severidade.ERRO: 0, Severidade.AVISO: 1, Severidade.INFO: 2}
    achados.sort(key=lambda a: (ordem[a.severidade], a.codigo))
    return achados
