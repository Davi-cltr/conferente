# Roadmap

## v0.1 — MVP de validação (pronto)

- Leitura de NF-e/NFC-e em XML e ZIP, com proteção contra XXE.
- 17 regras de conferência (CF001–CF070).
- Relatório HTML por cliente, imprimível em PDF.
- Simulação 2027 (PIS/Cofins × CBS/IBS).
- Linha de comando e upload web sem armazenamento.

## v0.2 — durante o piloto (semanas 3–6)

- Marcar cada achado como "real" ou "falso positivo" no relatório, para medir precisão.
- Exportar achados em planilha (.xlsx) para o analista distribuir aos clientes.
- Tabela NCM × anexos da LC 214 (cesta básica, 60%, 30%) para sugerir a classificação provável de cada item, não só conferir a escolhida.
- Atualizar tabela cClassTrib pela versão oficial vigente.

## v0.3 — primeira versão paga

- Login por escritório e histórico mensal por cliente (com consentimento e retenção curta).
- Explicação de cada achado em linguagem simples gerada por IA, revisada por regra fixa.
- Importação direta da pasta de XML exportada por Domínio, Questor e Alterdata.
- NFS-e (padrão nacional) e CT-e.

## Depois

- CST 620 (combustíveis), crédito presumido, Imposto Seletivo.
- Conferência de notas de entrada (créditos que o cliente pode estar perdendo).
- Alertas automáticos por e-mail/WhatsApp quando um cliente emitir nota com erro.
