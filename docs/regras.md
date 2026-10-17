# Regras de conferência

Parâmetros revisados em 17/10/2026. Cada regra aponta inconsistência; quem decide a classificação é o contador.

## Fontes

- **NT 2025.002 (NF-e/NFC-e) – Reforma Tributária do Consumo**, versões 1.50 a 1.52, Portal Nacional da NF-e. Grupo UB (`IBSCBS`) e grupo W03 (`IBSCBSTot`).
- **Informe Técnico RT 2025.002**: tabela de CST e cClassTrib.
- **LC 214/2025**: alíquotas de teste (2026), alíquotas de transição do IBS (2027–2028, art. 344) e regime do Simples (art. 348).
- **Ato Técnico Conjunto RFB/CGIBS nº 1/2026**: datas de produção.

## Leiaute lido

Item (`det/imposto/IBSCBS`): `CST`, `cClassTrib`, `gIBSCBS/vBC`, `gIBSUF/pIBSUF`, `gIBSUF/gRed/pRedAliq`, `gIBSUF/gRed/pAliqEfet`, `gIBSUF/gDif`, `gIBSUF/vIBSUF`, `gIBSMun/pIBSMun`, `gIBSMun/vIBSMun`, `vIBS`, `gCBS/pCBS`, `gCBS/gRed/...`, `gCBS/vCBS`.

Total (`total/IBSCBSTot`): `vBCIBSCBS`, `gIBS/vIBS`, `gIBS/gIBSUF/vIBSUF`, `gIBS/gIBSMun/vIBSMun`, `gCBS/vCBS`.

O parser ignora namespaces e procura as tags pelo nome, para aceitar XML de qualquer emissor.

## Regras

| Código | Regra | Gravidade | Base |
|---|---|---|---|
| CF001 | Item sem `IBSCBS`. Erro se o regime já está obrigado na data de emissão (CRT 3 desde 03/08/2026; CRT 1, 2 e 4 desde 04/01/2027); senão, informativo. | erro/info | NT 2025.002 v1.51; LC 214/2025 art. 348. A rejeição 1115 (UB12-10) foi adiada, mas a obrigação permanece. |
| CF002 | CST fora da tabela. | erro | Informe Técnico RT 2025.002 |
| CF003 | cClassTrib sem 6 dígitos ou cujos 3 primeiros dígitos diferem do CST. | erro | Estrutura da tabela cClassTrib |
| CF004 | cClassTrib com formato válido, mas fora da tabela embutida. | aviso | Tabela pode ter sido atualizada |
| CF005 | CST com tributo sem `gIBSCBS`. | erro | NT 2025.002, grupo UB15 |
| CF010/011/012 | `v` ≠ `vBC × alíquota efetiva` (tolerância R$ 0,01) para IBS UF, IBS Município e CBS. | erro | Cálculo do grupo UB |
| CF013 | `vIBS` ≠ `vIBSUF + vIBSMun`. | erro | UB54a |
| CF014 | `pAliqEfet` ≠ `alíquota × (1 − pRedAliq/100)`. | erro | Grupos UB26, UB45, UB64 |
| CF020 | Alíquota nominal diferente da do ano (2026: CBS 0,9%, IBS UF 0,1%, IBS Mun 0%; 2027: IBS 0,05% + 0,05%, CBS quando publicada). Não se aplica a CST 220/221. | erro | LC 214/2025 |
| CF030 | Redução prevista na classificação não aplicada, ou aplicada sem previsão. Alíquota zero aceita tanto redução de 100% quanto alíquota efetiva 0. | erro | Tabela cClassTrib |
| CF040 | Valores de IBS/CBS em item com CST 400, 410 ou 550. | erro | Tabela CST |
| CF041 | CST 510 sem `gDif`. | aviso | Grupo UB21 |
| CF050 | Totais `IBSCBSTot` diferentes da soma dos itens, ou ausentes. | erro | Grupo W03 |
| CF060 | No lote, mesmo emitente com o mesmo NCM em cClassTrib diferentes. | aviso | Consistência de cadastro |
| CF070 | `vBC` maior que produto + frete + seguro + outros − desconto. | aviso | Heurística |

## Limitações conhecidas

- Não sabe, sozinho, se um NCM tem direito a redução: só confere se a nota é coerente com a classificação escolhida. Próximo passo: tabela NCM × anexos da LC 214 (ver roadmap).
- Não trata ainda tributação monofásica de combustíveis (CST 620), crédito presumido, compras governamentais, Imposto Seletivo nem NFS-e.
- A tabela cClassTrib embutida veio de reprodução pública do informe técnico; confira contra a versão oficial antes do uso pago.
