"""Libera vários endereços por cliente e cria a coluna de rótulo.

    .venv/bin/python scripts/migrar_varios_enderecos.py

Pode rodar de novo sem estragar nada.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import configuracao  # noqa: E402

configuracao.carregar_env()

from sqlalchemy import inspect, text  # noqa: E402

from app.db import get_engine, init_db, url_mascarada  # noqa: E402


def main() -> int:
    print("banco:", url_mascarada())
    engine = get_engine()
    init_db()

    inspetor = inspect(engine)
    if "enderecos" not in inspetor.get_table_names():
        print("banco novo: nada a migrar")
        return 0
    colunas = {c["name"] for c in inspetor.get_columns("enderecos")}

    with engine.begin() as con:
        if "rotulo" not in colunas:
            con.execute(text("alter table enderecos add column rotulo varchar(60)"))
            print("coluna rotulo criada")
        else:
            print("coluna rotulo já existia")

        # A trava de "um endereço de cada tipo" é justamente o que sai.
        restricoes = [
            linha[0]
            for linha in con.execute(text(
                "select conname from pg_constraint"
                " where conname = 'uq_endereco_cliente_tipo'"))
        ]
        if restricoes:
            con.execute(text(
                "alter table enderecos drop constraint uq_endereco_cliente_tipo"))
            print("restrição de um endereço por tipo removida")
        else:
            print("restrição já não existia")

    print("migração concluída")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
