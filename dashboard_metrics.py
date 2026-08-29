"""
dashboard_metrics.py
-----------------------
Calcula métricas de negócio a partir dos mesmos arquivos de dados já usados
pelo mock_api.py (appointments.json, services.json). Não depende do agente
nem do canal de WhatsApp -- é lido diretamente, então funciona mesmo que o
servidor de mensagens esteja parado.

Quando migrar para banco de dados real (Fase 2 do roadmap), só a função
_load() precisa mudar; o resto do cálculo continua igual.
"""

import json
import os
from collections import Counter
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
APPOINTMENTS_FILE = os.path.join(DATA_DIR, "appointments.json")
SERVICES_FILE = os.path.join(DATA_DIR, "services.json")


def _load(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_metrics() -> dict:
    appts_data = _load(APPOINTMENTS_FILE)
    services_data = _load(SERVICES_FILE)

    appointments = appts_data["appointments"]
    services_by_id = {s["id"]: s for s in services_data["servicos"]}

    total = len(appointments)
    confirmados = [a for a in appointments if a["status"] == "confirmado"]
    cancelados = [a for a in appointments if a["status"] == "cancelado"]
    outros = [a for a in appointments if a["status"] not in ("confirmado", "cancelado")]

    # Receita estimada: soma do preço do serviço de cada agendamento confirmado.
    receita_total = 0.0
    for a in confirmados:
        servico = services_by_id.get(a["servico_id"])
        if servico:
            receita_total += servico["preco"]

    # Agendamentos por serviço (para o gráfico de barras).
    contagem_servico = Counter(a["servico_id"] for a in confirmados)
    agendamentos_por_servico = [
        {
            "servico": services_by_id.get(sid, {}).get("nome", sid),
            "quantidade": qtd,
        }
        for sid, qtd in contagem_servico.items()
    ]
    agendamentos_por_servico.sort(key=lambda x: x["quantidade"], reverse=True)

    # Agendamentos por dia (para o gráfico de linha/barras ao longo do tempo).
    contagem_dia = Counter(a["data"] for a in appointments)
    agendamentos_por_dia = [
        {"data": data, "quantidade": qtd}
        for data, qtd in sorted(contagem_dia.items())
    ]

    # Próximos agendamentos confirmados, ordenados por data/hora.
    proximos = sorted(confirmados, key=lambda a: (a["data"], a["hora"]))
    proximos_resumo = [
        {
            "cliente": a["cliente_nome"],
            "servico": services_by_id.get(a["servico_id"], {}).get("nome", a["servico_id"]),
            "data": a["data"],
            "hora": a["hora"],
        }
        for a in proximos
    ]

    return {
        "total_agendamentos": total,
        "confirmados": len(confirmados),
        "cancelados": len(cancelados),
        "outros_status": len(outros),
        "receita_total_estimada": round(receita_total, 2),
        "agendamentos_por_servico": agendamentos_por_servico,
        "agendamentos_por_dia": agendamentos_por_dia,
        "proximos_agendamentos": proximos_resumo,
        "gerado_em": datetime.now().strftime("%d/%m/%Y %H:%M"),
    }
