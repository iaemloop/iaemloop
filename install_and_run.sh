#!/bin/zsh
cd "$(dirname "$0")"
python3 -m pip install --break-system-packages --no-cache-dir pandas yfinance numpy 2>&1 | tee install.log
python3 pipeline.py 2>&1 | tee run.log