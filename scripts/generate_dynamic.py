#!/usr/bin/env python3
import json
from pathlib import Path
from datetime import datetime

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def format_money(num):
    if num is None: return '-'
    if num >= 1e9: return f'R$ {num/1e9:.2f} Bi'
    if num >= 1e6: return f'R$ {num/1e6:.2f} Mi'
    return f'R$ {num:.2f}'

def generate_barsi_html(data, update_date):
    stocks = data['stocks']
    total = len(stocks)
    if stocks:
        highest_dy = max(stocks, key=lambda x: x['dividend_yield'])
        highest_dy_val = highest_dy['dividend_yield'] * 100
        highest_dy_ticker = highest_dy['ticker']
    else:
        highest_dy_val = 0
        highest_dy_ticker = '-'

    # Preparar dados para gráficos
    top10 = stocks[:10]
    labels = [s['ticker'] for s in top10]
    scores = [s['score'] for s in top10]
    dys = [s['dividend_yield'] * 100 for s in top10]

    # Distribuição por setor
    setores = {}
    for s in stocks:
        setor = s['setor'].split(' ')[0]
        setores[setor] = setores.get(setor, 0) + 1
    setor_labels = list(setores.keys())
    setor_values = list(setores.values())

    rows = []
    for i, s in enumerate(stocks):
        rank = i + 1
        medal = ['🥇','🥈','🥉'][rank-1] if rank <= 3 else rank
        p_l_val = f"{s['p_l']:.2f}" if s.get('p_l') is not None else '-'
        row = f'''                <tr>
                    <td>{medal}</td>
                    <td><span class="ticker">{s['ticker']}</span></td>
                    <td>
                        <div class="nome">{s['nome']}</div>
                        <div style="font-size: 0.8rem; color: #64748b;">{s.get('segmento', s['setor'])}</div>
                    </td>
                    <td><span class="setor">{s['setor'].split(' ')[0]}</span></td>
                    <td class="font-mono">{format_money(s['preco'])}</td>
                    <td class="dy">{s['dividend_yield']*100:.2f}%</td>
                    <td class="font-mono">{format_money(s.get('dividend_rate'))}</td>
                    <td class="{'pvpa-good' if s['p_vpa'] <= 2.0 else ''}">{s['p_vpa']:.2f}</td>
                    <td class="font-mono">{p_l_val}</td>
                    <td><span class="score-badge">{s['score']:.1f}</span></td>
                </tr>'''
        rows.append(row)

    html = f'''<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Carteira Barsi - Dividendos | IA em Loop</title>
    <meta name="description" content="Carteira Barsi de dividendos: empresas perenes com DY ≥3%, P/VPA ≤2.0, market cap ≥R$1bi. Metodologia de Luiz Barsi Filho aplicada com capital real.">
    <link rel="canonical" href="https://iaemloop.com.br/barsi.html">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Inter', sans-serif; background: #0a0f1a; color: #e2e8f0; padding: 20px; line-height: 1.6; }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .header h1 {{ color: #10b981; font-size: 1.8rem; margin-bottom: 5px; }}
        .header p {{ color: #64748b; font-size: 0.9rem; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px,1fr)); gap: 15px; margin-bottom: 30px; }}
        .stat-card {{ background: #1e293b; padding: 20px; border-radius: 12px; border-left: 4px solid #f59e0b; }}
        .stat-card h3 {{ font-size: 0.85rem; color: #94a3b8; margin-bottom: 8px; }}
        .stat-card .value {{ font-size: 2rem; font-weight: 700; color: #fff; }}
        .stat-card .sub {{ font-size: 0.8rem; color: #64748b; }}
        table {{ width: 100%; background: #1e293b; border-radius: 12px; overflow: hidden; margin-bottom: 30px; }}
        th, td {{ padding: 15px; text-align: left; }}
        th {{ background: #0f172a; color: #94a3b8; font-weight: 600; font-size: 0.85rem; text-transform: uppercase; }}
        tr {{ border-bottom: 1px solid #334155; }}
        tr:hover {{ background: #334155; }}
        .ticker {{ font-weight: 700; color: #fff; font-size: 1.1rem; }}
        .nome {{ color: #cbd5e1; }}
        .setor {{ background: #059669; color: #fff; padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; }}
        .dy {{ color: #10b981; font-weight: 600; }}
        .pvpa-good {{ color: #3b82f6; font-weight: 600; }}
        .score-badge {{ background: linear-gradient(135deg, #f59e0b, #d97706); color: #fff; padding: 4px 12px; border-radius: 20px; font-weight: 600; font-size: 0.85rem; }}
        .methodology {{ background: #1e293b; padding: 25px; border-radius: 12px; margin-bottom: 30px; }}
        .methodology h2 {{ color: #10b981; margin-bottom: 15px; font-size: 1.3rem; }}
        .methodology ul {{ list-style: none; }}
        .methodology li {{ padding: 8px 0; color: #cbd5e1; }}
        .methodology li::before {{ content: "✓ "; color: #10b981; font-weight: bold; }}
        .footer {{ text-align: center; color: #64748b; font-size: 0.85rem; margin-top: 30px; }}
        select {{ background: #334155; color: #fff; border: 1px solid #475569; padding: 8px 12px; border-radius: 6px; margin-left: 10px; }}
        .charts {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(400px, 1fr)); gap: 20px; margin: 30px 0; }}
        .chart-card {{ background: #1e293b; padding: 20px; border-radius: 12px; }}
        .chart-card h3 {{ color: #60a5fa; margin-bottom: 15px; font-size: 1.1rem; }}
        .chart-container {{ position: relative; height: 300px; }}
    </style>
</head>
<body>
    <div class="container">
        <div style="text-align: center; margin-bottom: 20px;">
            <a href="index.html" style="display: inline-block; background: rgba(96,165,250,0.2); color: #60a5fa; padding: 8px 16px; border-radius: 20px; text-decoration: none; font-size: 0.9rem;">← Voltar ao Menu</a>
        </div>
        <div class="header">
            <ins class="adsbygoogle" style="display:block; margin: 20px auto; text-align: center;" data-ad-client="ca-pub-1004632420072229" data-ad-slot="auto" data-ad-format="auto"></ins>
            <script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>
            <h1>💎 Carteira Barsi (Dividendos)</h1>
            <p>Metodologia "O Rei dos Dividendos" • Atualizado: {update_date}</p>
        </div>

        <div class="stats">
            <div class="stat-card">
                <h3>Total Analisado</h3>
                <div class="value">{total}</div>
                <div class="sub">ativos</div>
            </div>
            <div class="stat-card">
                <h3>Oportunidades</h3>
                <div class="value" style="color: #10b981;">{total}</div>
                <div class="sub">após filtros</div>
            </div>
            <div class="stat-card">
                <h3>Maior DY</h3>
                <div class="value" style="color: #ef4444;">{highest_dy_val:.2f}%</div>
                <div class="sub">{highest_dy_ticker}</div>
            </div>
        </div>

        <!-- Gráficos -->
        <div class="charts">
            <div class="chart-card">
                <h3>📊 Top 10: Score vs Dividend Yield</h3>
                <div class="chart-container">
                    <canvas id="scoreDyChart"></canvas>
                </div>
            </div>
            <div class="chart-card">
                <h3>🍰 Distribuição por Setor</h3>
                <div class="chart-container">
                    <canvas id="sectorChart"></canvas>
                </div>
            </div>
        </div>

        <div style="margin-bottom: 20px; text-align: center;">
            <label style="color: #94a3b8;">Ordenar por: </label>
            <select id="sort-select">
                <option value="score">Score (maior)</option>
                <option value="dy">Dividend Yield</option>
                <option value="pvpa">P/VPA (menor)</option>
                <option value="market_cap">Market Cap</option>
                <option value="ticker">Ticker A-Z</option>
            </select>
        </div>

        <table>
            <thead>
                <tr>
                    <th>Rank</th>
                    <th>Ticker</th>
                    <th>Empresa</th>
                    <th>Setor</th>
                    <th>Preço</th>
                    <th>DY</th>
                    <th>Div/Anual</th>
                    <th>P/VPA</th>
                    <th>P/L</th>
                    <th>Score</th>
                </tr>
            </thead>
            <tbody>
{''.join(rows)}
            </tbody>
        </table>

        <!-- Ad in-feed 1 -->
        <ins class="adsbygoogle" style="display:block; margin:20px auto;" data-ad-client="ca-pub-1004632420072229" data-ad-slot="auto" data-ad-format="auto"></ins>
        <script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>

        <!-- Ad in-feed 2 -->
        <ins class="adsbygoogle" style="display:block; margin:20px auto;" data-ad-client="ca-pub-1004632420072229" data-ad-slot="auto" data-ad-format="auto"></ins>
        <script>(adsbygoogle = window.adsbygoogle || []).push({{}});</script>

        <div class="methodology">
            <h2>📚 Critérios Barsi</h2>
            <ul>
                <li>Dividend Yield ≥ 3% ao ano</li>
                <li>P/VPA ≤ 2.0 (valor justo)</li>
                <li>Market cap ≥ R$ 1 bilhão</li>
                <li>Mínimo 5 anos listed</li>
                <li>Histórico ≥ 3 anos de dividendos</li>
            </ul>
        </div>

        <div class="footer">
            <p>Dados: Yahoo Finance • Não é recomendação de investimento</p>
        </div>
    </div>
    <script>
        // Dados para gráficos
        const chartData = {{
            labels: {labels!r},
            scores: {scores!r},
            dys: {dys!r},
            setorLabels: {setor_labels!r},
            setorValues: {setor_values!r}
        }};

        // Gráfico: Score vs DY (barras agrupadas)
        const ctx1 = document.getElementById('scoreDyChart').getContext('2d');
        new Chart(ctx1, {{
            type: 'bar',
            data: {{
                labels: chartData.labels,
                datasets: [
                    {{
                        label: 'Score',
                        data: chartData.scores,
                        backgroundColor: 'rgba(96, 165, 250, 0.7)',
                        borderColor: 'rgba(96, 165, 250, 1)',
                        borderWidth: 1
                    }},
                    {{
                        label: 'DY (%)',
                        data: chartData.dys,
                        backgroundColor: 'rgba(16, 185, 129, 0.7)',
                        borderColor: 'rgba(16, 185, 129, 1)',
                        borderWidth: 1
                    }}
                ]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                scales: {{ y: {{ beginAtZero: true }} }},
                plugins: {{
                    legend: {{ position: 'top' }}
                }}
            }}
        }});

        // Gráfico de Pizza: Distribuição por setor
        const ctx2 = document.getElementById('sectorChart').getContext('2d');
        new Chart(ctx2, {{
            type: 'pie',
            data: {{
                labels: chartData.setorLabels,
                datasets: [{{
                    data: chartData.setorValues,
                    backgroundColor: [
                        '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
                        '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1'
                    ],
                    borderWidth: 1
                }}]
            }},
            options: {{
                responsive: true,
                maintainAspectRatio: false,
                plugins: {{
                    legend: {{ position: 'right' }}
                }}
            }}
        }});

        // Ordenação client-side
        function formatMoney(num) {{
            if (num === null || num === undefined) return '-';
            if (num >= 1e9) return 'R$ ' + (num/1e9).toFixed(2) + ' Bi';
            if (num >= 1e6) return 'R$ ' + (num/1e6).toFixed(2) + ' Mi';
            return 'R$ ' + num.toFixed(2);
        }}
    </script>
</body>
</html>'''
    return html

def main():
    base_dir = Path('/Users/diegoteixeira/iaemloop-site-opt')
    data_dir = base_dir / 'data'
    data_dir.mkdir(exist_ok=True)

    barsi_json = data_dir / 'barsi_latest.json'
    if not barsi_json.exists():
        print(f'⚠️  {barsi_json} não encontrado.')
        return

    data = load_json(barsi_json)
    update_date = data['meta'].get('gerado_em', datetime.now().isoformat())[:10]
    html = generate_barsi_html(data, update_date)
    (base_dir / 'barsi.html').write_text(html, encoding='utf-8')
    print('✅ barsi.html gerado com sucesso (com gráficos)!')

if __name__ == '__main__':
    main()
