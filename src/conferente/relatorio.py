"""Gera o relatório HTML (imprimível em PDF pelo navegador)."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from jinja2 import Environment, PackageLoader, select_autoescape

from . import __version__
from .modelos import Achado, ErroLeitura, NotaFiscal, Severidade
from .regras.motor import Contexto, _brl, _pct, conferir
from .simulacao import Simulacao, simular

# Horário de Brasília sem horário de verão desde 2019. Fuso fixo evita depender
# da base de fusos do sistema, que o Windows não traz.
BRASILIA = timezone(timedelta(hours=-3), "BRT")

_env = Environment(
    loader=PackageLoader("conferente", "templates"),
    autoescape=select_autoescape(["html"]),
    trim_blocks=True,
    lstrip_blocks=True,
)
_env.filters["brl"] = _brl
_env.filters["pct"] = _pct
_env.filters["cnpj"] = lambda d: (
    f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if d and len(d) == 14 else (d or "—")
)


@dataclass
class GrupoCliente:
    cnpj: str
    nome: str
    regime: str
    notas: int
    achados: list[Achado]

    @property
    def erros(self) -> int:
        return sum(a.severidade is Severidade.ERRO for a in self.achados)

    @property
    def avisos(self) -> int:
        return sum(a.severidade is Severidade.AVISO for a in self.achados)

    @property
    def status(self) -> str:
        return "erro" if self.erros else ("aviso" if self.avisos else "ok")


@dataclass
class Resultado:
    notas: list[NotaFiscal]
    erros_leitura: list[ErroLeitura]
    achados: list[Achado]
    simulacao: Simulacao

    @property
    def contagem(self) -> Counter:
        return Counter(a.severidade.value for a in self.achados)

    @property
    def itens_a_revisar(self) -> int:
        return len({(a.nota.chave, a.item.numero) for a in self.achados
                    if a.nota and a.item and a.severidade is not Severidade.INFO})

    def por_cliente(self) -> list[GrupoCliente]:
        grupos: dict[str, list[Achado]] = defaultdict(list)
        for a in self.achados:
            grupos[a.nota.emitente_cnpj if a.nota else "_lote"].append(a)
        info: dict[str, tuple[str, str]] = {}
        qtd: Counter = Counter()
        for n in self.notas:
            info[n.emitente_cnpj] = (n.emitente_nome, n.regime)
            qtd[n.emitente_cnpj] += 1
        out = [
            GrupoCliente(cnpj, info[cnpj][0], info[cnpj][1], qtd[cnpj], grupos.get(cnpj, []))
            for cnpj in info
        ]
        out.sort(key=lambda g: (-g.erros, -g.avisos, g.nome))
        if grupos.get("_lote"):
            out.append(GrupoCliente("", "Conferências entre notas", "", 0, grupos["_lote"]))
        return out


def processar(notas, erros_leitura, ctx: Contexto | None = None, pCBS: Decimal | None = None) -> Resultado:
    ctx = ctx or Contexto()
    return Resultado(notas, erros_leitura, conferir(notas, ctx), simular(notas, ctx, pCBS=pCBS))


def gerar_html(res: Resultado, escritorio: str = "", voltar: str | None = None) -> str:
    agora = datetime.now(BRASILIA)
    periodo = ""
    if res.notas:
        ini = min(n.emissao for n in res.notas)
        fim = max(n.emissao for n in res.notas)
        periodo = f"{ini:%d/%m/%Y} a {fim:%d/%m/%Y}" if ini != fim else f"{ini:%d/%m/%Y}"
    return _env.get_template("relatorio.html").render(
        res=res,
        grupos=res.por_cliente(),
        escritorio=escritorio,
        gerado_em=agora.strftime("%d/%m/%Y %H:%M"),
        periodo=periodo,
        versao=__version__,
        voltar=voltar,
    )
