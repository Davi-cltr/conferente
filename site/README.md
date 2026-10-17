# Vitrine (Netlify)

No ar em **https://conferent.netlify.app** (publica sozinho a cada `git push` na branch `main`).

Página de apresentação do Conferente para mandar a possíveis clientes. É estática: não roda o sistema, só mostra o produto, o relatório de exemplo e um formulário para pedir o teste grátis.

| Arquivo | O que é |
|---|---|
| `index.html` | Página de apresentação com planos e formulário |
| `exemplo.html` | Relatório de exemplo (gerado por `python scripts/gerar_vitrine.py`) |
| `obrigado.html` | Página que aparece depois que alguém envia o formulário |

## Publicar no Netlify (uma vez)

1. Crie uma conta grátis em https://app.netlify.com (pode entrar com o GitHub).
2. **Add new site → Import an existing project → GitHub** e escolha o repositório `conferente`.
3. O Netlify lê o `netlify.toml` sozinho: pasta `site`, sem build. Clique em **Deploy**.
4. Em **Site configuration → Change site name**, escolha um nome, por exemplo `conferente-fiscal`. O endereço fica `https://conferente-fiscal.netlify.app`.
5. Em **Forms**, clique em **Enable form detection** e faça um novo deploy (**Deploys → Trigger deploy**). Sem isso, o formulário não é registrado.
6. Em **Forms → Form notifications → Add notification → Email notification**, coloque o seu e-mail. Cada pedido de teste chega na sua caixa.

Depois disso, cada `git push` atualiza o site sozinho.

O plano grátis do Netlify recebe até 100 envios de formulário por mês.

## Testar

Envie o formulário você mesmo e confira se o e-mail chegou e se o pedido aparece em **Forms** no painel do Netlify.
