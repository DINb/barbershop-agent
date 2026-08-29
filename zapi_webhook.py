"""
zapi_webhook.py
------------------
Versão do servidor webhook usando a Z-API em vez da Meta Cloud API.
Mesma lógica do whatsapp_webhook.py, só troca a "porta de entrada" e o
formato de envio/recebimento de mensagem para o padrão da Z-API.

Z-API conecta via QR code no seu WhatsApp comum (não precisa de número de
teste, nem de aprovação da Meta) — ótimo para destravar a demo rapidamente.

Variáveis de ambiente necessárias (veja .env):
- GROQ_API_KEY      -> mesma chave já usada no agent_orchestrator.py
- ZAPI_INSTANCE_ID  -> ID da instância, copiado do painel da Z-API
- ZAPI_TOKEN        -> token da instância, copiado do painel da Z-API
- ZAPI_CLIENT_TOKEN -> "Client-Token" de conta, copiado do painel da Z-API
"""

import os
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response

from agent_orchestrator import BarbershopAgent
import human_handoff

load_dotenv()

app = FastAPI(title="Barbearia Z-API Webhook")

ZAPI_INSTANCE_ID = os.environ.get("ZAPI_INSTANCE_ID")
ZAPI_TOKEN = os.environ.get("ZAPI_TOKEN")
ZAPI_CLIENT_TOKEN = os.environ.get("ZAPI_CLIENT_TOKEN")
ZAPI_SEND_TEXT_URL = f"https://api.z-api.io/instances/{ZAPI_INSTANCE_ID}/token/{ZAPI_TOKEN}/send-text"

# Um agente por número de cliente, mantendo o histórico de cada conversa separado.
agents_by_phone: dict[str, BarbershopAgent] = {}


def get_agent_for(phone: str) -> BarbershopAgent:
    if phone not in agents_by_phone:
        agents_by_phone[phone] = BarbershopAgent()
    return agents_by_phone[phone]


def send_whatsapp_message(phone: str, message: str) -> dict:
    headers = {
        "Client-Token": ZAPI_CLIENT_TOKEN,
        "Content-Type": "application/json",
    }
    payload = {"phone": phone, "message": message}
    resp = requests.post(ZAPI_SEND_TEXT_URL, headers=headers, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


# Registra esta função como o "canal" usado para avisar o dono do negócio
# quando o agente decidir transferir uma conversa para atendimento humano.
human_handoff.register_notifier(send_whatsapp_message)


@app.post("/webhook")
async def receive_message(request: Request):
    """Recebe o evento de 'mensagem recebida' que a Z-API envia."""
    body = await request.json()

    # Ignora eventos que não são mensagem de texto recebida de um cliente
    # (ex: confirmação de entrega, mensagens enviadas pelo próprio número,
    # mensagens de grupo).
    if body.get("fromMe") or body.get("isGroup"):
        return Response(status_code=200)

    sender_phone = body.get("phone")
    text_block = body.get("text") or {}
    text = text_block.get("message")

    if not sender_phone or not text:
        # Pode ser imagem, áudio, figurinha, etc. -- fora do escopo do POC.
        if sender_phone:
            send_whatsapp_message(sender_phone, "Por enquanto só consigo entender mensagens de texto :)")
        return Response(status_code=200)

    agent = get_agent_for(sender_phone)
    resposta = agent.chat(text)
    send_whatsapp_message(sender_phone, resposta)

    return Response(status_code=200)


@app.get("/")
def health_check():
    return {"status": "online", "service": "Barbearia Z-API Webhook"}
