# Conferente

**Copiloto fiscal para escritórios de contabilidade.** O escritório envia os XMLs de NF-e de todos os clientes e recebe, em segundos, um relatório com os erros de IBS e CBS de cada um — antes da apuração, antes da autuação.

> Status: MVP de validação (v0.1). Feito para o piloto com 5 escritórios descrito em [docs/plano-de-validacao.md](docs/plano-de-validacao.md).

## Por que existe

A reforma tributária obriga toda empresa que emite nota a informar IBS e CBS item a item. Para o **Regime Normal**, os campos são obrigatórios desde **03/08/2026**; para **Simples Nacional e MEI**, desde **janeiro de 2027**, quando a CBS também passa a ser cobrada de verdade.

Quem sente a dor primeiro é o contador: ele atende dezenas de clientes, cada um com um emissor diferente, e não tem como conferir nota por nota. O Conferente é **independente de ERP**: lê o XML, que todo emissor gera igual.

## O que ele confere

| Código | O que aponta | Gravidade |
|---|---|---|
| CF001 | Item sem o grupo IBSCBS depois do prazo do regime | erro |
| CF002/003/004 | CST inválido, cClassTrib que não pertence ao CST, código fora da tabela | erro/aviso |
| CF005 | CST tributado sem base e valores | erro |
| CF010–014 | Contas de IBS estadual, municipal, CBS, vIBS e alíquota efetiva | erro |
| CF020 | Alíquota fora do padrão do ano (2026: CBS 0,9%, IBS 0,1%) | erro |
| CF030 | Redução de alíquota prevista na classificação e não aplicada (ou o contrário) | erro |
| CF040/041 | Imposto destacado em item isento/imune; diferimento sem grupo gDif | erro/aviso |
| CF050 | Total da nota diferente da soma dos itens | erro |
| CF060 | Mesmo NCM com classificações diferentes no mesmo cliente | aviso |
| CF070 | Base de cálculo maior que o valor da operação | aviso |

Cada regra, com fonte legal, está em [docs/regras.md](docs/regras.md). O relatório também traz uma **simulação de 2027**: PIS/Cofins de hoje contra CBS + IBS nas mesmas vendas.

Veja um relatório de exemplo em [docs/exemplo-relatorio.html](docs/exemplo-relatorio.html) (baixe e abra no navegador).

## Como usar

**No Windows, o jeito mais fácil:** dê dois cliques em `iniciar.bat`. Na primeira vez ele prepara o ambiente; depois abre o Conferente no navegador.

O sistema completo tem: site com planos, cadastro do escritório (com 14 dias grátis), login, área **Minha conta** com pagamento por plano e a conferência de notas, liberada só para contas ativas. Contas e pagamentos ficam em `dados/conferente.db`.

Sem configuração, os pagamentos são **simulados**. Para usar o Mercado Pago, siga [docs/pagamento-mercadopago.md](docs/pagamento-mercadopago.md).

Para testar a conferência, use os arquivos da pasta `tests/amostras`.

Pela linha de comando:

Requer Python 3.11+.

```bash
pip install -e ".[dev]"

# Linha de comando: uma pasta com XMLs ou .zip
conferente conferir pasta_dos_xmls/ -o relatorio.html --escritorio "Contabilidade Exemplo"

# Simular 2027 com uma alíquota estimada de CBS (a oficial sai até 15/12/2026)
conferente conferir pasta_dos_xmls/ --cbs-2027 8,8

# Versão web local (arrastar e soltar)
conferente servir            # abre em http://127.0.0.1:8000
```

Com Docker:

```bash
docker build -t conferente .
docker run -p 8000:8000 conferente
```

O relatório é HTML; para PDF, use “Imprimir → Salvar como PDF” no navegador.

## Testes

```bash
python tests/gerar_amostras.py   # XMLs fictícios com erros conhecidos
pytest
```

## Estrutura

```
src/conferente/
  parser.py          leitura de NF-e/NFC-e (XML ou ZIP), protegida contra XXE
  regras/motor.py    regras CFxxx
  regras/parametros.json   datas e alíquotas por ano, com fonte
  tabelas/cclasstrib.json  CST × cClassTrib × redução
  simulacao.py       PIS/Cofins × CBS/IBS 2027
  relatorio.py       relatório HTML
  web/app.py         upload web (FastAPI), nada é gravado em disco
docs/                regras, plano de validação, roteiro de entrevistas, modelo de negócio
landing/             página de pré-venda
```

## Manutenção das regras

As regras mudam por nota técnica. Antes de cada mês de apuração:

1. Conferir a versão vigente da NT 2025.002 e do Informe Técnico de cClassTrib no [Portal Nacional da NF-e](https://www.nfe.fazenda.gov.br/).
2. Atualizar `tabelas/cclasstrib.json` e `regras/parametros.json` (cada valor tem campo de fonte).
3. Rodar `pytest`.

## Aviso

O Conferente aponta inconsistências para análise do contador responsável. Não substitui a análise tributária nem garante a classificação correta de cada produto.

© 2026 Davi Motta Peluci. Todos os direitos reservados.
