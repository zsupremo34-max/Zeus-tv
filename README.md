# Zeus IA — WhatsApp Bot

Webhook em Python para WhatsApp Business Cloud API oficial da Meta. Inclui busca por música que responde com links de pesquisa oficiais do YouTube e YouTube Music; não baixa nem envia áudio.

## Deploy inicial no Render (plano gratuito)

1. Crie um Web Service conectado a este repositório, runtime **Python**, branch `main`.
2. Build command vazio; start command `python bot.py`; health check `/health`.
3. Se usar `render.yaml`, confirme que o plano selecionado é Free. A configuração não contém serviços pagos.
4. Configure as variáveis secretas indicadas em `render.yaml` no dashboard do Render. Nunca as salve no GitHub.
5. A instância Free pode suspender por inatividade e não garante armazenamento persistente; o SQLite local e a deduplicação podem ser reiniciados. Avalie persistência e requisitos atuais antes de produção.

## WhatsApp Cloud API

Configure um app Meta com WhatsApp Business Platform, número de teste e webhook HTTPS `/webhook`; use o mesmo `WHATSAPP_VERIFY_TOKEN` e configure `META_APP_SECRET`, token de acesso e `WHATSAPP_PHONE_NUMBER_ID`. Assine o evento `messages`. Teste com número de sandbox antes de produção.

Docs Meta: https://developers.facebook.com/documentation/business-messaging/whatsapp/get-started

## Recursos do bot

- `oi`, `menu` e `ajuda`: mostra menu
- `música <artista/faixa>`: retorna links oficiais de busca do YouTube e YouTube Music; não baixa música
- opções de brainstorming de imagem, roteiro e legenda
- SQLite local para deduplicação e contexto de conversas

## Segurança

Não adicione tokens ou chaves ao repositório. Use as variáveis secretas do host. Proteja o endpoint público, mantenha `META_APP_SECRET` e revise termos, privacidade, consentimento e regras atuais da Meta antes de usar com clientes.
