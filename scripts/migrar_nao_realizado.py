"""Acrescenta o estado 'não realizado', o motivo e o vínculo de remarcação.

Rode uma vez em bancos criados antes desta versão:

    .venv/bin/python scripts/migrar_nao_realizado.py

Pode rodar de novo sem estragar nada.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from sqlalchemy import inspect, text  # noqa: E402

from app.db import get_engine, init_db, url_mascarada  # noqa: E402


def main() -> int:
    print("banco:", url_mascarada())
    engine = get_engine()
    init_db()

    inspetor = inspect(engine)
    if "eventos" not in inspetor.get_table_names():
        print("banco novo: nada a migrar")
        return 0
    colunas = {c["name"] for c in inspetor.get_columns("eventos")}

    # ALTER TYPE ... ADD VALUE não roda dentro de transação junto com uso do
    # tipo, então vai em autocommit e à parte.
    with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as con:
        valores = [
            linha[0]
            for linha in con.execute(text(
                "select e.enumlabel from pg_enum e"
                " join pg_type t on t.oid = e.enumtypid"
                " where t.typname = 'status_evento'"))
        ]
        if "NAO_REALIZADO" not in valores:
            con.execute(text(
                "alter type status_evento add value 'NAO_REALIZADO' after 'CONCLUIDO'"))
            print("estado NAO_REALIZADO adicionado")
        else:
            print("estado NAO_REALIZADO já existia")

    with engine.begin() as con:
        if "motivo" not in colunas:
            con.execute(text("alter table eventos add column motivo text"))
            print("coluna motivo criada")
        if "origem_id" not in colunas:
            con.execute(text("alter table eventos add column origem_id integer"))
            con.execute(text("""
                alter table eventos
                  add constraint eventos_origem_id_fkey
                  foreign key (origem_id) references eventos (id)
                  on delete set null
            """))
            con.execute(text(
                "create index if not exists ix_eventos_origem_id"
                " on eventos (origem_id)"))
            print("coluna origem_id criada")

    print("migração concluída")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
