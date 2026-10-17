# Ligar o Mercado Pago

Sem configuração, o Conferente roda em **modo simulado**: uma faixa amarela no topo avisa, e o "pagamento" é uma tela com os botões "aprovar" e "recusar". Serve para ver o fluxo inteiro sem conta nenhuma.

## 1. Criar a aplicação (uma vez)

1. Entre em https://www.mercadopago.com.br/developers com a sua conta do Mercado Pago (pode ser de CPF).
2. Clique em **Suas integrações → Criar aplicação**. Nome: `Conferente`. Escolha **Pagamentos on-line** e o produto **Checkout Pro**.
3. Na aplicação, abra **Contas de teste** e crie duas contas do Brasil: uma **Vendedor** e uma **Comprador**. Anote usuário e senha de cada uma.

## 2. Testar com dinheiro de mentira

1. Entre no painel de desenvolvedor com a **conta de teste Vendedor**, abra a aplicação e copie o **Access Token** das credenciais (começa com `APP_USR-`).
2. Na pasta do projeto, copie `.env.exemplo` para `.env` e cole o token:
   ```
   MP_ACCESS_TOKEN=APP_USR-...
   ```
3. Feche a janela do Conferente e abra `iniciar.bat` de novo. A faixa amarela some.
4. Crie uma conta no Conferente, clique em **Pagar** num plano e depois em **Abrir a página de pagamento**.
5. No Mercado Pago, entre com a **conta de teste Comprador** e pague. Para cartão, use os cartões de teste da documentação do Mercado Pago, com o nome do titular `APRO` para aprovar ou `OTHE` para recusar.
6. Volte para a aba do Conferente: em até 5 segundos a página mostra "Pagamento aprovado" e o acesso é estendido em 30 dias.

## 3. Cobrar de verdade

1. No painel, use as **credenciais de produção** da sua conta real e cole o novo token no `.env`.
2. Faça um pagamento real de um plano para confirmar (dá para estornar depois pelo Mercado Pago).

## Por que o retorno não é automático no seu computador

O Mercado Pago não aceita voltar para endereços locais (`127.0.0.1`). Por isso, rodando no seu computador, o pagamento abre em outra aba e a página **Minha conta** confere sozinha a cada 5 segundos, consultando a API do Mercado Pago. Quando o sistema estiver num endereço público (definido em `BASE_URL`), ele passa a usar o retorno automático e o aviso de pagamento (`/pagamento/notificacao`).

## Segurança

- O acesso só é liberado depois que o Conferente consulta o pagamento direto na API e confere referência, situação e valor. Os dados que voltam na URL nunca liberam acesso sozinhos.
- O arquivo `.env` tem a sua chave secreta e **não vai para o GitHub** (está no `.gitignore`). Não envie esse arquivo para ninguém.
