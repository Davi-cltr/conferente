# Plano de validação (6 a 8 semanas, até R$ 20 mil)

Objetivo: descobrir, com dinheiro real na mesa, se escritórios contábeis pagam para conferir IBS/CBS dos clientes. A decisão sai na semana 8.

## Por que agora

- Regime Normal: campos de IBS/CBS obrigatórios desde 03/08/2026; regra de validação da alíquota da CBS em produção desde 05/10/2026.
- Simples Nacional e MEI: obrigados a partir de janeiro de 2027. É a maior parte da carteira dos escritórios pequenos.
- CBS cobrada de verdade a partir de 2027; alíquota fixada pelo Senado até 15/12/2026.
- Risco principal: os sistemas contábeis grandes embutirem a mesma conferência em 2 a 3 anos. A janela é curta; a velocidade importa mais que perfeição.

## Calendário

| Semana | O que fazer | Entregável |
|---|---|---|
| 1–2 | 15 entrevistas com donos de escritórios de 5 a 30 pessoas ([roteiro](roteiro-entrevistas.md)) | Planilha de entrevistas com citações |
| 2 | Publicar a [landing](../landing/index.html) com pré-venda de R$ 300/mês para os 20 primeiros | Lista de espera |
| 3–6 | Piloto concierge com 5 escritórios: eles mandam um lote de XMLs, você roda o Conferente, revisa com um especialista tributário e devolve o relatório em 48h | 5 relatórios entregues, achados reais anotados |
| 7–8 | Pedir o pagamento, medir e decidir | Decisão: seguir, mudar ou parar |

## Onde achar os escritórios

- Grupos de WhatsApp e Telegram de contadores da sua região.
- CRC-SP (eventos e cursos sobre reforma tributária), sindicatos de contabilistas, Fenacon.
- LinkedIn: buscar "escritório contábil" + cidade; mensagem curta pedindo 20 minutos.
- Indicação: ao fim de cada entrevista, pedir dois nomes.

Comece por Campinas, Americana, Sumaré e Nova Odessa: dá para visitar pessoalmente, o que aumenta muito a taxa de resposta.

## Critérios de decisão

**Seguir** se tudo isto acontecer:

- pelo menos 8 dos 15 entrevistados descrevem a dor sem você sugerir;
- 3 dos 5 escritórios do piloto encontram erro real que não teriam achado sozinhos;
- 3 escritórios aceitam pagar.

**Mudar ou parar** se a maioria disser que o sistema contábil atual já resolve, ou se ninguém pagar ao fim do piloto.

## Métricas do piloto

| Métrica | Como medir | Meta |
|---|---|---|
| Notas processadas por escritório | contagem no relatório | > 500 |
| Achados confirmados pelo contador | anotação por achado: real / falso positivo | > 70% reais |
| Tempo economizado | pergunta direta: "quanto tempo levaria conferindo à mão?" | > 4 h/mês |
| Disposição a pagar | proposta de R$ 300/mês | 3 de 5 |

## Orçamento

| Item | Valor |
|---|---|
| Especialista tributário (revisão dos relatórios do piloto, ~20 h) | R$ 6.000–10.000 |
| Domínio, hospedagem, e-mail | R$ 300 |
| Deslocamento para entrevistas presenciais | R$ 1.000 |
| Reserva (anúncios no LinkedIn, café, imprevistos) | R$ 3.000 |
| **Total** | **até R$ 15 mil** |

## Cuidados

- **LGPD**: os XMLs têm dados de clientes do escritório. Assine um termo simples de confidencialidade e tratamento de dados antes do piloto, processe em memória e apague tudo após entregar o relatório.
- **Responsabilidade**: o relatório aponta inconsistências; a decisão é do contador. Deixe isso escrito no termo.
- **Dados reais nunca vão para o GitHub** (a pasta `dados/` está no `.gitignore`).
