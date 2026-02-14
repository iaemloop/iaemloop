# 🧠 IA em Loop - Site Público

> Investimentos com Inteligência Artificial • Skin in the Game

Este repositório contém o **código aberto e land pages** das carteiras de investimento do canal [IA em Loop](https://www.youtube.com/@IAemLoop).

---

## 📂 Estrutura

```
.
├── index.html                    # Página principal com links
├── landpage_final.html          # Carteira Barsi (Dividendos)
├── greenblatt_landing.html      # Carteira Greenblatt (Fórmula Mágica)
├── youtube_banner_2560x1440.html # Banner do canal
├── pipeline.py                  # Pipeline de filtragem (Barsi)
├── greenblatt_ranking.py        # Pipeline da Fórmula Mágica
├── empresas_info.csv            # Mapeamento ticker → empresa/setor
├── outputs/                     # Resultados das execuções
└── references/                  # (VAZIO - memórias privadas em repo separado)
```

---

## 🎯 Carteiras

### 1. Carteira Barsi (Dividendos)
- **Metodologia**: Luiz Barsi Filho - "O Rei dos Dividendos"
- **Critérios**: DY ≥3%, P/VPA ≤2.0, setores perenes
- **Capital**: R$500
- **Resultado**: 11 ações selecionadas (execução 12/02/2026)
- **Land page**: `landpage_final.html`

### 2. Carteira Greenblatt (Fórmula Mágica)
- **Metodologia**: Joel Greenblatt - "The Little Book That Beats the Market"
- **Critérios**: ROIC + Earnings Yield (top 30)
- **Capital**: R$500
- **Resultado**: Top 30 ações da B3
- **Land page**: `greenblatt_landing.html`

---

## 🚀 Como Executar

### Pipeline Barsi
```bash
pip install -r requirements.txt
python pipeline.py
```
Saída em `outputs/`.

### Pipeline Greenblatt
```bash
python generate_greenblatt_landing.py
```
Gera `greenblatt_landing.html` e `greenblatt_top30.csv`.

---

## 🌐 Visualizar Land Pages

Execute o servidor local:
```bash
python3 -m http.server 8081
```

Acesse:
- http://localhost:8081/ →lista de land pages
- http://localhost:8081/landpage_final.html →Barsi
- http://localhost:8081/greenblatt_landing.html →Greenblatt

---

## 📊 Dados

- Fonte B3: yfinance (com fallback para Fundamentus via scraping)
- Empresas_info.csv: mapeamento manual de tickers para nomes/setores
- Arquivos CSV gerados em formatos compatíveis

---

## 🔐 Repositório Privado

As **memórias** (MEMORY.md, memory/, references/) estão em repo separado e privado:

**Tyrion Hand Memories** (privado) - contém:
- Anotações de livros (Buffett, Barsi, Greenblatt)
- Diário de sessões
- Configurações internas
- Scripts de backup

**Este repo aqui (`iaemloop`) é público** e contém apenas código e dados abertos.

---

## 📺 Canal YouTube

- Nome: **IA em Loop**
- URL: https://www.youtube.com/@IAemLoop
- Abordagem: Skin in the game, transparência total
- Duas carteiras reais com R$500 cada
- Começa sem rosto, depois voz, depois aparição gradual

---

## 🤝 Contribuindo

Este repo é mantido pelo bot Tyrion. Issues e PRs são bem-vindos, mas note que:
- Estratégias são pessoais e não são recomendações de investimento
- Faça sua própria due diligence
- Não nos responsabilizamos por perdas

---

## 📝 Licença

Código: MIT (ver LICENSE)

Dados: Para uso educacional. Consulte as fontes originais (B3, yfinance).

---

🧙‍♂️ *Mantido por Tyrion Bot*

**Última atualização**: 2026-02-14