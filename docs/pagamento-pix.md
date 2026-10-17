# Receber por Pix direto na sua conta

Sem empresa de pagamento no meio e sem taxa. O escritório paga o Pix e você confirma.

## Ligar

1. Na pasta do projeto, copie `configuracao-exemplo.txt` com o nome `configuracao.txt`.
2. Abra `configuracao.txt` no Bloco de Notas e preencha:
   ```
   PIX_CHAVE=seu@email.com
   PIX_NOME=Seu Nome Completo
   PIX_CIDADE=Campinas
   ADMIN_SENHA=uma-senha-so-sua
   ```
   - Chave por telefone: escreva com +55, por exemplo `+5519999999999`.
   - Chave por CPF: só os números.
3. Feche a janela do Conferente e abra `iniciar.bat` de novo. A faixa amarela de "demonstração" some.

## Como funciona para o escritório

1. Em **Minha conta**, clica em **Pagar** num plano.
2. Vê o QR Code e o Pix copia e cola, já com o valor e um **identificador** da cobrança (ex.: `CF12643b4028373`).
3. Paga pelo app do banco e clica em **Já paguei**.
4. A tela mostra "Em conferência" e se atualiza sozinha quando você confirmar.

## Como funciona para você

1. Abra **http://127.0.0.1:8000/admin** e entre com a `ADMIN_SENHA`.
2. Em **Pix para conferir** aparecem as cobranças, com os escritórios que já avisaram que pagaram no topo.
3. Abra o extrato do seu banco e procure um Pix com o **mesmo valor**. Muitos bancos mostram o identificador; se o seu não mostrar, confira pelo nome de quem pagou e pela data.
4. Clique em **Confirmar recebimento**. O escritório ganha 30 dias na hora. Se o dinheiro não entrou, clique em **Não recebi**.

Só confirme o que você viu entrar na conta: o sistema não tem como consultar o seu banco sozinho.

## Cuidados

- O `configuracao.txt` não vai para o GitHub (está no `.gitignore`).
- Antes de cobrar muitos escritórios, vale abrir um MEI e receber numa chave Pix do CNPJ, para emitir nota fiscal e separar o dinheiro do negócio.
