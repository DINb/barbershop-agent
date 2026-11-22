"""
test_chat_server.py
--------------------
Servidor de TESTE que conversa diretamente com o BarbershopAgent, sem
passar pela Whapi. Serve para:
  1) Testar a lógica do agente (RAG, disponibilidade, LGPD, agendamento)
     sem limite de cota nem custo -- é só a sua própria máquina chamando
     a Groq.
  2) Gravar o vídeo de demonstração com uma interface de chat, mostrando
     o agente real respondendo (não um mockup, não o Playground "pelado").

Isso NÃO substitui o whapi_webhook.py para produção -- é uma ferramenta
de desenvolvimento/demo. Quando for atender clientes de verdade pelo
WhatsApp, use o whapi_webhook.py (ou a integração de mensageria que você
escolher).

Como rodar:
    uvicorn test_chat_server:app --reload --port 8001

Depois abra no navegador:
    http://127.0.0.1:8001
"""

import uuid

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

load_dotenv(override=True)  # força o .env a vencer, mesmo se houver uma
                             # variável de ambiente (vazia ou não) já definida
                             # na sessão do terminal

from agent_orchestrator import BarbershopAgent

app = FastAPI(title="Barbearia Corte Certo - Chat de Teste")

# Um agente por sessão de navegador, igual ao padrão usado no whapi_webhook.py
# (agents_by_phone), só que aqui a "chave" é um id de sessão gerado no navegador.
agents_by_session: dict[str, BarbershopAgent] = {}


class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    if req.session_id not in agents_by_session:
        agents_by_session[req.session_id] = BarbershopAgent()

    agent = agents_by_session[req.session_id]
    resposta = agent.chat(req.message)
    return ChatResponse(reply=resposta)


@app.post("/api/reset")
def reset(session_id: str):
    """Limpa o histórico de uma sessão, para recomeçar um teste do zero."""
    agents_by_session.pop(session_id, None)
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_PAGE


HTML_PAGE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Corte Certo — Chat de Teste</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,500;9..144,600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root {
    --charcoal: #1c1b1a;
    --charcoal-soft: #2a2826;
    --paper: #f6f1e7;
    --paper-dim: #ece4d3;
    --brass: #b08d57;
    --barber-red: #a13d2f;
    --ink: #2a2622;
    --ink-soft: #6b6357;
  }

  * { box-sizing: border-box; }

  html, body {
    margin: 0;
    height: 100%;
    background: var(--charcoal);
    font-family: 'Inter', sans-serif;
    color: var(--ink);
  }

  body {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 32px 16px;
  }

  .stage {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 18px;
  }

  .brand {
    text-align: center;
  }

  .brand .eyebrow {
    font-family: 'Inter', sans-serif;
    font-size: 12px;
    letter-spacing: 0.14em;
    color: var(--brass);
    margin: 0 0 4px;
  }

  .brand h1 {
    font-family: 'Fraunces', serif;
    font-weight: 600;
    font-size: 26px;
    color: var(--paper);
    margin: 0;
  }

  .phone {
    width: 380px;
    max-width: 92vw;
    height: 700px;
    max-height: 82vh;
    background: var(--paper);
    border-radius: 34px;
    border: 10px solid var(--charcoal-soft);
    box-shadow: 0 30px 60px rgba(0,0,0,0.45), 0 0 0 1px rgba(176,141,87,0.15);
    display: flex;
    flex-direction: column;
    overflow: hidden;
    position: relative;
  }

  .phone::before {
    content: "";
    position: absolute;
    top: 8px;
    left: 50%;
    transform: translateX(-50%);
    width: 90px;
    height: 5px;
    border-radius: 3px;
    background: rgba(0,0,0,0.35);
    z-index: 5;
  }

  .chat-header {
    background: var(--charcoal);
    color: var(--paper);
    padding: 22px 18px 14px;
    display: flex;
    align-items: center;
    gap: 12px;
    border-bottom: 2px solid var(--brass);
  }

  .avatar {
    width: 38px;
    height: 38px;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--brass), var(--barber-red));
    display: flex;
    align-items: center;
    justify-content: center;
    font-family: 'Fraunces', serif;
    font-weight: 600;
    font-size: 16px;
    color: var(--paper);
    flex-shrink: 0;
  }

  .chat-header .who { line-height: 1.25; }
  .chat-header .name { font-weight: 600; font-size: 15px; }
  .chat-header .status {
    font-size: 12px;
    color: #8fbf8f;
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .chat-header .status::before {
    content: "";
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: #6fcf6f;
    display: inline-block;
  }

  .messages {
    flex: 1;
    overflow-y: auto;
    padding: 18px 14px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    background:
      radial-gradient(circle at 20% 10%, rgba(176,141,87,0.06), transparent 40%),
      var(--paper);
  }

  .bubble {
    max-width: 78%;
    padding: 10px 13px;
    border-radius: 14px;
    font-size: 14.5px;
    line-height: 1.42;
    white-space: pre-wrap;
    word-wrap: break-word;
  }

  .bubble.agent {
    align-self: flex-start;
    background: #ffffff;
    border: 1px solid rgba(0,0,0,0.06);
    border-top-left-radius: 4px;
    color: var(--ink);
  }

  .bubble.user {
    align-self: flex-end;
    background: var(--charcoal);
    color: var(--paper);
    border-top-right-radius: 4px;
  }

  .bubble.typing {
    align-self: flex-start;
    background: #ffffff;
    border: 1px solid rgba(0,0,0,0.06);
    border-top-left-radius: 4px;
    display: flex;
    gap: 4px;
    padding: 12px 14px;
  }

  .dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--ink-soft);
    animation: blink 1.2s infinite ease-in-out;
  }
  .dot:nth-child(2) { animation-delay: 0.15s; }
  .dot:nth-child(3) { animation-delay: 0.3s; }

  @keyframes blink {
    0%, 80%, 100% { opacity: 0.25; }
    40% { opacity: 1; }
  }

  .composer {
    display: flex;
    gap: 8px;
    padding: 12px;
    background: var(--paper-dim);
    border-top: 1px solid rgba(0,0,0,0.06);
  }

  .composer input {
    flex: 1;
    border: none;
    border-radius: 20px;
    padding: 11px 16px;
    font-family: 'Inter', sans-serif;
    font-size: 14px;
    background: #ffffff;
    color: var(--ink);
    outline: none;
  }

  .composer input:focus {
    box-shadow: 0 0 0 2px var(--brass);
  }

  .composer button {
    border: none;
    background: var(--barber-red);
    color: var(--paper);
    width: 42px;
    height: 42px;
    border-radius: 50%;
    font-size: 16px;
    cursor: pointer;
    flex-shrink: 0;
    transition: transform 0.15s ease;
  }

  .composer button:hover { transform: scale(1.05); }
  .composer button:disabled { opacity: 0.5; cursor: default; }

  .reset {
    background: none;
    border: none;
    color: rgba(246,241,231,0.55);
    font-size: 12px;
    cursor: pointer;
    text-decoration: underline;
  }

  .reset:hover { color: var(--paper); }
</style>
</head>
<body>

<div class="stage">
  <div class="brand">
    <h1>Barbearia Corte Certo</h1>
  </div>

  <div class="phone">
    <div class="chat-header">
      <div class="avatar">CC</div>
      <div class="who">
        <div class="name">Corte Certo — Atendimento</div>
        <div class="status">online</div>
      </div>
    </div>
    <div class="messages" id="messages"></div>
    <div class="composer">
      <input id="input" type="text" placeholder="Digite uma mensagem..." autocomplete="off">
      <button id="send" title="Enviar">➤</button>
    </div>
  </div>

  <button class="reset" id="resetBtn">reiniciar conversa</button>
</div>

<script>
  const sessionKey = 'cortecerto_session_id';
  let sessionId = localStorage.getItem(sessionKey);
  if (!sessionId) {
    sessionId = crypto.randomUUID();
    localStorage.setItem(sessionKey, sessionId);
  }

  const messagesEl = document.getElementById('messages');
  const inputEl = document.getElementById('input');
  const sendBtn = document.getElementById('send');
  const resetBtn = document.getElementById('resetBtn');

  function addBubble(text, who) {
    const div = document.createElement('div');
    div.className = 'bubble ' + who;
    div.textContent = text;
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  function addTyping() {
    const div = document.createElement('div');
    div.className = 'bubble typing';
    div.innerHTML = '<span class="dot"></span><span class="dot"></span><span class="dot"></span>';
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  async function sendMessage() {
    const text = inputEl.value.trim();
    if (!text) return;

    addBubble(text, 'user');
    inputEl.value = '';
    sendBtn.disabled = true;

    const typingEl = addTyping();

    try {
      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sessionId, message: text })
      });
      const data = await resp.json();
      typingEl.remove();
      addBubble(data.reply, 'agent');
    } catch (err) {
      typingEl.remove();
      addBubble('Erro ao conectar com o servidor. Confira se o uvicorn está rodando.', 'agent');
    } finally {
      sendBtn.disabled = false;
      inputEl.focus();
    }
  }

  sendBtn.addEventListener('click', sendMessage);
  inputEl.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') sendMessage();
  });

  resetBtn.addEventListener('click', async () => {
    await fetch('/api/reset?session_id=' + sessionId, { method: 'POST' });
    messagesEl.innerHTML = '';
    localStorage.removeItem(sessionKey);
    location.reload();
  });

  addBubble('Olá! 👋 Sou o assistente da Barbearia Corte Certo. Posso te ajudar com informações sobre serviços, horários ou agendar seu próximo corte. Como posso ajudar?', 'agent');
</script>

</body>
</html>
"""
