"""
whatsapp_webhook.py
---------------------
Servidor que conecta o agent_orchestrator.py (já existente) à Meta WhatsApp
Cloud API. Substitui o interactive_cli.py como "porta de entrada" do agente,
sem mudar nada da lógica de negócio, RAG ou LGPD.

Fluxo:
1. Meta manda um POST /webhook toda vez que o cliente envia mensagem no WhatsApp.
2. Extraímos o texto e o número do remetente.
3. Chamamos agent.chat(texto) -- o mesmo agente do CLI.
4. Enviamos a resposta de volta via API da Meta (POST /messages).

Variáveis de ambiente necessárias (veja .env.example):
- GROQ_API_KEY        -> mesma chave já usada no agent_orchestrator.py
- WHATSAPP_TOKEN      -> token de acesso gerado no Meta App Dashboard
- WHATSAPP_PHONE_ID   -> ID do número de teste (Phone Number ID)
- VERIFY_TOKEN        -> palavra-chave que você escolhe, usada na verificação do webhook
"""

import os
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.responses import PlainTextResponse

from agent_orchestrator import BarbershopAgent
import human_handoff

load_dotenv()

app = FastAPI(title="Barbearia WhatsApp Webhook")

WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
WHATSAPP_PHONE_ID = os.environ.get("WHATSAPP_PHONE_ID")
VERIFY_TOKEN = os.environ.get("VERIFY_TOKEN", "barbearia_verify_token")
GRAPH_API_URL = f"https://graph.facebook.com/v21.0/{WHATSAPP_PHONE_ID}/messages"

# Um agente por número de cliente, para manter o histórico de conversa de
# cada pessoa separado (equivalente a uma sessão por usuário).
agents_by_phone: dict[str, BarbershopAgent] = {}


def get_agent_for(phone: str) -> BarbershopAgent:
    if phone not in agents_by_phone:
        agents_by_phone[phone] = BarbershopAgent()
    return agents_by_phone[phone]


def send_whatsapp_message(to: str, text: str) -> dict:
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }
    resp = requests.post(GRAPH_API_URL, headers=headers, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


# Registra esta função como o "canal" usado para avisar o dono do negócio
# quando o agente decidir transferir uma conversa para atendimento humano.
human_handoff.register_notifier(send_whatsapp_message)


@app.get("/webhook")
def verify_webhook(request: Request):
    """A Meta chama esse GET uma vez, ao configurar o webhook, pra confirmar
    que você é dono do endpoint."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    if mode == "subscribe" and token == VERIFY_TOKEN:
        return PlainTextResponse(content=challenge, status_code=200)
    return PlainTextResponse(content="Token de verificação inválido", status_code=403)


@app.post("/webhook")
async def receive_message(request: Request):
    """Recebe as mensagens reais enviadas pelos clientes no WhatsApp."""
    body = await request.json()

    try:
        entry = body["entry"][0]
        change = entry["changes"][0]["value"]

        if "messages" not in change:
            # Pode ser um evento de status (entregue/lido), não uma mensagem nova.
            return Response(status_code=200)

        message = change["messages"][0]
        sender_phone = message["from"]
        text = message.get("text", {}).get("body", "")

        if not text:
            send_whatsapp_message(sender_phone, "Por enquanto só consigo entender mensagens de texto :)")
            return Response(status_code=200)

        agent = get_agent_for(sender_phone)
        resposta = agent.chat(text)
        send_whatsapp_message(sender_phone, resposta)

    except (KeyError, IndexError):
        # Payload que não é uma mensagem de usuário (ex: confirmação de leitura).
        pass

    return Response(status_code=200)


@app.get("/")
def health_check():
    return {"status": "online", "service": "Barbearia WhatsApp Webhook"}
