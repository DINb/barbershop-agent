"""
agent_orchestrator.py
----------------------
Agente conversacional para atendimento da barbearia, usando a Groq API
(Llama 3.3) com tool-calling — mesmo padrão do oic-fusion-incident-agent.

Fluxo:
1. Cliente manda mensagem em linguagem natural.
2. Se ainda não há consentimento LGPD registrado para o telefone informado,
   o agente PRECISA obter o consentimento antes de chamar qualquer tool que
   grave dados pessoais (create_appointment). Isso é reforçado tanto no
   system prompt quanto em uma verificação de código (defesa em profundidade
   -- não confiamos só no LLM para cumprir a regra).
3. O modelo decide, via tool-calling, qual função chamar (RAG, disponibilidade,
   criar/cancelar/remarcar agendamento, notificar, ou os endpoints de LGPD).
4. O resultado da tool volta pro modelo, que formula a resposta final.
"""

import json
import os

from groq import Groq

import mock_api
import lgpd_compliance as lgpd
import human_handoff
from rag_knowledge import build_knowledge_base

MODEL = "openai/gpt-oss-120b"

KB = build_knowledge_base()

SYSTEM_PROMPT = """Você é o assistente virtual da Barbearia Corte Certo, responsável por:
- Tirar dúvidas sobre serviços, preços e horários (use a tool consultar_servicos).
- Consultar horários disponíveis (tool consultar_disponibilidade).
- Criar, cancelar e remarcar agendamentos.
- Enviar confirmações e lembretes.

REGRA CRÍTICA DE PRIVACIDADE (LGPD):
Antes de criar um agendamento pela primeira vez para um cliente, você DEVE
apresentar o texto de consentimento (tool obter_texto_consentimento) e só
prosseguir com criar_agendamento depois que o cliente responder afirmativamente
e você tiver chamado registrar_consentimento com aceito=true. Nunca colete ou
grave nome/telefone sem esse passo. Se o cliente pedir para apagar os dados
dele, use a tool apagar_meus_dados. Se pedir para ver os dados dele, use
consultar_meus_dados.

REGRA DE TRANSFERÊNCIA PARA HUMANO:
Chame a tool transferir_para_humano nestas situações, sem tentar resolver
sozinho:
- O cliente pede explicitamente para falar com uma pessoa/atendente.
- O cliente demonstra insatisfação, reclamação ou frustração (ex: sobre um
  atendimento anterior, cobrança, qualidade do serviço).
- O pedido é uma exceção às regras normais (ex: desconto especial,
  remarcação fora da política, horário fora do funcionamento).
- A pergunta está fora do seu escopo (não é sobre agendamento, serviços,
  horários ou dados pessoais).
- Você tentou ajudar 2 vezes seguidas na mesma dúvida e não conseguiu.
Depois de chamar essa tool, informe ao cliente de forma acolhedora que
alguém da equipe vai continuar o atendimento em breve.

Seja objetivo, cordial, e sempre confirme os detalhes (serviço, data, hora)
antes de efetivar uma ação. Datas devem estar no formato YYYY-MM-DD."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_servicos",
            "description": "Busca na base de conhecimento informações sobre serviços, preços, duração, horário de funcionamento ou equipe de barbeiros.",
            "parameters": {
                "type": "object",
                "properties": {"pergunta": {"type": "string"}},
                "required": ["pergunta"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_disponibilidade",
            "description": "Consulta horários livres em uma data específica.",
            "parameters": {
                "type": "object",
                "properties": {
                    "data": {"type": "string", "description": "YYYY-MM-DD"},
                    "servico_id": {"type": "string"},
                    "barbeiro_id": {"type": "string"},
                },
                "required": ["data"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "obter_texto_consentimento",
            "description": "Retorna o texto de consentimento LGPD que deve ser apresentado ao cliente antes de coletar dados pessoais.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "registrar_consentimento",
            "description": "Registra a decisão do cliente sobre o uso de seus dados pessoais.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cliente_nome": {"type": "string"},
                    "cliente_telefone": {"type": "string"},
                    "aceito": {"type": "boolean"},
                },
                "required": ["cliente_nome", "cliente_telefone", "aceito"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "criar_agendamento",
            "description": "Cria um novo agendamento. Só pode ser chamada após consentimento LGPD registrado.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cliente_nome": {"type": "string"},
                    "cliente_telefone": {"type": "string"},
                    "servico_id": {"type": "string"},
                    "data": {"type": "string"},
                    "hora": {"type": "string"},
                    "barbeiro_id": {"type": "string"},
                },
                "required": ["cliente_nome", "cliente_telefone", "servico_id", "data", "hora"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancelar_agendamento",
            "description": "Cancela um agendamento existente pelo ID.",
            "parameters": {
                "type": "object",
                "properties": {"appointment_id": {"type": "string"}},
                "required": ["appointment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remarcar_agendamento",
            "description": "Remarca um agendamento existente para nova data/hora.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {"type": "string"},
                    "nova_data": {"type": "string"},
                    "nova_hora": {"type": "string"},
                },
                "required": ["appointment_id", "nova_data", "nova_hora"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "enviar_notificacao",
            "description": "Envia uma notificação (confirmação/lembrete/cancelamento) ao cliente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cliente_telefone": {"type": "string"},
                    "mensagem": {"type": "string"},
                    "tipo": {"type": "string"},
                },
                "required": ["cliente_telefone", "mensagem"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_meus_dados",
            "description": "Retorna os dados pessoais e agendamentos armazenados de um cliente (direito de acesso, LGPD art. 18).",
            "parameters": {
                "type": "object",
                "properties": {"cliente_telefone": {"type": "string"}},
                "required": ["cliente_telefone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "apagar_meus_dados",
            "description": "Anonimiza/apaga os dados pessoais de um cliente a pedido dele (direito ao esquecimento, LGPD art. 18, VI).",
            "parameters": {
                "type": "object",
                "properties": {"cliente_telefone": {"type": "string"}},
                "required": ["cliente_telefone"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "transferir_para_humano",
            "description": "Transfere a conversa para um atendente humano, notificando o dono do negócio. Use quando o cliente pedir, demonstrar insatisfação, pedir uma exceção às regras, ou fizer uma pergunta fora do escopo do agente.",
            "parameters": {
                "type": "object",
                "properties": {
                    "cliente_telefone": {"type": "string"},
                    "motivo": {
                        "type": "string",
                        "description": "Categoria curta, ex: 'pedido explícito', 'reclamação', 'excecao_de_regra', 'fora_de_escopo'",
                    },
                    "resumo": {
                        "type": "string",
                        "description": "Resumo em 1-2 frases do que o cliente precisa, para o dono entender rápido o contexto.",
                    },
                },
                "required": ["cliente_telefone", "motivo", "resumo"],
            },
        },
    },
]


def _execute_tool(name: str, args: dict) -> dict:
    if name == "consultar_servicos":
        resultados = KB.search(args["pergunta"], top_k=3)
        return {"resultados": [r["text"] for r in resultados]}

    if name == "consultar_disponibilidade":
        return mock_api.check_availability(
            data=args["data"],
            servico_id=args.get("servico_id"),
            barbeiro_id=args.get("barbeiro_id"),
        )

    if name == "obter_texto_consentimento":
        return {"texto": lgpd.ConsentManager.request_consent_text()}

    if name == "registrar_consentimento":
        return lgpd.ConsentManager.register_consent(
            cliente_nome=args["cliente_nome"],
            cliente_telefone=args["cliente_telefone"],
            aceito=args["aceito"],
        )

    if name == "criar_agendamento":
        # Defesa em profundidade: não confia só no prompt, verifica em código.
        if not lgpd.ConsentManager.has_valid_consent(args["cliente_telefone"]):
            return {
                "sucesso": False,
                "erro": "CONSENTIMENTO_AUSENTE",
                "mensagem": "É necessário obter e registrar o consentimento do cliente antes de criar o agendamento.",
            }
        return mock_api.create_appointment(
            cliente_nome=args["cliente_nome"],
            cliente_telefone=args["cliente_telefone"],
            servico_id=args["servico_id"],
            data=args["data"],
            hora=args["hora"],
            barbeiro_id=args.get("barbeiro_id", "barb_001"),
        )

    if name == "cancelar_agendamento":
        return mock_api.cancel_appointment(args["appointment_id"])

    if name == "remarcar_agendamento":
        return mock_api.reschedule_appointment(
            args["appointment_id"], args["nova_data"], args["nova_hora"]
        )

    if name == "enviar_notificacao":
        return mock_api.send_notification(
            cliente_telefone=args["cliente_telefone"],
            mensagem=args["mensagem"],
            tipo=args.get("tipo", "confirmacao"),
        )

    if name == "consultar_meus_dados":
        return lgpd.DataSubjectRights.get_my_data(args["cliente_telefone"])

    if name == "apagar_meus_dados":
        return lgpd.DataSubjectRights.forget_me(args["cliente_telefone"])

    if name == "transferir_para_humano":
        return human_handoff.notify_owner(
            cliente_telefone=args["cliente_telefone"],
            motivo=args["motivo"],
            resumo=args["resumo"],
        )

    return {"erro": f"Tool desconhecida: {name}"}


class BarbershopAgent:
    def __init__(self, api_key: str = None):
        self.client = Groq(api_key=api_key or os.environ.get("GROQ_API_KEY"))
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    def chat(self, user_message: str) -> str:
        self.messages.append({"role": "user", "content": user_message})

        # Loop de tool-calling: o modelo pode encadear várias chamadas
        # antes de responder em linguagem natural (igual ao incident-agent).
        for _ in range(6):
            response = self.client.chat.completions.create(
                model=MODEL,
                messages=self.messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.3,
            )
            msg = response.choices[0].message

            if not msg.tool_calls:
                self.messages.append({"role": "assistant", "content": msg.content})
                return msg.content

            self.messages.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [tc.model_dump() for tc in msg.tool_calls],
            })

            for tool_call in msg.tool_calls:
                args = json.loads(tool_call.function.arguments)
                result = _execute_tool(tool_call.function.name, args)
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

        return "Desculpe, não consegui concluir a solicitação. Pode tentar reformular?"
