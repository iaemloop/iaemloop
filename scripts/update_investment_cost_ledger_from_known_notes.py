#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data' / 'investment_costs_2026.json'

def trade(ticker, quantity, price, side='Compra'):
    return {
        'ticker': ticker,
        'side': side,
        'quantity': quantity,
        'average_price_brl': round(price, 4),
        'gross_value_brl': round(quantity * price, 2),
    }

def exact_entry(date, settlement, broker, portfolio, note_number, gross, liquid, fees, source, trades, status='exact_pdf_extracted'):
    return {
        'date': date,
        'date_precision': 'day',
        'settlement_date': settlement,
        'broker': broker,
        'portfolio': portfolio,
        'note_number': note_number,
        'source': source,
        'source_status': status,
        'currency': 'BRL',
        'gross_operations_brl': round(gross, 2),
        'settlement_total_brl': round(liquid, 2) if liquid is not None else None,
        'costs': {
            'clearing_fees_brl': fees.get('clearing'),
            'exchange_fees_brl': fees.get('exchange'),
            'registration_fees_brl': fees.get('registration'),
            'asset_transfer_fee_brl': fees.get('asset_transfer'),
            'brokerage_brl': fees.get('brokerage'),
            'irrf_brl': fees.get('irrf'),
            'iss_brl': fees.get('iss'),
            'iof_brl': fees.get('iof'),
            'fx_spread_brl': fees.get('fx_spread'),
            'other_costs_brl': fees.get('other'),
        },
        'trades': trades,
        'cost_total_brl': round(sum(v for v in fees.values() if isinstance(v, (int, float))), 2),
    }

def reconstructed_entry(date, broker, portfolio, label, gross, source, trades, note='Original PDF/text not available in current cache; reconstructed from prior carteira update references and current public custody arithmetic.'):
    return {
        'date': date,
        'date_precision': 'month' if date.endswith('-00') else 'day',
        'settlement_date': None,
        'broker': broker,
        'portfolio': portfolio,
        'note_number': label,
        'source': source,
        'source_status': 'reconstructed_from_prior_extraction',
        'currency': 'BRL',
        'gross_operations_brl': round(gross, 2),
        'settlement_total_brl': None,
        'costs': {
            'clearing_fees_brl': None,
            'exchange_fees_brl': None,
            'registration_fees_brl': None,
            'asset_transfer_fee_brl': None,
            'brokerage_brl': None,
            'irrf_brl': None,
            'iss_brl': None,
            'iof_brl': None,
            'fx_spread_brl': None,
            'other_costs_brl': None,
        },
        'trades': trades,
        'cost_total_brl': None,
        'note': note,
    }

entries = []

# BESST / Ágora: posições iniciais já existentes antes das notas de maio, reconstruídas da carteira pública.
entries.append(reconstructed_entry(
    '2026-03-00', 'Ágora', 'BESST & Buffett B3', 'BESST-inicial-marco-2026', 577.24,
    'carteira-notes-and-proceeds-workflow-2026-05-18.md + carteira_besst_real.html',
    [
        trade('TAEE11', 3, 43.23), trade('CSMG3', 2, 53.83), trade('PSSA3', 2, 51.65),
        trade('SAPR11', 2, 44.33), trade('BRSR6', 3, 18.41), trade('BMGB4', 10, 4.95),
        trade('CPLE3', 3, 14.40),
    ]
))

# Magic Formula / XP-Rico: posições iniciais antes da atualização de maio, reconstruídas por diferença.
entries.append(reconstructed_entry(
    '2026-03-00', 'XP/Rico', 'Magic Formula B3', 'Magic-inicial-marco-2026', 549.61,
    'carteira-notes-and-proceeds-workflow-2026-05-18.md + carteira_magic_formula_real.html',
    [
        trade('CSED3', 9, 6.33), trade('CMIN3', 11, 5.05), trade('CSUD3', 3, 19.14),
        trade('BEEF3', 10, 4.94), trade('PETR4', 2, 41.78), trade('PLPL3', 3, 11.80),
        trade('QUAL3', 25, 1.89), trade('TGMA3', 2, 39.40), trade('VTRU3', 3, 14.18),
        trade('WIZC3', 5, 4.51),
    ],
    note='Reconstructed from May-reference total and current custody history; ticker-level March split is approximate where original March note is no longer in cache.'
))

# Maio.
entries.append(reconstructed_entry(
    '2026-05-13', 'Ágora', 'BESST & Buffett B3', 'Agora-maio-2026', 197.92,
    'carteira-notes-and-proceeds-workflow-2026-05-18.md',
    [trade('ENGI3', 5, 12.35), trade('KLBN4', 16, 3.36), trade('SANB11', 3, 27.47)],
    note='Trades exactly from prior extraction reference; note-level fees unavailable because the original PDF is not in current cache.'
))
entries.append(reconstructed_entry(
    '2026-05-13', 'Rico', 'Magic Formula B3', 'Rico-maio-2026', 207.56,
    'carteira-notes-and-proceeds-workflow-2026-05-18.md + price history',
    [trade('CMIN3', 9, 5.05), trade('PSSA3', 1, 48.50), trade('WIZC3', 5, 8.55), trade('PLPL3', 6, 11.81)],
    note='Quantities from prior extraction reference; prices from carteira price-history/weighted arithmetic; note-level fees unavailable.'
))

# Junho.
entries.append(reconstructed_entry(
    '2026-06-17', 'Ágora', 'BESST & Buffett B3', 'Agora-junho-2026', 489.35,
    'carteira-june-2026-brokerage-notes-update.md',
    [trade('ENGI3', 3, 11.83), trade('KLBN4', 25, 3.43), trade('PETR4', 4, 38.50), trade('VIVT3', 4, 33.32), trade('VALE3', 1, 80.83)],
    note='Trades exactly from prior extraction reference; note-level fees unavailable because original June PDF is not in current cache.'
))
entries.append(reconstructed_entry(
    '2026-06-17', 'Rico', 'Magic Formula B3', 'Rico-junho-2026', 500.26,
    'carteira-june-2026-brokerage-notes-update.md',
    [
        trade('CSED3', 25, 3.56), trade('CSUD3', 4, 15.79), trade('CSUD3', 1, 15.78),
        trade('PSSA3', 2, 51.61), trade('QUAL3', 60, 1.56), trade('TGMA3', 1, 31.49),
        trade('VTRU3', 6, 13.57), trade('WIZC3', 3, 7.53),
    ],
    note='Trades exactly from prior extraction reference; note-level fees unavailable because original June PDF is not in current cache.'
))

# Julho PDFs atuais.
entries.append(exact_entry(
    '2026-07-13', '2026-07-15', 'Ágora', 'BESST & Buffett B3', '16141118', 413.34, 413.46,
    {'clearing':0.09,'exchange':0.02,'registration':0.0,'asset_transfer':0.01,'brokerage':0.0,'irrf':0.0,'iss':0.0,'iof':0.0,'fx_spread':0.0,'other':0.0},
    'Negociação Agora Jul.pdf',
    [trade('ENGI3',8,12.16), trade('EQTL3',2,40.13), trade('SANB11',6,27.19), trade('VALE3',1,72.66)]
))
entries.append(exact_entry(
    '2026-07-13', '2026-07-15', 'Rico', 'Magic Formula B3', '140032061', 497.12, 497.26,
    {'clearing':0.11,'exchange':0.02,'registration':0.0,'asset_transfer':0.01,'brokerage':0.0,'irrf':0.0,'iss':0.0,'iof':0.0,'fx_spread':0.0,'other':0.0},
    'Negociação Rico Jul.pdf',
    [trade('CMIN3',12,5.55), trade('POMO3',21,5.28), trade('LEVE3',4,32.14), trade('PLPL3',12,8.15), trade('WIZC3',11,8.48)]
))
entries.append(exact_entry(
    '2026-07-14', '2026-07-16', 'Ágora', 'BESST & Buffett B3', '60256014-provisional', 24.78, 24.78,
    {'clearing':0.0,'exchange':0.0,'registration':0.0,'asset_transfer':0.0,'brokerage':0.0,'irrf':0.0,'iss':0.0,'iof':0.0,'fx_spread':0.0,'other':0.0},
    'execução informada por Diego: ENGI3F 2 @12,39; substituir pela nota oficial quando recebida',
    [trade('ENGI3',2,12.39)],
    status='provisional_execution_notice'
))

# Summaries.
summary = {}
for e in entries:
    broker = e['broker']
    s = summary.setdefault(broker, {'gross_operations_brl':0.0, 'known_cost_total_brl':0.0, 'entries':0, 'entries_with_unknown_costs':0})
    s['gross_operations_brl'] += e['gross_operations_brl'] or 0
    s['entries'] += 1
    if e['cost_total_brl'] is None:
        s['entries_with_unknown_costs'] += 1
    else:
        s['known_cost_total_brl'] += e['cost_total_brl']
for s in summary.values():
    s['gross_operations_brl'] = round(s['gross_operations_brl'],2)
    s['known_cost_total_brl'] = round(s['known_cost_total_brl'],2)

ledger = {
    'schema': 'iaemloop-investment-cost-ledger-v2',
    'updated_at': '2026-07-14',
    'scope': 'IA em Loop real investment brokerage notes and execution notices for 2026',
    'privacy': 'Public-safe aggregate/trade data only; no CPF, address, account number or private PDF text.',
    'entries': entries,
    'summary_by_broker': summary,
    'notes': [
        'Entries marked reconstructed_from_prior_extraction came from previous note-extraction references and current public carteira arithmetic because the original PDFs are not present in the current Hermes cache.',
        'The 2026-07-14 ENGI3F entry is provisional and must be replaced by the official brokerage note when Diego sends it.',
        'Dollarized/Inter brokerage, IOF, FX and spread should be appended after the official execution/FX documents are available.',
    ]
}
OUT.parent.mkdir(exist_ok=True)
OUT.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print('wrote', OUT)
print('entries', len(entries))
print(json.dumps(summary, ensure_ascii=False, indent=2))
