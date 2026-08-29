"""
dashboard_server.py
----------------------
Painel administrativo simples para o dono do negócio acompanhar
agendamentos, receita estimada e próximos horários. Roda como um serviço
web independente do canal de WhatsApp (porta separada) -- ou seja,
funciona mesmo que o whatsapp_webhook.py ou zapi_webhook.py não estejam
no ar no momento.

Uso:
    uvicorn dashboard_server:app --reload --port 8001

Depois, acesse http://localhost:8001 no navegador.

Esta é a primeira versão (Fase 3 do roadmap). Uma versão futura pode
adicionar autenticação (login do dono) antes de expor isso publicamente
na internet -- por enquanto, é pensado para uso local ou atrás de um
túnel privado, não para publicação sem senha.
"""

import json

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

import dashboard_metrics

app = FastAPI(title="Painel - Barbearia Corte Certo")


def render_dashboard(metrics: dict) -> str:
    labels_servico = json.dumps([item["servico"] for item in metrics["agendamentos_por_servico"]])
    valores_servico = json.dumps([item["quantidade"] for item in metrics["agendamentos_por_servico"]])

    labels_dia = json.dumps([item["data"] for item in metrics["agendamentos_por_dia"]])
    valores_dia = json.dumps([item["quantidade"] for item in metrics["agendamentos_por_dia"]])

    linhas_proximos = "".join(
        f"<tr><td>{p['data']}</td><td>{p['hora']}</td><td>{p['cliente']}</td><td>{p['servico']}</td></tr>"
        for p in metrics["proximos_agendamentos"]
    ) or "<tr><td colspan='4' class='empty'>Nenhum agendamento confirmado no momento.</td></tr>"

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>Painel - Barbearia Corte Certo</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f1115;
    --card: #171a21;
    --border: #262b36;
    --text: #e6e8ec;
    --muted: #8b93a5;
    --accent: #4f8cff;
    --accent-2: #34d399;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    padding: 32px;
  }}
  h1 {{ font-size: 22px; margin: 0 0 4px 0; }}
  .subtitle {{ color: var(--muted); font-size: 13px; margin-bottom: 28px; }}
  .cards {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 16px;
    margin-bottom: 28px;
  }}
  .card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 18px;
  }}
  .card .label {{ color: var(--muted); font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; }}
  .card .value {{ font-size: 28px; font-weight: 600; margin-top: 6px; }}
  .value.green {{ color: var(--accent-2); }}
  .value.red {{ color: #f87171; }}
  .charts {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 16px;
    margin-bottom: 28px;
  }}
  .chart-card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 18px;
  }}
  .chart-card h2 {{ font-size: 14px; margin: 0 0 14px 0; color: var(--text); }}
  table {{
    width: 100%;
    border-collapse: collapse;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 12px;
    overflow: hidden;
  }}
  th, td {{
    text-align: left;
    padding: 10px 14px;
    font-size: 13px;
    border-bottom: 1px solid var(--border);
  }}
  th {{ color: var(--muted); font-weight: 500; text-transform: uppercase; font-size: 11px; }}
  .empty {{ color: var(--muted); text-align: center; }}
</style>
</head>
<body>

  <h1>📊 Painel — Barbearia Corte Certo</h1>
  <div class="subtitle">Atualizado em {metrics['gerado_em']}</div>

  <div class="cards">
    <div class="card">
      <div class="label">Total de agendamentos</div>
      <div class="value">{metrics['total_agendamentos']}</div>
    </div>
    <div class="card">
      <div class="label">Confirmados</div>
      <div class="value green">{metrics['confirmados']}</div>
    </div>
    <div class="card">
      <div class="label">Cancelados</div>
      <div class="value red">{metrics['cancelados']}</div>
    </div>
    <div class="card">
      <div class="label">Receita estimada</div>
      <div class="value">R$ {metrics['receita_total_estimada']:.2f}</div>
    </div>
  </div>

  <div class="charts">
    <div class="chart-card">
      <h2>Agendamentos por serviço</h2>
      <canvas id="chartServicos"></canvas>
    </div>
    <div class="chart-card">
      <h2>Agendamentos por dia</h2>
      <canvas id="chartDias"></canvas>
    </div>
  </div>

  <table>
    <thead>
      <tr><th>Data</th><th>Hora</th><th>Cliente</th><th>Serviço</th></tr>
    </thead>
    <tbody>
      {linhas_proximos}
    </tbody>
  </table>

<script>
  const corTexto = '#8b93a5';
  const corGrade = '#262b36';

  new Chart(document.getElementById('chartServicos'), {{
    type: 'bar',
    data: {{
      labels: {labels_servico},
      datasets: [{{
        label: 'Agendamentos',
        data: {valores_servico},
        backgroundColor: '#4f8cff',
        borderRadius: 6,
      }}]
    }},
    options: {{
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ ticks: {{ color: corTexto }}, grid: {{ color: corGrade }} }},
        y: {{ ticks: {{ color: corTexto, precision: 0 }}, grid: {{ color: corGrade }} }}
      }}
    }}
  }});

  new Chart(document.getElementById('chartDias'), {{
    type: 'line',
    data: {{
      labels: {labels_dia},
      datasets: [{{
        label: 'Agendamentos',
        data: {valores_dia},
        borderColor: '#34d399',
        backgroundColor: 'rgba(52, 211, 153, 0.15)',
        fill: true,
        tension: 0.3,
      }}]
    }},
    options: {{
      plugins: {{ legend: {{ display: false }} }},
      scales: {{
        x: {{ ticks: {{ color: corTexto }}, grid: {{ color: corGrade }} }},
        y: {{ ticks: {{ color: corTexto, precision: 0 }}, grid: {{ color: corGrade }} }}
      }}
    }}
  }});
</script>

</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def dashboard():
    metrics = dashboard_metrics.compute_metrics()
    return render_dashboard(metrics)


@app.get("/api/metrics")
def metrics_json():
    """Endpoint JSON puro, útil se quiser plugar em outra ferramenta depois."""
    return dashboard_metrics.compute_metrics()
