"""Simulação: quanto o cliente pagaria de CBS/IBS em 2027 sobre as mesmas vendas.

A CBS substitui PIS e Cofins em 2027. A simulação compara o PIS/Cofins
destacado nas notas do lote com a CBS + IBS estimada, usando a
classificação (e a redução) de cada item. É uma ordem de grandeza para
conversar com o cliente, não um cálculo de apuração: não considera
créditos, regimes específicos nem a alíquota final da CBS antes de ser
publicada.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal

from .modelos import NotaFiscal
from .regras.motor import CEM, Contexto, _r2, _reducao_esperada


@dataclass
class SimulacaoCliente:
    cnpj: str
    nome: str
    regime: str
    notas: int = 0
    base: Decimal = Decimal("0")
    pis_cofins_atual: Decimal = Decimal("0")
    cbs_2027: Decimal = Decimal("0")
    ibs_2027: Decimal = Decimal("0")
    itens_sem_classificacao: int = 0
    itens_com_reducao: int = 0
    itens: int = 0

    @property
    def total_2027(self) -> Decimal:
        return self.cbs_2027 + self.ibs_2027

    @property
    def variacao(self) -> Decimal:
        return self.total_2027 - self.pis_cofins_atual


@dataclass
class Simulacao:
    ano: int
    pCBS: Decimal | None
    pIBS: Decimal
    fonte: str
    clientes: list[SimulacaoCliente] = field(default_factory=list)

    @property
    def disponivel(self) -> bool:
        return self.pCBS is not None


def simular(notas: list[NotaFiscal], ctx: Contexto | None = None, pCBS: Decimal | None = None, ano: int = 2027) -> Simulacao:
    ctx = ctx or Contexto()
    p = ctx.aliquotas(ano) or {}
    cbs = pCBS if pCBS is not None else (Decimal(str(p["pCBS"])) if p.get("pCBS") is not None else None)
    ibs = Decimal(str(p.get("pIBSUF") or 0)) + Decimal(str(p.get("pIBSMun") or 0))
    sim = Simulacao(ano=ano, pCBS=cbs, pIBS=ibs, fonte=p.get("fonte", ""))

    por_cliente: dict[str, SimulacaoCliente] = {}
    for n in notas:
        c = por_cliente.get(n.emitente_cnpj)
        if c is None:
            c = por_cliente[n.emitente_cnpj] = SimulacaoCliente(n.emitente_cnpj, n.emitente_nome, n.regime)
        c.notas += 1
        c.pis_cofins_atual += n.vPIS + n.vCOFINS
        for i in n.itens:
            c.itens += 1
            base = i.ibscbs.vBC if (i.ibscbs and i.ibscbs.vBC is not None) else (
                i.vProd + i.vFrete + i.vSeg + i.vOutro - i.vDesc
            )
            classe = ctx.classe(i.ibscbs.cclasstrib) if i.ibscbs else None
            cst = ctx.cst(i.ibscbs.cst) if i.ibscbs else None
            if classe is None:
                c.itens_sem_classificacao += 1
                red_cbs = red_ibs = Decimal("0")
            elif cst and cst["incidencia"] != "tributado":
                continue
            else:
                red_cbs = _reducao_esperada(classe, "CBS")
                red_ibs = _reducao_esperada(classe, "IBS")
                if red_cbs or red_ibs:
                    c.itens_com_reducao += 1
            c.base += base
            if cbs is not None:
                c.cbs_2027 += _r2(base * cbs * (1 - red_cbs / CEM) / CEM)
            c.ibs_2027 += _r2(base * ibs * (1 - red_ibs / CEM) / CEM)
    sim.clientes = sorted(por_cliente.values(), key=lambda c: -c.base)
    return sim
