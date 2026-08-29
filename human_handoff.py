"""
human_handoff.py
------------------
Lógica de transferência de conversa para um atendente humano (o dono do
negócio ou quem ele designar). Fica separado do agent_orchestrator.py para
não acoplar a lógica de negócio a um canal específico (Meta ou Z-API) --
cada servidor de webhook registra sua própria forma de "enviar mensagem"
na inicialização, e este módulo só chama essa função quando necessário.

Como funciona:
1. No startup do servidor (whatsapp_webhook.py ou zapi_webhook.py), chama-se
   register_notifier(funcao_de_envio) uma vez.
2. Quando o agente decide transferir (via tool transferir_para_humano), o
   agent_orchestrator.py chama notify_owner(...) daqui.
3. Esta função monta a mensagem e usa a função registrada para mandar ao
   número do dono, configurado em OWNER_PHONE no .env.

Se nenhum notifier for registrado (ex: rodando via interactive_cli.py), a
notificação apenas é registrada em log local -- não quebra a demo.
"""

import os
from datetime import datetime

OWNER_PHONE = os.environ.get("OWNER_PHONE")

# Função de envio real, injetada pelo servidor de webhook em uso.
# Assinatura esperada: (telefone_destino: str, mensagem: str) -> None
_notifier = None

# Log local de transferências, útil para a demo e para debug.
HANDOFF_LOG = []


def register_notifier(send_function) -> None:
    """Chamado pelo servidor de webhook (Meta ou Z-API) na inicialização,
    para informar qual função usar para de fato mandar a mensagem real."""
    global _notifier
    _notifier = send_function


def notify_owner(cliente_telefone: str, motivo: str, resumo: str) -> dict:
    """Avisa o dono do negócio que uma conversa precisa de atenção humana."""
    mensagem = (
        f"🔔 Atendimento humano solicitado\n"
        f"Cliente: {cliente_telefone}\n"
        f"Motivo: {motivo}\n"
        f"Resumo: {resumo}\n"
        f"Hora: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    )

    entry = {
        "cliente_telefone": cliente_telefone,
        "motivo": motivo,
        "resumo": resumo,
        "timestamp": datetime.now().isoformat(),
        "notificado": False,
    }

    if _notifier and OWNER_PHONE:
        try:
            _notifier(OWNER_PHONE, mensagem)
            entry["notificado"] = True
        except Exception as exc:  # não deixa a falha de notificação travar o atendimento ao cliente
            entry["erro"] = str(exc)
    else:
        # Sem notifier configurado (ex: demo via terminal) -- só registra em log.
        entry["erro"] = "Notifier ou OWNER_PHONE não configurados; notificação apenas registrada."

    HANDOFF_LOG.append(entry)
    return {
        "sucesso": True,
        "notificado_dono": entry["notificado"],
        "mensagem_para_cliente_sugerida": (
            "Vou chamar alguém da nossa equipe para te ajudar com isso. "
            "Só um momento, já já retornamos! 😊"
        ),
    }


def get_handoff_log() -> list:
    return HANDOFF_LOG
