#!/usr/bin/env python3
import subprocess
import sys
import os
import venv

def main():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    venv_dir = os.path.join(base_dir, 'venv')

    # Criar venv se não existir
    if not os.path.exists(venv_dir):
        print(f"Criando virtual environment em {venv_dir}...")
        venv.create(venv_dir, with_pip=True)

    # Ativar venv (não precisamos source, usamos o python do venv diretamente)
    if sys.platform == 'win32':
        python_path = os.path.join(venv_dir, 'Scripts', 'python')
    else:
        python_path = os.path.join(venv_dir, 'bin', 'python')

    # Instalar dependências
    print("Instalando dependências no venv...")
    subprocess.check_call([python_path, '-m', 'pip', 'install', '--upgrade', 'pip'])
    subprocess.check_call([python_path, '-m', 'pip', 'install', 'pandas', 'yfinance', 'numpy'])

    # Executar pipeline
    print("\nExecutando pipeline...")
    os.chdir(base_dir)
    subprocess.check_call([python_path, 'pipeline.py'])

if __name__ == '__main__':
    main()