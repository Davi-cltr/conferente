"""Leitura de XML de NF-e/NFC-e (modelo 55/65), com ou sem nfeProc.

O parser ignora namespaces e busca as tags pelo nome local, para aceitar
XMLs de qualquer emissor. Entidades externas e acesso à rede ficam
desligados (proteção contra XXE).
"""

from __future__ import annotations

import io
import zipfile
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable

from lxml import etree

from .modelos import (
    ErroLeitura,
    IBSCBSItem,
    Item,
    NotaFiscal,
    Reducao,
    TotaisIBSCBS,
    TributoEsfera,
)

_PARSER = etree.XMLParser(
    resolve_entities=False, no_network=True, remove_comments=True, huge_tree=False
)
LIMITE_BYTES = 5 * 1024 * 1024  # um XML de NF-e real fica bem abaixo disso


def _filho(el, nome):
    if el is None:
        return None
    for c in el:
        if isinstance(c.tag, str) and etree.QName(c).localname == nome:
            return c
    return None


def _caminho(el, *nomes):
    for n in nomes:
        el = _filho(el, n)
        if el is None:
            return None
    return el


def _todos(el, nome):
    if el is None:
        return []
    return [c for c in el if isinstance(c.tag, str) and etree.QName(c).localname == nome]


def _busca(el, nome):
    """Primeiro descendente com o nome local informado."""
    if el is None:
        return None
    for c in el.iter():
        if isinstance(c.tag, str) and etree.QName(c).localname == nome:
            return c
    return None


def _txt(el, *nomes, padrao=""):
    alvo = _caminho(el, *nomes) if nomes else el
    if alvo is None or alvo.text is None:
        return padrao
    return alvo.text.strip()


def _dec(el, *nomes) -> Decimal | None:
    t = _txt(el, *nomes)
    if not t:
        return None
    try:
        return Decimal(t)
    except InvalidOperation:
        return None


def _dec0(el, *nomes) -> Decimal:
    v = _dec(el, *nomes)
    return v if v is not None else Decimal("0")


def _data(texto: str) -> date:
    texto = texto.strip()
    if not texto:
        raise ValueError("data de emissão ausente")
    if len(texto) == 10:
        return date.fromisoformat(texto)
    return datetime.fromisoformat(texto).date()


def _esfera(grupo, campo_aliq: str, campo_valor: str) -> TributoEsfera:
    if grupo is None:
        return TributoEsfera()
    red = _filho(grupo, "gRed")
    reducao = None
    if red is not None:
        reducao = Reducao(
            pRedAliq=_dec0(red, "pRedAliq"), pAliqEfet=_dec0(red, "pAliqEfet")
        )
    return TributoEsfera(
        aliquota=_dec(grupo, campo_aliq),
        valor=_dec(grupo, campo_valor),
        reducao=reducao,
        tem_diferimento=_filho(grupo, "gDif") is not None,
    )


def _ibscbs(imposto) -> IBSCBSItem | None:
    g = _filho(imposto, "IBSCBS")
    if g is None:
        return None
    vals = _filho(g, "gIBSCBS")
    return IBSCBSItem(
        cst=_txt(g, "CST") or None,
        cclasstrib=_txt(g, "cClassTrib") or None,
        tem_grupo_valores=vals is not None,
        vBC=_dec(vals, "vBC"),
        ibs_uf=_esfera(_filho(vals, "gIBSUF"), "pIBSUF", "vIBSUF"),
        ibs_mun=_esfera(_filho(vals, "gIBSMun"), "pIBSMun", "vIBSMun"),
        cbs=_esfera(_filho(vals, "gCBS"), "pCBS", "vCBS"),
        vIBS=_dec(vals, "vIBS"),
    )


def _totais(total) -> TotaisIBSCBS | None:
    t = _filho(total, "IBSCBSTot")
    if t is None:
        return None
    g_ibs = _filho(t, "gIBS")
    return TotaisIBSCBS(
        vBCIBSCBS=_dec(t, "vBCIBSCBS"),
        vIBS=_dec(g_ibs, "vIBS"),
        vIBSUF=_dec(_filho(g_ibs, "gIBSUF"), "vIBSUF"),
        vIBSMun=_dec(_filho(g_ibs, "gIBSMun"), "vIBSMun"),
        vCBS=_dec(_filho(t, "gCBS"), "vCBS"),
    )


def ler_nota(conteudo: bytes, arquivo: str = "") -> NotaFiscal:
    if len(conteudo) > LIMITE_BYTES:
        raise ValueError("arquivo maior que 5 MB, não parece uma NF-e")
    try:
        raiz = etree.fromstring(conteudo, _PARSER)
    except etree.XMLSyntaxError as e:
        raise ValueError(f"XML inválido: {e.msg}") from None

    inf = _busca(raiz, "infNFe")
    if inf is None:
        raise ValueError("não é uma NF-e (tag infNFe não encontrada)")

    ide = _filho(inf, "ide")
    emit = _filho(inf, "emit")
    dest = _filho(inf, "dest")
    total = _filho(inf, "total")
    icmstot = _filho(total, "ICMSTot")

    chave = (inf.get("Id") or "").removeprefix("NFe")
    emissao = _data(_txt(ide, "dhEmi") or _txt(ide, "dEmi"))

    itens: list[Item] = []
    for det in _todos(inf, "det"):
        prod = _filho(det, "prod")
        itens.append(
            Item(
                numero=int(det.get("nItem") or len(itens) + 1),
                codigo=_txt(prod, "cProd"),
                descricao=_txt(prod, "xProd"),
                ncm=_txt(prod, "NCM"),
                cfop=_txt(prod, "CFOP"),
                vProd=_dec0(prod, "vProd"),
                vDesc=_dec0(prod, "vDesc"),
                vFrete=_dec0(prod, "vFrete"),
                vSeg=_dec0(prod, "vSeg"),
                vOutro=_dec0(prod, "vOutro"),
                ibscbs=_ibscbs(_filho(det, "imposto")),
            )
        )

    return NotaFiscal(
        arquivo=arquivo,
        chave=chave,
        modelo=_txt(ide, "mod"),
        numero=_txt(ide, "nNF"),
        serie=_txt(ide, "serie"),
        emissao=emissao,
        emitente_cnpj=_txt(emit, "CNPJ") or _txt(emit, "CPF"),
        emitente_nome=_txt(emit, "xNome"),
        crt=_txt(emit, "CRT"),
        uf_emitente=_txt(emit, "enderEmit", "UF"),
        destinatario_doc=_txt(dest, "CNPJ") or _txt(dest, "CPF"),
        destinatario_nome=_txt(dest, "xNome"),
        itens=itens,
        vNF=_dec0(icmstot, "vNF"),
        vPIS=_dec0(icmstot, "vPIS"),
        vCOFINS=_dec0(icmstot, "vCOFINS"),
        totais_ibscbs=_totais(total),
    )


def _expandir(nome: str, conteudo: bytes) -> Iterable[tuple[str, bytes]]:
    if nome.lower().endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
            total = 0
            for info in z.infolist():
                if info.is_dir() or not info.filename.lower().endswith(".xml"):
                    continue
                total += info.file_size
                if info.file_size > LIMITE_BYTES or total > 500 * 1024 * 1024:
                    raise ValueError("zip grande demais (limite de 500 MB descompactado)")
                yield f"{nome}/{info.filename}", z.read(info)
    else:
        yield nome, conteudo


def ler_lote(arquivos: Iterable[tuple[str, bytes]]):
    """Lê vários arquivos (XML ou ZIP). Devolve (notas, erros de leitura)."""
    notas: list[NotaFiscal] = []
    erros: list[ErroLeitura] = []
    vistas: set[str] = set()
    for nome, conteudo in arquivos:
        try:
            pares = list(_expandir(nome, conteudo))
        except (zipfile.BadZipFile, ValueError) as e:
            erros.append(ErroLeitura(nome, str(e)))
            continue
        for n, c in pares:
            try:
                nota = ler_nota(c, n)
            except ValueError as e:
                erros.append(ErroLeitura(n, str(e)))
                continue
            if nota.chave and nota.chave in vistas:
                erros.append(ErroLeitura(n, "nota duplicada no lote (mesma chave)"))
                continue
            vistas.add(nota.chave)
            notas.append(nota)
    return notas, erros


def ler_pasta(caminho: str | Path):
    p = Path(caminho)
    arquivos = sorted(
        f for f in (p.rglob("*") if p.is_dir() else [p])
        if f.is_file() and f.suffix.lower() in {".xml", ".zip"}
    )
    return ler_lote((str(f.relative_to(p) if p.is_dir() else f.name), f.read_bytes()) for f in arquivos)
