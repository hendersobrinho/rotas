"""Roda as verificações num banco descartável — no Windows e no Linux.

    .venv-win\\Scripts\\python testes\\rodar.py        (Windows)
    .venv/bin/python testes/rodar.py                 (Linux)
    ... testes/rodar.py pdf interface                (só os que casam)

Usa a conexão do .env, trocando o banco por `rotas_teste` (ou o que estiver em
ROTAS_BANCO_TESTE), que é apagado e criado de novo antes de cada arquivo. O
usuário do .env precisa poder criar banco. O mesmo que testes/rodar.sh, sem
depender de dropdb/createdb no PATH.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from dotenv import load_dotenv  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

load_dotenv(RAIZ / ".env")
from app.db import database_url  # noqa: E402

BANCO = os.environ.get("ROTAS_BANCO_TESTE", "rotas_teste")


def _url_teste():
    if os.environ.get("ROTAS_URL_TESTE"):
        return make_url(os.environ["ROTAS_URL_TESTE"])
    return make_url(database_url()).set(database=BANCO)


def recriar() -> None:
    import psycopg

    url = _url_teste()
    with psycopg.connect(
        host=url.host or "localhost",
        port=url.port or 5432,
        user=url.username,
        password=url.password or "",
        dbname="postgres",
        autocommit=True,
    ) as conexao:
        conexao.execute(f'DROP DATABASE IF EXISTS "{url.database}" WITH (FORCE)')
        conexao.execute(f'CREATE DATABASE "{url.database}"')


def main() -> int:
    filtro = sys.argv[1:]
    try:
        recriar()
    except Exception as erro:
        print(f"não deu para criar o banco de teste: {erro}")
        return 1

    falhas = 0
    for arquivo in sorted((RAIZ / "testes").glob("teste_*.py")):
        if filtro and not any(f in arquivo.name for f in filtro):
            continue
        shutil.rmtree(RAIZ / "testes" / ".dados", ignore_errors=True)
        ambiente = dict(
            os.environ,
            PYTHONPATH=str(RAIZ / "testes"),
            PYTHONIOENCODING="utf-8",
            ROTAS_URL_TESTE=_url_teste().render_as_string(hide_password=False),
        )
        saida = subprocess.run(
            [sys.executable, str(arquivo)], cwd=RAIZ, env=ambiente,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        texto = saida.stdout + saida.stderr
        ok = any(linha.rstrip().endswith(" OK") for linha in texto.splitlines())
        print(("OK      " if ok else "FALHOU  ") + arquivo.stem, flush=True)
        if not ok:
            falhas += 1
            linhas = [
                linha for linha in texto.splitlines()
                if "Gtk-WARNING" not in linha and "Theme parsing" not in linha
            ]
            print("\n".join(linhas[-15:]), flush=True)
        recriar()
    return 1 if falhas else 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
