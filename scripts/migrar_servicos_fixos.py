"""Cria a tabela de serviços fixos e o vínculo nos eventos.

    .venv/bin/python scripts/migrar_servicos_fixos.py

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
    init_db()  # cria a tabela recorrencias, se faltar

    inspetor = inspect(engine)
    if "eventos" not in inspetor.get_table_names():
        print("banco novo: nada a migrar")
        return 0
    colunas = {c["name"] for c in inspetor.get_columns("eventos")}

    with engine.begin() as con:
        if "recorrencia_id" not in colunas:
            con.execute(text(
                "alter table eventos add column recorrencia_id integer"))
            con.execute(text("""
                alter table eventos
                  add constraint eventos_recorrencia_id_fkey
                  foreign key (recorrencia_id) references recorrencias (id)
                  on delete set null
            """))
            con.execute(text(
                "create index if not exists ix_eventos_recorrencia_id"
                " on eventos (recorrencia_id)"))
            print("coluna recorrencia_id criada")
        else:
            print("coluna recorrencia_id já existia")

    print("migração concluída")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
