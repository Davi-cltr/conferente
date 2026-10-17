"""Gera site/exemplo.html (relatório de exemplo da vitrine) a partir de tests/amostras.

    python scripts/gerar_vitrine.py
"""

from decimal import Decimal
from pathlib import Path

from conferente.parser import ler_pasta
from conferente.relatorio import gerar_html, processar

RAIZ = Path(__file__).resolve().parents[1]

notas, erros = ler_pasta(RAIZ / "tests" / "amostras")
html = gerar_html(processar(notas, erros, pCBS=Decimal("8.8")), "Exemplo com notas fictícias",
                  voltar="/", voltar_texto="← Voltar para o Conferente")
(RAIZ / "site" / "exemplo.html").write_text(html, encoding="utf-8")
(RAIZ / "docs" / "exemplo-relatorio.html").write_text(html, encoding="utf-8")
print("site/exemplo.html gerado")
