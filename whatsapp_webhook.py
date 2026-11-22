"""
whapi_webhook.py
-------------------
Versão do servidor webhook usando a Whapi Cloud (sandbox gratuito) em vez
da Meta Cloud API ou da Z-API. Mesma lógica das outras duas versões --
o agente conversacional (agent_orchestrator.py, com Groq + tool-calling)
continua sendo o "cérebro"; este arquivo só troca a "porta de entrada" e o
formato de envio/recebimento de mensagem para o padrão da Whapi Cloud.

Whapi Cloud conecta via QR code no seu WhatsApp comum (como o WhatsApp
Web) e tem um sandbox gratuito para sempre, sem taxa por mensagem -- ótimo
para a fase de testes/demo.

Variáveis de ambiente necessárias (veja .env):
- GROQ_API_KEY   -> mesma chave já usada no agent_orchestrator.py
- WHAPI_TOKEN    -> token do canal, copiado do painel da Whapi Cloud
- OWNER_PHONE    -> (opcional) número do dono, para receber transferências humanas
"""

import os
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response

from agent_orchestrator import BarbershopAgent
import human_handoff

load_dotenv()

app = FastAPI(title="Barbearia Whapi Cloud Webhook")

WHAPI_TOKEN = os.environ.get("WHAPI_TOKEN")
WHAPI_SEND_TEXT_URL = "https://gate.whapi.cloud/messages/text"

# Um agente por número de cliente, mantendo o histórico de cada conversa separado.
agents_by_phone: dict[str, BarbershopAgent] = {}


def get_agent_for(phone: str) -> BarbershopAgent:
    if phone not in agents_by_phone:
        agents_by_phone[phone] = BarbershopAgent()
    return agents_by_phone[phone]


def _normalizar_numero(chat_id: str) -> str:
    """A Whapi manda o chat_id como '5581999998888@s.whatsapp.net'.
    Para enviar uma mensagem, o campo 'to' espera só os números."""
    return chat_id.split("@")[0]


def send_whatsapp_message(phone: str, message: str) -> dict:
    headers = {
        "Authorization": f"Bearer {WHAPI_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"to": _normalizar_numero(phone), "body": message}
    resp = requests.post(WHAPI_SEND_TEXT_URL, headers=headers, json=payload, timeout=15)
    resp.raise_for_status()
    return resp.json()


# Registra esta função como o "canal" usado para avisar o dono do negócio
# quando o agente decidir transferir uma conversa para atendimento humano.
human_handoff.register_notifier(send_whatsapp_message)


@app.post("/webhook")
async def receive_message(request: Request):
    """Recebe o evento de mensagem que a Whapi Cloud envia."""
    body = await request.json()

    for message in body.get("messages", []):
        # Ignora mensagens enviadas pelo próprio número conectado (from_me=True)
        # e qualquer coisa que não seja mensagem de texto simples.
        if message.get("from_me"):
            continue

        chat_id = message.get("chat_id", "")
        texto = message.get("text", {}).get("body", "").strip()

        if not chat_id:
            continue

        if not texto:
            send_whatsapp_message(chat_id, "Por enquanto só consigo entender mensagens de texto :)")
            continue

        agent = get_agent_for(chat_id)
        resposta = agent.chat(texto)
        send_whatsapp_message(chat_id, resposta)

    return Response(status_code=200)


@app.get("/")
def health_check():
    return {"status": "online", "service": "Barbearia Whapi Cloud Webhook"}