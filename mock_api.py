"""
mock_api.py
-----------
Simula os endpoints REST que, em produção, corresponderiam a Integration
Flows no OIC (ex.: um flow REST Adapter -> validação -> Fusion/DB Adapter
-> resposta). Aqui ficam em memória/JSON para a demo, mas a assinatura das
funções já reflete o contrato de API que seria exposto (payload de entrada,
validações de negócio, payload de saída), facilitando a migração posterior
para endpoints reais.

Endpoints simulados:
- GET  /availability
- POST /appointments          (create)
- POST /appointments/cancel
- POST /appointments/reschedule
- POST /notifications/send
"""

import json
import os
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
SERVICES_FILE = os.path.join(DATA_DIR, "services.json")
APPOINTMENTS_FILE = os.path.join(DATA_DIR, "appointments.json")

NOTIFICATIONS_SENT = []  # log em memória, simula fila/gateway de SMS-WhatsApp


def _load(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def check_availability(data: str, servico_id: str = None, barbeiro_id: str = None) -> dict:
    """GET /availability?data=YYYY-MM-DD&servico_id=&barbeiro_id=

    Retorna horários livres no dia, considerando os agendamentos já existentes.
    """
    appts = _load(APPOINTMENTS_FILE)
    services = _load(SERVICES_FILE)

    ocupados = {
        a["hora"] for a in appts["appointments"]
        if a["data"] == data and a["status"] != "cancelado"
        and (barbeiro_id is None or a["barbeiro_id"] == barbeiro_id)
    }

    slots_padrao = [f"{h:02d}:00" for h in range(9, 19)] + [f"{h:02d}:30" for h in range(9, 19)]
    slots_padrao.sort()
    livres = [s for s in slots_padrao if s not in ocupados]

    return {
        "data": data,
        "servico_id": servico_id,
        "barbeiro_id": barbeiro_id,
        "horarios_disponiveis": livres,
    }


def create_appointment(cliente_nome: str, cliente_telefone: str, servico_id: str,
                        data: str, hora: str, barbeiro_id: str = "barb_001") -> dict:
    """POST /appointments

    Regras de negócio: não permite overbooking no mesmo horário/barbeiro.
    """
    appts = _load(APPOINTMENTS_FILE)

    conflito = any(
        a["data"] == data and a["hora"] == hora and a["barbeiro_id"] == barbeiro_id
        and a["status"] != "cancelado"
        for a in appts["appointments"]
    )
    if conflito:
        return {"sucesso": False, "erro": "Horário indisponível para este barbeiro."}

    novo_id = f"apt_{appts['next_id']}"
    appts["next_id"] += 1

    novo = {
        "id": novo_id,
        "cliente_nome": cliente_nome,
        "cliente_telefone": cliente_telefone,
        "servico_id": servico_id,
        "barbeiro_id": barbeiro_id,
        "data": data,
        "hora": hora,
        "status": "confirmado",
        "criado_em": datetime.now().isoformat(),
    }
    appts["appointments"].append(novo)
    _save(APPOINTMENTS_FILE, appts)
    return {"sucesso": True, "agendamento": novo}


def cancel_appointment(appointment_id: str) -> dict:
    """POST /appointments/cancel"""
    appts = _load(APPOINTMENTS_FILE)
    for a in appts["appointments"]:
        if a["id"] == appointment_id:
            a["status"] = "cancelado"
            _save(APPOINTMENTS_FILE, appts)
            return {"sucesso": True, "agendamento": a}
    return {"sucesso": False, "erro": "Agendamento não encontrado."}


def reschedule_appointment(appointment_id: str, nova_data: str, nova_hora: str) -> dict:
    """POST /appointments/reschedule"""
    appts = _load(APPOINTMENTS_FILE)

    alvo = next((a for a in appts["appointments"] if a["id"] == appointment_id), None)
    if not alvo:
        return {"sucesso": False, "erro": "Agendamento não encontrado."}

    conflito = any(
        a["data"] == nova_data and a["hora"] == nova_hora
        and a["barbeiro_id"] == alvo["barbeiro_id"] and a["status"] != "cancelado"
        and a["id"] != appointment_id
        for a in appts["appointments"]
    )
    if conflito:
        return {"sucesso": False, "erro": "Novo horário indisponível."}

    alvo["data"] = nova_data
    alvo["hora"] = nova_hora
    alvo["status"] = "confirmado"
    _save(APPOINTMENTS_FILE, appts)
    return {"sucesso": True, "agendamento": alvo}


def send_notification(cliente_telefone: str, mensagem: str, tipo: str = "confirmacao") -> dict:
    """POST /notifications/send

    Em produção: integração real com WhatsApp Business API / SMS gateway,
    orquestrada por um Integration Flow no OIC (REST Trigger -> template de
    mensagem -> Adapter do provedor de notificação).
    """
    registro = {
        "cliente_telefone": cliente_telefone,
        "tipo": tipo,
        "mensagem": mensagem,
        "enviado_em": datetime.now().isoformat(),
    }
    NOTIFICATIONS_SENT.append(registro)
    return {"sucesso": True, "notificacao": registro}


def get_services() -> dict:
    return _load(SERVICES_FILE)
