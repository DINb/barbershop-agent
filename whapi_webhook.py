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

Mudanças nesta versão (fix do ReadTimeout -> 500):
- /webhook responde 200 IMEDIATAMENTE e processa as mensagens em background,
  para que uma chamada lenta à Whapi/Groq nunca segure a resposta do webhook.
- send_whatsapp_message agora tem retry automático (via tenacity) em caso de
  ReadTimeout/ConnectionError, e timeout de conexão/leitura separados.
- Erros durante o processamento em background são logados, nunca propagam
  para derrubar o endpoint com 500.
"""

import logging
import os
import requests
from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, Request, Response
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from agent_orchestrator import BarbershopAgent
import human_handoff

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("whapi_webhook")

app = FastAPI(title="Barbearia Whapi Cloud Webhook")

WHAPI_TOKEN = os.environ.get("WHAPI_TOKEN")
WHAPI_SEND_TEXT_URL = "https://gate.whapi.cloud/messages/text"

# Sufixos de chat_id que o bot deve ignorar -- grupos, canais/newsletters e
# listas de transmissão não são conversas de atendimento individual.
IGNORED_CHAT_SUFFIXES = ("@g.us", "@newsletter", "@broadcast")

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


@retry(
    reraise=True,
    stop=stop_after_attempt(3),                        # até 3 tentativas
    wait=wait_exponential(multiplier=1, min=1, max=8),  # espera 1s, 2s, 4s...
    retry=retry_if_exception_type(
        (requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError)
    ),
)
def send_whatsapp_message(phone: str, message: str) -> dict:
    headers = {
        "Authorization": f"Bearer {WHAPI_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {"to": _normalizar_numero(phone), "body": message}
    # (timeout_conexao, timeout_leitura) -- separa o tempo pra conectar do
    # tempo pra Whapi responder, evita travar indefinidamente num só valor
    resp = requests.post(
        WHAPI_SEND_TEXT_URL, headers=headers, json=payload, timeout=(5, 20)
    )
    resp.raise_for_status()
    return resp.json()


# Registra esta função como o "canal" usado para avisar o dono do negócio
# quando o agente decidir transferir uma conversa para atendimento humano.
human_handoff.register_notifier(send_whatsapp_message)


def process_messages(body: dict):
    """Processa as mensagens recebidas em background, fora do ciclo de
    request/response do webhook. Nenhum erro aqui derruba o endpoint."""
    for message in body.get("messages", []):
        try:
            # Ignora mensagens enviadas pelo próprio número conectado (from_me=True)
            # e qualquer coisa que não seja mensagem de texto simples.
            if message.get("from_me"):
                continue

            chat_id = message.get("chat_id", "")
            texto = message.get("text", {}).get("body", "").strip()

            if not chat_id:
                continue

            # Ignora grupos, canais e listas de transmissão -- o bot só
            # atende conversas individuais (chat_id termina em @s.whatsapp.net).
            if any(chat_id.endswith(suf) for suf in IGNORED_CHAT_SUFFIXES):
                logger.info(f"Ignorando mensagem de chat não-individual: {chat_id}")
                continue

            if not texto:
                send_whatsapp_message(
                    chat_id, "Por enquanto só consigo entender mensagens de texto :)"
                )
                continue

            agent = get_agent_for(chat_id)
            resposta = agent.chat(texto)
            send_whatsapp_message(chat_id, resposta)

        except requests.exceptions.RequestException as e:
            # esgotou as tentativas de retry ao enviar pela Whapi
            logger.error(f"Falha ao enviar mensagem via Whapi (chat_id={chat_id}): {e}")

        except Exception as e:
            # erro de parsing, lógica do agente, etc. -- loga e segue pro próximo
            logger.exception(f"Erro inesperado processando mensagem (chat_id={chat_id}): {e}")


@app.post("/webhook")
async def receive_message(request: Request, background_tasks: BackgroundTasks):
    """Recebe o evento de mensagem que a Whapi Cloud envia.
    Responde 200 imediatamente e processa em background, para que uma
    chamada lenta à Whapi ou à Groq nunca vire timeout/500 no webhook."""
    body = await request.json()

    background_tasks.add_task(process_messages, body)

    return Response(status_code=200)


@app.get("/")
def health_check():
    return {"status": "online", "service": "Barbearia Whapi Cloud Webhook"}