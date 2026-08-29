"""
lgpd_compliance.py
-------------------
Camada de conformidade com a LGPD (Lei 13.709/2018) para o POC da barbearia.

Implementa, de forma simplificada mas funcional, os principais pontos que uma
banca avaliadora ou um cliente costuma perguntar:

1. Consentimento explícito e registrado (art. 7º, 8º)       -> ConsentManager
2. Finalidade e minimização de dados (art. 6º)               -> apenas nome/telefone
3. Direito de acesso e portabilidade (art. 18, incisos II/V) -> get_my_data()
4. Direito de eliminação / esquecimento (art. 18, inciso VI) -> forget_me()
5. Retenção limitada de dados (art. 15, 16)                  -> purge_expired()
6. Registro de operações (log de auditoria)                  -> AUDIT_LOG

Em produção, isso seria: banco de dados com criptografia em repouso,
DPO formalizado, base legal documentada por processo, e integração com o
módulo de Segurança de Dados do OIC / Oracle Fusion (ex.: mascaramento de
dados sensíveis em logs de integração).
"""

import json
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
CONSENT_FILE = os.path.join(DATA_DIR, "consent_log.json")
APPOINTMENTS_FILE = os.path.join(DATA_DIR, "appointments.json")

# Prazo de retenção de dados pessoais após o último agendamento (em dias).
# Ajustável conforme política de privacidade da barbearia.
RETENTION_DAYS = 365

AUDIT_LOG = []  # log em memória para exibir na demo (auditoria simplificada)


def _log(action: str, detail: str):
    entry = {
        "timestamp": datetime.now().isoformat(),
        "action": action,
        "detail": detail,
    }
    AUDIT_LOG.append(entry)
    return entry


def _load(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(path: str, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


class ConsentManager:
    """Gerencia o consentimento explícito do titular dos dados (o cliente)."""

    @staticmethod
    def request_consent_text() -> str:
        """Texto que o agente deve apresentar ANTES de coletar qualquer dado."""
        return (
            "Para agendar seu horário, preciso guardar seu nome e telefone, "
            "usados apenas para confirmar, lembrar ou remarcar seu atendimento. "
            f"Esses dados ficam guardados por até {RETENTION_DAYS} dias após seu "
            "último agendamento e você pode pedir a exclusão a qualquer momento "
            "dizendo 'apagar meus dados'. Posso prosseguir com o agendamento? (sim/não)"
        )

    @staticmethod
    def register_consent(cliente_nome: str, cliente_telefone: str, aceito: bool) -> dict:
        data = _load(CONSENT_FILE)
        record = {
            "consent_id": str(uuid.uuid4()),
            "cliente_nome": cliente_nome,
            "cliente_telefone": cliente_telefone,
            "aceito": aceito,
            "finalidade": "Agendamento, confirmação, lembrete e remarcação de serviços de barbearia",
            "base_legal": "Consentimento do titular (art. 7º, I, LGPD)",
            "timestamp": datetime.now().isoformat(),
        }
        data["consents"].append(record)
        _save(CONSENT_FILE, data)
        _log("CONSENT_REGISTERED", f"{cliente_telefone} -> aceito={aceito}")
        return record

    @staticmethod
    def has_valid_consent(cliente_telefone: str) -> bool:
        data = _load(CONSENT_FILE)
        registros = [c for c in data["consents"] if c["cliente_telefone"] == cliente_telefone]
        if not registros:
            return False
        ultimo = sorted(registros, key=lambda c: c["timestamp"])[-1]
        return ultimo["aceito"] is True


class DataSubjectRights:
    """Implementa os direitos do titular previstos no art. 18 da LGPD."""

    @staticmethod
    def get_my_data(cliente_telefone: str) -> dict:
        """Direito de acesso e portabilidade (art. 18, II e V)."""
        appts = _load(APPOINTMENTS_FILE)
        consents = _load(CONSENT_FILE)

        meus_agendamentos = [
            a for a in appts["appointments"] if a["cliente_telefone"] == cliente_telefone
        ]
        meus_consentimentos = [
            c for c in consents["consents"] if c["cliente_telefone"] == cliente_telefone
        ]
        _log("DATA_ACCESS_REQUEST", cliente_telefone)
        return {
            "agendamentos": meus_agendamentos,
            "consentimentos": meus_consentimentos,
        }

    @staticmethod
    def forget_me(cliente_telefone: str) -> dict:
        """Direito de eliminação / esquecimento (art. 18, VI).

        Remove dados identificáveis mas mantém um registro estatístico
        anonimizado (ex.: contagem de serviços prestados), prática comum
        para não perder valor analítico do dado enquanto se respeita o
        direito do titular.
        """
        appts = _load(APPOINTMENTS_FILE)
        removidos = 0
        for a in appts["appointments"]:
            if a["cliente_telefone"] == cliente_telefone:
                a["cliente_nome"] = "ANONIMIZADO"
                a["cliente_telefone"] = "ANONIMIZADO"
                a["status"] = a["status"] + " (dados anonimizados a pedido do titular)"
                removidos += 1
        _save(APPOINTMENTS_FILE, appts)

        consents = _load(CONSENT_FILE)
        for c in consents["consents"]:
            if c["cliente_telefone"] == cliente_telefone:
                c["cliente_nome"] = "ANONIMIZADO"
                c["cliente_telefone"] = "ANONIMIZADO"
        _save(CONSENT_FILE, consents)

        _log("RIGHT_TO_ERASURE_EXECUTED", f"{removidos} registro(s) anonimizados")
        return {"registros_anonimizados": removidos}


class RetentionPolicy:
    """Política de retenção e expurgo automático de dados (art. 15, 16 LGPD)."""

    @staticmethod
    def purge_expired(reference_date: Optional[datetime] = None) -> dict:
        reference_date = reference_date or datetime.now()
        cutoff = reference_date - timedelta(days=RETENTION_DAYS)

        appts = _load(APPOINTMENTS_FILE)
        expurgados = 0
        for a in appts["appointments"]:
            data_agendamento = datetime.fromisoformat(a["data"])
            if data_agendamento < cutoff and a["cliente_nome"] != "ANONIMIZADO":
                a["cliente_nome"] = "ANONIMIZADO (retenção expirada)"
                a["cliente_telefone"] = "ANONIMIZADO"
                expurgados += 1
        _save(APPOINTMENTS_FILE, appts)

        _log("RETENTION_PURGE_RUN", f"{expurgados} registro(s) expurgados")
        return {"expurgados": expurgados, "cutoff": cutoff.isoformat()}


def get_audit_log() -> list:
    return AUDIT_LOG
