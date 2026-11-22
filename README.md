# Barbershop Agent — Atendente de IA para barbearias (POC)

Prova de conceito de um assistente de IA que atende clientes de uma barbearia em linguagem natural: tira dúvidas sobre serviços e preços, consulta horários, agenda, cancela e remarca, tudo com **consentimento LGPD** antes de guardar qualquer dado pessoal e **transferência para um humano** quando necessário.

> **Status:** prova de conceito. Ela valida a ideia ponta a ponta, mas usa dados simulados (arquivos JSON) e não está pronta para produção. Veja [Limitações](#limitações) e [Próximos passos](#próximos-passos-rumo-a-um-mvp).

## O que o agente faz

- Responde sobre serviços, preços, duração e equipe usando uma base de conhecimento (RAG simples).
- Consulta horários disponíveis e entende datas em linguagem natural ("sábado que vem", "dia 14"), respondendo no padrão brasileiro `DD/MM/AAAA`.
- Cria, cancela e remarca agendamentos.
- **LGPD:** apresenta o texto de consentimento e só cria o agendamento depois que o cliente aceita. A regra vale no prompt **e** no código (defesa em profundidade). O cliente também pode consultar ou apagar os próprios dados.
- **Transferência para humano:** reclamações, pedidos de exceção, perguntas fora do escopo ou pedido explícito por um atendente notificam o dono do negócio.

## Como funciona

```
Cliente (chat/WhatsApp)
        │
        ▼
 Interface de entrada ──► BarbershopAgent (agent_orchestrator.py)
 (chat web ou webhook)         │
                               ├─ Groq API (LLM com tool-calling)
                               └─ Tools: serviços (RAG) · disponibilidade · agendamento
                                         · consentimento LGPD · dados do cliente · humano
```

O modelo decide qual *tool* chamar, o resultado volta para ele e ele formula a resposta. A "porta de entrada" é intercambiável: o mesmo agente atende o chat web de testes e o webhook do WhatsApp.

## Stack

- Python, FastAPI e Uvicorn
- Groq API (modelo `openai/gpt-oss-120b`, configurável em `agent_orchestrator.py`) com tool-calling
- Whapi Cloud para o WhatsApp (opcional) e ngrok para expor o webhook em desenvolvimento

## Como rodar (modo mais simples: chat web local)

Não precisa de WhatsApp, Whapi nem ngrok. Só de uma chave da Groq (gratuita).

```powershell
git clone https://github.com/DINb/barbershop-agent.git
cd barbershop-agent

python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

copy .env.example .env
# edite o .env e preencha GROQ_API_KEY

uvicorn test_chat_server:app --port 8001
```

Abra `http://127.0.0.1:8001` e converse com o agente. Em `http://127.0.0.1:8001/?demo=1` o chat digita sozinho um roteiro de exemplo, útil para gravar uma demonstração.

## Como rodar com WhatsApp (Whapi Cloud)

1. Crie um canal na [Whapi Cloud](https://whapi.cloud) e conecte um número por QR code.
2. Preencha `WHAPI_TOKEN` no `.env` (e, opcionalmente, `OWNER_PHONE`, o número que recebe as transferências para humano).
3. Suba o webhook e o túnel:
   ```powershell
   uvicorn whapi_webhook:app --port 8000
   ngrok http 8000
   ```
4. Cadastre `https://SEU-TUNEL.ngrok-free.dev/webhook` como webhook de mensagens no painel da Whapi.

O webhook responde `200` imediatamente e processa a mensagem em segundo plano, com *retry* nas chamadas à Whapi, para que lentidão de terceiros não derrube a requisição. Mensagens de grupos, canais e listas de transmissão são ignoradas.

## Variáveis de ambiente

| Variável | Uso |
|---|---|
| `GROQ_API_KEY` | Chave da Groq (obrigatória) |
| `WHAPI_TOKEN` | Token do canal na Whapi Cloud (só no modo WhatsApp) |
| `OWNER_PHONE` | Número do dono, para avisos de transferência para humano (opcional) |

Nunca faça commit do arquivo `.env`.

## Estrutura do projeto

| Arquivo | Função |
|---|---|
| `agent_orchestrator.py` | Agente: prompt, tools e loop de tool-calling |
| `test_chat_server.py` | Chat web local para testar e demonstrar o agente |
| `whapi_webhook.py` | Webhook do WhatsApp via Whapi Cloud |
| `whatsapp_webhook.py`, `zapi_webhook.py` | Versões anteriores da integração (Meta Cloud API e Z-API) |
| `rag_knowledge.py` | Base de conhecimento de serviços, preços e horários |
| `mock_api.py` | Agenda simulada (arquivos JSON em `data/`) |
| `lgpd_compliance.py` | Consentimento e direitos do titular (acesso e exclusão) |
| `human_handoff.py` | Transferência da conversa para um humano |
| `interactive_cli.py` | Chat pelo terminal |
| `dashboard_server.py`, `dashboard_metrics.py` | Painel de métricas e gráficos para o dono do negócio |
| `data/` | Serviços e dados simulados |

## Limitações

- A agenda é simulada em arquivos JSON, sem banco de dados e sem controle de concorrência.
- O histórico das conversas fica em memória e se perde ao reiniciar o servidor.
- Não há autenticação, limite de mensagens por cliente nem multi-barbearia.
- Respostas de um LLM variam; não há suíte de testes automatizados do comportamento do agente.
- O plano gratuito da Whapi tem cota curta de mensagens e dias de uso.

## Próximos passos rumo a um MVP

- Banco de dados no lugar do `mock_api.py` e integração com uma agenda real.
- Linha de WhatsApp dedicada (Whapi paga ou Meta Cloud API oficial).
- Painel para o dono da barbearia, com agenda, conversas e transferências.
- Configuração por barbearia (serviços, horários, tom de voz), limite de mensagens e logs de auditoria da LGPD.
- Testes automatizados dos fluxos principais (consentimento, agendamento, transferência).

## Aviso

Projeto de portfólio, em fase de prova de conceito. Todos os dados de exemplo são fictícios.
