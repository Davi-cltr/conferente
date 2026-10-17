# Modelo de negócio

## Cliente

Escritórios de contabilidade com 5 a 30 pessoas que atendem empresas de vários regimes. São cerca de 98 mil organizações contábeis no Brasil (CFC, 2025). Quem decide a compra é o dono do escritório; quem usa é o analista fiscal.

## Proposta de valor

"Confira IBS e CBS de todos os seus clientes em minutos, sem depender do ERP de cada um, e descubra os erros antes da apuração."

## Preço (hipótese a validar no piloto)

| Plano | CNPJs conferidos | Preço/mês |
|---|---|---|
| Fundador (20 primeiros) | até 150 | R$ 300, preço travado por 12 meses |
| Essencial | até 50 | R$ 290 |
| Escritório | até 150 | R$ 490 |
| Ampliado | até 400 | R$ 890 |

Referência: o escritório típico gasta mais de R$ 1.000/mês em software; o relatório substitui horas de conferência manual que o escritório não cobra do cliente.

Receita extra possível: o escritório revende um "check-up da reforma" ao cliente final usando o relatório (R$ 150–500 por cliente). Isso ajuda o escritório a pagar a assinatura.

## Contas de referência

- Meta de 3 anos do relatório original: 1.000 escritórios × R$ 400/mês ≈ R$ 4,8 mi/ano de receita recorrente.
- Ponto de equilíbrio de uma pessoa em tempo integral (custo R$ 12 mil/mês com especialista tributário em meio período): ~35 escritórios no plano Escritório.

## Custos principais

- Especialista tributário recorrente para manter regras (o maior custo e a maior barreira de entrada).
- Hospedagem: baixa (processamento em memória, sem armazenar XML).
- Aquisição: conteúdo e presença em grupos de contadores, parcerias com CRCs e cursos de reforma.

## Riscos e respostas

| Risco | Resposta |
|---|---|
| Sistemas contábeis grandes embutem a conferência | Ser independente de ERP e mais rápido nas mudanças de regra; mirar escritórios com clientes em emissores variados |
| Erro da ferramenta vira autuação do cliente | Relatório aponta inconsistência, não decide; termo de responsabilidade; revisão por especialista |
| Regras mudam toda hora | Parâmetros versionados com fonte; revisão mensal no calendário |
| LGPD | Processar em memória, não guardar XML, termo de tratamento de dados |
