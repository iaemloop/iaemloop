#!/bin/bash
# Run EUA stocks pipelines for IA em Loop
# Runs monthly on days 1-6

set -e

REPO_DIR="/Users/diegoteixeira/iaemloop-review-blog-20260507"
cd "$REPO_DIR"

echo "[$(date)] Starting EUA pipelines..."

# 1. Base fundamentals
echo "Running base pipeline..."
python3 pipeline_stocks_eua_base.py

# 2. BESST & Buffett
echo "Running BESST & Buffett pipeline..."
python3 pipeline_besst_buffett_stocks.py

# 3. Magic Formula
echo "Running Magic Formula pipeline..."
python3 pipeline_magic_formula_stocks.py

# 4. Watchlist
echo "Running Watchlist pipeline..."
python3 pipeline_watchlist_buffett_stocks.py

echo "[$(date)] EUA pipelines completed."