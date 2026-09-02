#!/usr/bin/env python3
import subprocess
import sys
import os

def run_command(cmd, cwd=None):
    """Roda comando e captura saida em tempo real."""
    print(f"Executando: {' '.join(cmd)}")
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    # Ler em tempo real
    for line in proc.stdout:
        print(line, end='')
        sys.stdout.flush()
    proc.wait()
    return proc.returncode

if __name__ == '__main__':
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # Instalar
    print("\n=== Instalando dependências ===")
    rc = run_command([sys.executable, "-m", "pip", "install", "--user", "pandas", "yfinance", "numpy"], cwd=base_dir)
    if rc != 0:
        print(f"Erro na instalação (código {rc})")
        sys.exit(1)
    print("\n=== Executando pipeline ===")
    rc = run_command([sys.executable, "pipeline.py"], cwd=base_dir)
    print(f"\nPipeline finalizada com código {rc}")
    sys.exit(rc)