#!/bin/zsh
set -e

cd "$(dirname "$0")"

echo "=== Instalando dependências ==="
python3 -m pip install --break-system-packages pandas yfinance numpy

echo "\n=== Executando pipeline ==="
python3 pipeline.py

echo "\n=== Concluído ==="