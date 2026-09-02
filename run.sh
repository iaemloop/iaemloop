#!/bin/zsh
cd "$(dirname "$0")"
python3 -m pip install --user pandas yfinance numpy > /dev/null 2>&1
python3 pipeline.py