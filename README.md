# Barsi Screener 📈

Pipeline para filtrar ações brasileiras (B3) seguindo a metodologia de Luiz Barsi Filho do livro **"O Rei dos Dividendos"**.

## Filosofia

- Dividendos, não especulação
- Empresas perenes (energia, papel/celulose, bancos, saneamento, telecom)
- Comprar barato, guardar e reinvestir dividendos
- Horizonte de 10-30 anos

## Como usar

### 1. Instalar dependências

```bash
pip install -r requirements.txt
```

### 2. Executar pipeline

```bash
python pipeline.py
```

### 3. Resultados

Os arquivos são gerados em `outputs/`:
- `barsi_screener_[timestamp].csv` - planilha completa
- `barsi_screener_latest.csv` - última execução
- `relatorio_[timestamp].md` - resumo formatado

## Critérios de filtragem

| Critério | Threshold |
|----------|-----------|
| Dividend Yield | > 5% ao ano |
| P/VPA (Preço/Valor Patrimonial) | < 1.5 |
| Tempo de listed | > 10 anos |
| Volume médio diário | > R$ 1 milhão |
| Market cap mínimo | > R$ 500 milhões |
| Histórico de dividendos | ≥ 5 anos consecutivos |
| Setor | Apenas setores perenes (energia, papel/celulose, bancos, saneamento, telecom, mineração, química/petróleo, seguros) |

## Setores perenes incluídos

- **Energia** (ELETROBRAS, EQUATORIAL, ENERGISA, ENGIE, EDP-BR, CPFL)
- **Papel e Celulose** (KLABIN, SUZANO, FIBRIA)
- **Bancos** (BBAS3, ITUB4, BBDC4, SANB11, BPAC11)
- **Saneamento** (SABESP, COPASA)
- **Telecom** (VIVT3, TIMB3, TOTS3)
- **Mineração** (VALE3)
- **Química/Petróleo** (UNIPAR, BRAP4, PETR4, PETR3)
- **Seguros** (PSSA3, SULA11, IRBR3)

## Score

As ações são ranqueadas por um score que considera:
- Dividend Yield (quanto maior, melhor)
- P/VPA (quanto menor, melhor)
- Liquidez (volume)
- Anos de listed
- Consistência de dividendos

## Personalização

Altere os thresholds no topo do `pipeline.py`:

```python
MIN_DIVIDEND_YIELD = 0.05    # 5%
MAX_PVPA = 1.5               # Preço <= 1.5x valor patrimonial
MIN_HISTORY_YEARS = 10       # Mínimo 10 anos na bolsa
MIN_VOLUME_BRL = 1_000_000   # Volume mínimo R$ 1M/dia
MIN_MARKET_CAP = 500_000_000 # Market cap mínimo R$ 500M
```

## Adicionar novos tickers

Edite a função `get_b3_tickers()` no `pipeline.py` para incluir mais ações.

## Nota

Esta pipeline é uma homenagem à metodologia de Barsi, mas **não é recomendação de investimento**. Faça sua própria due diligence.

---

🧙‍♂️ *"Com paciência e disciplina, é impossível perder dinheiro com ações."* - Luiz Barsi Filho