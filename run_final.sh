#!/bin/zsh
set -e

cd "$(dirname "$0")"

echo "=== Verificando Python ==="
which python3
python3 --version

echo "\n=== Criando virtual environment ==="
python3 -m venv venv

echo "\n=== Ativando venv e instalando dependências ==="
source venv/bin/activate
pip install --upgrade pip
pip install pandas yfinance numpy

echo "\n=== Executando pipeline ==="
python pipeline.py

echo "\n=== Concluído ==="