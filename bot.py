#!/usr/bin/env python3
"""Zeus IA WhatsApp Bot v1 — webhook oficial da WhatsApp Business Cloud API.
Python standard library only. See README.md. Never expose secrets in source code.
"""
import hashlib
import hmac
import json
import os
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOST = os.getenv('HOST', '0.0.0.0')
PORT = int(os.getenv('PORT', '8080'))
VERIFY_TOKEN = os.getenv('WHATSAPP_VERIFY_TOKEN', '')
APP_SECRET = os.getenv('META_APP_SECRET', '')
WA_TOKEN = os.getenv('WHATSAPP_ACCESS_TOKEN', '')
PHONE_NUMBER_ID = os.getenv('WHATSAPP_PHONE_NUMBER_ID', '')
GRAPH_VERSION = os.getenv('WHATSAPP_GRAPH_VERSION', 'v23.0')
OPENAI_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
BOT_NAME = os.getenv('BOT_NAME', 'Zeus IA')
BOT_INFO = os.getenv('BOT_INFO', 'Assistente criativo para ideias de imagens, vídeos, textos e conteúdo para redes sociais.')
DB_PATH = os.getenv('ZEUS_DB_PATH', 'zeus.sqlite3')
LOCK = threading.Lock()

MENU = (
    '⚡ *ZEUS IA — MENU*\n\n'
    'Sou seu assistente criativo. Envie sua ideia ou escolha uma opção:\n\n'
    '1️⃣ Criar ideia para imagem\n'
    '2️⃣ Criar roteiro para vídeo\n'
    '3️⃣ Criar legenda para redes sociais\n'
    '4️⃣ Fazer uma pergunta\n'
    '5️⃣ Buscar música (envie: música <nome da música ou artista>)\n\n'
    'Exemplos: “roteiro de vídeo sobre café” ou “legenda para uma loja de roupas”.\n'
    'Digite *menu* a qualquer momento para ver estas opções.'
)

SYSTEM_PROMPT = (
    'Você é Zeus IA, assistente criativo em português do Brasil no WhatsApp. '
    'Ajude com brainstorming, prompts de imagem, roteiros de vídeos curtos, legendas, '
    'ideias e dúvidas gerais. Seja cordial, conciso e prático. Para pedidos de imagem, '
    'escreva um prompt detalhado para ser usado num gerador externo; não afirme que '
    'gerou um arquivo de imagem ou vídeo. Não peça dados sensíveis. '
    'Se perguntarem sobre o bot, explique que é a versão 1 do Zeus IA.'
)

def db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute('CREATE TABLE IF NOT EXISTS seen (msg_id TEXT PRIMARY KEY, ts INTEGER NOT NULL)')
    conn.execute('CREATE TABLE IF NOT EXISTS history (wa_id TEXT NOT NULL, role TEXT NOT NULL, text TEXT NOT NULL, ts INTEGER NOT NULL)')
    return conn

def is_seen(msg_id):
    if not msg_id:
        return False
    with LOCK, db() as c:
        row = c.execute('SELECT 1 FROM seen WHERE msg_id=?', (msg_id,)).fetchone()
        return row is not None

def mark_seen(msg_id):
    if not msg_id:
        return
    with LOCK, db() as c:
        c.execute('DELETE FROM seen WHERE ts < ?', (int(time.time()) - 7*86400,))
        c.execute('INSERT OR IGNORE INTO seen(msg_id,ts) VALUES(?,?)', (msg_id, int(time.time())))


def already_seen(msg_id):
    """Backward-compatible check-and-mark, not used for webhook reply flow."""
    if is_seen(msg_id):
        return True
    mark_seen(msg_id)
    return False

def load_history(wa_id):
    with LOCK, db() as c:
        rows = c.execute('SELECT role,text FROM history WHERE wa_id=? ORDER BY ts DESC LIMIT 12', (wa_id,)).fetchall()
    return [{'role': role, 'content': text} for role, text in reversed(rows)]

def save_history(wa_id, role, text):
    with LOCK, db() as c:
        c.execute('INSERT INTO history(wa_id,role,text,ts) VALUES(?,?,?,?)', (wa_id, role, text[:12000], int(time.time())))
        c.execute('DELETE FROM history WHERE wa_id=? AND ts < ?', (wa_id, int(time.time()) - 30*86400))

def ai_reply(wa_id, user_text):
    history = load_history(wa_id)
    payload = json.dumps({
        'model': OPENAI_MODEL,
        'instructions': SYSTEM_PROMPT + '\nInformações do projeto: ' + BOT_INFO,
        'input': history + [{'role': 'user', 'content': user_text[:6000]}],
        'max_output_tokens': 500
    }).encode()
    req = urllib.request.Request('https://api.openai.com/v1/responses', data=payload,
        headers={'Authorization': 'Bearer ' + OPENAI_KEY, 'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=40) as res:
        data = json.loads(res.read())
    text = data.get('output_text', '')
    if not text:
        parts = []
        for item in data.get('output', []):
            if item.get('type') == 'message':
                parts.extend(part.get('text', '') for part in item.get('content', []) if part.get('type') == 'output_text')
        text = '\n'.join(parts)
    if not text:
        raise RuntimeError('Resposta vazia do modelo')
    save_history(wa_id, 'user', user_text)
    save_history(wa_id, 'assistant', text)
    return text[:4000]

def local_reply(text):
    t = text.strip().lower()
    if t in ('oi','olá','ola','bom dia','boa tarde','boa noite','menu','ajuda','help','start','início','inicio','0'):
        return 'Olá! ⚡ Eu sou o *Zeus IA*.\n\n' + MENU
    if t in ('1','imagem','criar imagem','ideia para imagem'):
        return '🎨 Me diga o que você quer ver na imagem — tema, estilo e cores — e preparo um prompt bem detalhado. Ex.: “um dragão dourado numa cidade futurista, estilo pintura digital”.'
    if t in ('2','vídeo','video','roteiro','roteiro para vídeo','roteiro para video'):
        return '🎬 Qual é o tema do vídeo e para qual rede? Posso montar um roteiro curto com cenas, falas e texto na tela.'
    if t in ('3','legenda','legenda para redes sociais'):
        return '✍️ Para qual produto, foto ou assunto você precisa de legenda? Diga também o tom: divertido, elegante ou informativo.'
    if t in ('5', 'música', 'musica', 'buscar música', 'buscar musica'):
        return '🎵 Escreva *música* e o nome do artista ou da faixa. Exemplo: *música Elis Regina Como Nossos Pais*. Vou te enviar links oficiais para ouvir.'
    if t.startswith(('música ', 'musica ', 'buscar música ', 'buscar musica ')):
        query = text.strip().split(' ', 1)[1].strip()
        if not query:
            return '🎵 Escreva o artista ou a faixa. Exemplo: *música Elis Regina Como Nossos Pais*.'
        q = urllib.parse.quote_plus(query)
        return ('🎵 Encontrei buscas oficiais para *' + query[:180] + '*:\n\n'
                'YouTube: https://www.youtube.com/results?search_query=' + q + '\n'
                'YouTube Music: https://music.youtube.com/search?q=' + q + '\n\n'
                'O Zeus não baixa nem envia o áudio; os links abrem nos serviços oficiais.')
    if not OPENAI_KEY:
        return ('⚡ Recebi sua mensagem! O Zeus está no modo básico. Para respostas criativas com IA, '
                'o administrador precisa configurar uma chave de API no servidor.\n\n' + MENU)
    return ''

def send_text(to, body):
    if not WA_TOKEN or not PHONE_NUMBER_ID:
        raise RuntimeError('Falta configurar WHATSAPP_ACCESS_TOKEN ou WHATSAPP_PHONE_NUMBER_ID')
    url = f'https://graph.facebook.com/{GRAPH_VERSION}/{PHONE_NUMBER_ID}/messages'
    payload = json.dumps({'messaging_product':'whatsapp','recipient_type':'individual','to':to,
                          'type':'text','text':{'preview_url':False,'body':body[:4000]}}).encode()
    req = urllib.request.Request(url, data=payload, headers={'Authorization':'Bearer '+WA_TOKEN,
        'Content-Type':'application/json'}, method='POST')
    with urllib.request.urlopen(req, timeout=25) as res:
        res.read()

def process(payload):
    if payload.get('object') != 'whatsapp_business_account':
        return
    for entry in payload.get('entry', []):
        for change in entry.get('changes', []):
            value = change.get('value', {})
            for message in value.get('messages', []):
                mid = message.get('id', '')
                if is_seen(mid):
                    continue
                sender = message.get('from', '')
                typ = message.get('type')
                if typ != 'text':
                    send_text(sender, 'Por enquanto consigo responder mensagens de texto. Envie *menu* para ver o que posso fazer.')
                    mark_seen(mid)
                    continue
                text = message.get('text', {}).get('body', '').strip()
                if not text:
                    mark_seen(mid)
                    continue
                answer = local_reply(text)
                if not answer and OPENAI_KEY:
                    try:
                        answer = ai_reply(sender, text)
                    except Exception as e:
                        print('AI error:', repr(e), flush=True)
                        answer = 'Tive um problema ao preparar a resposta. Tente novamente daqui a pouco ou envie *menu*.'
                if answer:
                    try:
                        send_text(sender, answer)
                        mark_seen(mid)
                    except Exception as e:
                        print('WhatsApp send error:', repr(e), flush=True)
                        raise

class Handler(BaseHTTPRequestHandler):
    server_version = 'ZeusWhatsAppBot/1.0'
    def log_message(self, fmt, *args):
        print('%s %s' % (self.log_date_time_string(), fmt % args), flush=True)
    def respond(self, code, body=b'', content_type='text/plain; charset=utf-8'):
        self.send_response(code); self.send_header('Content-Type', content_type)
        self.send_header('Cache-Control','no-store'); self.end_headers(); self.wfile.write(body)
    def do_GET(self):
        if self.path.split('?',1)[0] == '/health':
            status = {'ok':True,'whatsapp_configured':bool(WA_TOKEN and PHONE_NUMBER_ID),'ai_configured':bool(OPENAI_KEY)}
            return self.respond(200, json.dumps(status).encode(), 'application/json')
        if self.path.split('?',1)[0] != '/webhook':
            return self.respond(404, b'Not found')
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        mode = q.get('hub.mode',[''])[0]; token = q.get('hub.verify_token',[''])[0]; challenge = q.get('hub.challenge',[''])[0]
        if mode == 'subscribe' and VERIFY_TOKEN and hmac.compare_digest(token, VERIFY_TOKEN):
            return self.respond(200, challenge.encode())
        return self.respond(403, b'Webhook verification failed')
    def do_POST(self):
        if self.path.split('?',1)[0] != '/webhook':
            return self.respond(404, b'Not found')
        try:
            size = int(self.headers.get('Content-Length','0'))
            if size <= 0 or size > 3_200_000:
                return self.respond(413, b'Payload too large')
            raw = self.rfile.read(size)
            # Verify Meta webhook authenticity whenever app secret is configured.
            signature = self.headers.get('X-Hub-Signature-256','')
            if APP_SECRET:
                expected = 'sha256=' + hmac.new(APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
                if not hmac.compare_digest(signature, expected):
                    return self.respond(401, b'Invalid signature')
            else:
                print('Webhook rejected: META_APP_SECRET is not configured.', flush=True)
                return self.respond(503, b'Webhook is not configured')
            data = json.loads(raw)
            # Acknowledge after request parsing and reply processing. Meta retries on failures;
            # duplicate message ids are recorded so repeats do not send duplicate replies.
            process(data)
            return self.respond(200, b'OK')
        except Exception as e:
            print('Webhook error:', repr(e), flush=True)
            return self.respond(500, b'Webhook processing error')

def main():
    missing = [name for name, val in [('WHATSAPP_VERIFY_TOKEN', VERIFY_TOKEN), ('WHATSAPP_ACCESS_TOKEN', WA_TOKEN), ('WHATSAPP_PHONE_NUMBER_ID', PHONE_NUMBER_ID)] if not val]
    if missing:
        print('WARNING: Missing configuration:', ', '.join(missing), flush=True)
    if not APP_SECRET:
        print('WARNING: Set META_APP_SECRET before connecting a public webhook.', flush=True)
    print(f'{BOT_NAME} v1 webhook listening at http://{HOST}:{PORT}/webhook', flush=True)
    print('Health check: /health. In production use HTTPS, firewall and a managed process.', flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()

if __name__ == '__main__':
    main()
