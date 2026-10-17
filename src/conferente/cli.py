"""Linha de comando.

    conferente conferir caminho/para/xmls -o relatorio.html --escritorio "Contábil Exemplo"
    conferente servir --porta 8000
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .parser import ler_lote
from .relatorio import gerar_html, processar


def _decimal(v: str) -> Decimal:
    try:
        return Decimal(v.replace(",", "."))
    except InvalidOperation:
        raise argparse.ArgumentTypeError(f"número inválido: {v}") from None


def _arquivos(caminhos: list[str]):
    for c in caminhos:
        p = Path(c)
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and f.suffix.lower() in {".xml", ".zip"}:
                    yield str(f.relative_to(p)), f.read_bytes()
        elif p.is_file():
            yield p.name, p.read_bytes()
        else:
            print(f"aviso: {c} não encontrado", file=sys.stderr)


def _cmd_conferir(a) -> int:
    notas, erros = ler_lote(_arquivos(a.caminhos))
    if not notas and not erros:
        print("Nenhum XML ou ZIP encontrado.", file=sys.stderr)
        return 2
    res = processar(notas, erros, pCBS=a.cbs_2027)
    Path(a.saida).write_text(gerar_html(res, a.escritorio), encoding="utf-8")
    c = res.contagem
    print(f"{len(notas)} notas lidas, {len(erros)} arquivos com problema.")
    print(f"{c.get('erro', 0)} erros, {c.get('aviso', 0)} avisos. Relatório: {a.saida}")
    if a.json:
        dados = [
            {
                "codigo": x.codigo, "severidade": x.severidade.value, "titulo": x.titulo,
                "explicacao": x.explicacao, "o_que_fazer": x.o_que_fazer,
                "cnpj": x.nota.emitente_cnpj if x.nota else None,
                "chave": x.nota.chave if x.nota else None,
                "item": x.item.numero if x.item else None,
                "impacto": str(x.impacto) if x.impacto is not None else None,
            }
            for x in res.achados
        ]
        Path(a.json).write_text(json.dumps(dados, ensure_ascii=False, indent=2), encoding="utf-8")
    return 1 if c.get("erro") else 0


def _cmd_servir(a) -> int:
    import uvicorn

    uvicorn.run("conferente.web.app:app", host=a.host, port=a.porta)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="conferente", description="Confere IBS/CBS em lotes de NF-e.")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("conferir", help="gera o relatório de um lote de XMLs")
    c.add_argument("caminhos", nargs="+", help="pastas, arquivos .xml ou .zip")
    c.add_argument("-o", "--saida", default="relatorio.html")
    c.add_argument("--escritorio", default="", help="nome do escritório no cabeçalho")
    c.add_argument("--cbs-2027", type=_decimal, default=None, help="alíquota da CBS de 2027 para a simulação, em %%")
    c.add_argument("--json", help="também salva os achados em JSON neste caminho")
    c.set_defaults(fn=_cmd_conferir)

    s = sub.add_parser("servir", help="abre a versão web local")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--porta", type=int, default=8000)
    s.set_defaults(fn=_cmd_servir)

    a = p.parse_args(argv)
    return a.fn(a)


if __name__ == "__main__":
    sys.exit(main())
