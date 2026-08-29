# Barbearia Corte Certo — Agente de Atendimento (POC)

POC de um assistente virtual para barbearias, cobrindo **agendamento,
confirmação, cancelamento e remarcação**, com **conformidade LGPD** embutida
no fluxo de conversa — não como um adendo jurídico, mas como parte do
produto.

Arquitetura no mesmo padrão do [`oic-fusion-incident-agent`](https://github.com/DINb):
agente orquestrado via **Groq API (Llama 3.3)** com tool-calling, RAG leve
(TF-IDF) para base de conhecimento, e endpoints REST mockados desenhados no
mesmo estilo de um Integration Flow no OIC (entrada validada → regra de
negócio → resposta padronizada).

## Por que isso importa para o cliente (dono da barbearia)

- **Menos no-show**: confirmações e lembretes automáticos.
- **Zero conflito de agenda**: regra de negócio impede overbooking.
- **Proteção jurídica**: consentimento registrado e auditável, retenção de
  dados com prazo definido, atendimento aos direitos do titular (acesso e
  exclusão) — reduz risco de multa por descumprimento da LGPD (art. 52).
- **Escalável**: a mesma arquitetura de agente + tools pode, depois, plugar
  em WhatsApp Business API real, banco de dados persistente, e até em
  integrações com sistemas de gestão da barbearia via OIC.

## Estrutura do projeto

```
barbershop-agent/
├── agent_orchestrator.py   # Agente (Groq + tool-calling) e regras de LGPD
├── mock_api.py              # Endpoints REST simulados (agendamento, notificação)
├── lgpd_compliance.py        # Consentimento, direitos do titular, retenção
├── rag_knowledge.py          # RAG (TF-IDF) sobre serviços/preços/horários
├── interactive_cli.py        # Demo em terminal
├── data/
│   ├── services.json         # Catálogo de serviços e horário de funcionamento
│   ├── appointments.json     # Agendamentos (estado em memória/arquivo)
│   └── consent_log.json      # Registro de consentimentos LGPD
└── requirements.txt
```

## Como rodar a demo

```bash
pip install -r requirements.txt
export GROQ_API_KEY="sua_chave_aqui"
python interactive_cli.py
```

### Roteiro sugerido de demonstração (para o cliente)

1. **Pergunta de serviço** — "Quanto custa corte e barba?"
   → mostra o RAG respondendo sem precisar de agendamento.
2. **Início de agendamento** — "Quero marcar um corte pra sábado às 10h"
   → o agente **pede consentimento LGPD antes de gravar qualquer dado
   pessoal**. Esse é o momento de destacar o diferencial pro cliente.
3. **Confirmação** — cliente aceita, agente cria o agendamento e "envia"
   confirmação (`enviar_notificacao`).
4. **Remarcação** — "Preciso mudar para domingo" → mostra que domingo está
   fechado (regra de negócio no `services.json`), e sugere alternativa.
5. **Direito de acesso** — "Quero ver meus dados" → `consultar_meus_dados`.
6. **Direito ao esquecimento** — "Apaga meus dados" → `apagar_meus_dados`,
   anonimiza sem quebrar o histórico estatístico.
7. **Bastidor de auditoria** — digite `/auditoria` no CLI para mostrar o log
   de conformidade, ótimo argumento de venda ("tudo fica registrado").

## Integração real com WhatsApp (número de teste gratuito da Meta)

Veja o passo a passo completo na resposta do Claude ou siga resumidamente:

1. Crie um app tipo "Business" em developers.facebook.com/apps, adicione o produto WhatsApp.
2. Gere um token de acesso e anote o "Phone Number ID" do número de teste.
3. Copie `.env.example` para `.env` e preencha `GROQ_API_KEY`, `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`, `VERIFY_TOKEN`.
4. Rode `uvicorn whatsapp_webhook:app --reload --port 8000`.
5. Exponha a porta local com `ngrok http 8000` (ou similar) para obter uma URL pública https.
6. No painel da Meta, em WhatsApp > Configuration, cole a URL pública + `/webhook` como Callback URL, e o mesmo valor de `VERIFY_TOKEN` no campo Verify Token.
7. Adicione seu próprio número como destinatário de teste (a Meta envia um código de confirmação por WhatsApp).
8. Mande uma mensagem para o número de teste da barbearia e veja o agente responder.

## Próximos passos (para a proposta comercial pós-demo)

- Integração real com WhatsApp Business API / Twilio para notificações.
- Persistência em banco de dados (Postgres/Oracle) em vez de JSON.
- Painel administrativo para o dono da barbearia (agenda, relatórios).
- Hospedagem + manutenção mensal (SLA de suporte, atualizações).
- Assinatura de contrato de operador de dados (LGPD) formalizando o papel
  do prestador de serviço frente ao controlador (a barbearia).

## Nota sobre esta POC

Os dados de agendamento, consentimento e disponibilidade são simulados em
arquivos JSON para fins de demonstração. Em produção, cada ponto marcado
como "mock" neste código seria substituído por uma integração real (banco
de dados, gateway de notificação, etc.), mantendo o mesmo contrato de tools
usado pelo agente.
