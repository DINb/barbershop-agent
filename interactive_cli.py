"""
interactive_cli.py
--------------------
Demo ao vivo em terminal, no mesmo espírito do interactive_groq.py do
oic-fusion-incident-agent. Ideal para gravar GIF/vídeo de demonstração
ou apresentar em call com o cliente.

Uso:
    export GROQ_API_KEY="sua_chave_aqui"
    python interactive_cli.py
"""

import os
import sys

from agent_orchestrator import BarbershopAgent
import lgpd_compliance as lgpd

BANNER = """
============================================================
 Barbearia Corte Certo - Assistente Virtual (POC)
 Agendamento | Confirmacao | Cancelamento | Remarcacao
 Conformidade LGPD embutida no fluxo de atendimento
============================================================
Digite sua mensagem como se fosse um cliente no WhatsApp.
Comandos especiais:
  /auditoria   -> mostra o log de auditoria LGPD desta sessao
  /sair        -> encerra a demo
------------------------------------------------------------
"""


def main():
    if not os.environ.get("GROQ_API_KEY"):
        print("ERRO: defina a variável de ambiente GROQ_API_KEY antes de rodar.")
        print('Exemplo: export GROQ_API_KEY="gsk_..."')
        sys.exit(1)

    print(BANNER)
    agent = BarbershopAgent()

    while True:
        try:
            user_input = input("Cliente> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nEncerrando demo.")
            break

        if not user_input:
            continue
        if user_input.lower() in ("/sair", "sair", "exit", "quit"):
            print("Encerrando demo. Obrigado!")
            break
        if user_input.lower() == "/auditoria":
            print("\n--- Log de auditoria LGPD ---")
            for entry in lgpd.get_audit_log():
                print(f"[{entry['timestamp']}] {entry['action']}: {entry['detail']}")
            print("-----------------------------\n")
            continue

        resposta = agent.chat(user_input)
        print(f"Agente> {resposta}\n")


if __name__ == "__main__":
    main()
