"""Estruturas de dados da NF-e usadas pelo motor de regras."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum


class Severidade(str, Enum):
    ERRO = "erro"      # pode gerar autuação, rejeição ou dinheiro perdido
    AVISO = "aviso"    # merece conferência humana
    INFO = "info"      # contexto, sem ação obrigatória


@dataclass
class Reducao:
    pRedAliq: Decimal
    pAliqEfet: Decimal


@dataclass
class TributoEsfera:
    """Uma esfera do IBS/CBS (IBS UF, IBS Município ou CBS) dentro do item."""

    aliquota: Decimal | None = None
    valor: Decimal | None = None
    reducao: Reducao | None = None
    tem_diferimento: bool = False


@dataclass
class IBSCBSItem:
    cst: str | None = None
    cclasstrib: str | None = None
    tem_grupo_valores: bool = False  # gIBSCBS presente
    vBC: Decimal | None = None
    ibs_uf: TributoEsfera = field(default_factory=TributoEsfera)
    ibs_mun: TributoEsfera = field(default_factory=TributoEsfera)
    cbs: TributoEsfera = field(default_factory=TributoEsfera)
    vIBS: Decimal | None = None


@dataclass
class Item:
    numero: int
    codigo: str
    descricao: str
    ncm: str
    cfop: str
    vProd: Decimal
    vDesc: Decimal = Decimal("0")
    vFrete: Decimal = Decimal("0")
    vSeg: Decimal = Decimal("0")
    vOutro: Decimal = Decimal("0")
    ibscbs: IBSCBSItem | None = None


@dataclass
class TotaisIBSCBS:
    vBCIBSCBS: Decimal | None = None
    vIBS: Decimal | None = None
    vIBSUF: Decimal | None = None
    vIBSMun: Decimal | None = None
    vCBS: Decimal | None = None


@dataclass
class NotaFiscal:
    arquivo: str
    chave: str
    modelo: str
    numero: str
    serie: str
    emissao: date
    emitente_cnpj: str
    emitente_nome: str
    crt: str
    uf_emitente: str
    destinatario_doc: str
    destinatario_nome: str
    itens: list[Item]
    vNF: Decimal
    vPIS: Decimal = Decimal("0")
    vCOFINS: Decimal = Decimal("0")
    totais_ibscbs: TotaisIBSCBS | None = None

    @property
    def regime(self) -> str:
        return {
            "1": "Simples Nacional",
            "2": "Simples Nacional (excesso de sublimite)",
            "3": "Regime Normal",
            "4": "MEI",
        }.get(self.crt, f"CRT {self.crt or '?'}")


@dataclass
class Achado:
    codigo: str
    severidade: Severidade
    titulo: str
    explicacao: str
    nota: NotaFiscal | None = None
    item: Item | None = None
    o_que_fazer: str = ""
    impacto: Decimal | None = None  # diferença em R$, quando mensurável

    @property
    def onde(self) -> str:
        if self.nota is None:
            return "Lote"
        txt = f"NF {self.nota.numero}/{self.nota.serie}"
        if self.item is not None:
            txt += f" · item {self.item.numero} ({self.item.descricao[:40]})"
        return txt


@dataclass
class ErroLeitura:
    arquivo: str
    motivo: str
