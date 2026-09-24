"""Migra o banco para tipos de serviço e solicitantes cadastráveis.

Antes: `eventos.tipo_servico` era um ENUM nativo e `eventos.solicitante` um
texto solto. Depois: as duas viram chaves estrangeiras para as tabelas novas.

Pode rodar mais de uma vez — cada passo confere antes se já foi feito.

    .venv/bin/python scripts/migrar_tipos_e_solicitantes.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from sqlalchemy import inspect, text  # noqa: E402

from app.db import get_engine, init_db, session_scope, url_mascarada  # noqa: E402
from app.repository import tipos_servico as repo_tipos  # noqa: E402


def coluna_existe(inspetor, tabela: str, coluna: str) -> bool:
    if tabela not in inspetor.get_table_names():
        return False
    return coluna in {c["name"] for c in inspetor.get_columns(tabela)}


def main() -> int:
    print("banco:", url_mascarada())
    engine = get_engine()

    # 1. cria as tabelas novas (e as antigas, se o banco estiver vazio)
    init_db()
    print("tabelas garantidas")

    # 2. Coleta e Retirada como ponto de partida
    with session_scope() as sessao:
        tipos = repo_tipos.garantir_padrao(sessao)
    print("tipos de serviço:", ", ".join(t.nome for t in tipos))

    inspetor = inspect(engine)
    tinha_enum = coluna_existe(inspetor, "eventos", "tipo_servico")
    tinha_texto = coluna_existe(inspetor, "eventos", "solicitante")
    if not (tinha_enum or tinha_texto):
        print("nada a migrar: eventos já está no formato novo")
        return 0

    with engine.begin() as con:
        if tinha_texto:
            # cada solicitante que já aparecia escrito à mão vira cadastro
            con.execute(text("""
                insert into solicitantes (nome, ativo)
                select distinct btrim(solicitante), true
                  from eventos
                 where solicitante is not null and btrim(solicitante) <> ''
                   and not exists (
                       select 1 from solicitantes s
                        where lower(s.nome) = lower(btrim(eventos.solicitante))
                          and s.setor is null)
            """))
            con.execute(text(
                "alter table eventos add column if not exists solicitante_id integer"))
            con.execute(text("""
                update eventos e
                   set solicitante_id = s.id
                  from solicitantes s
                 where s.setor is null
                   and lower(s.nome) = lower(btrim(e.solicitante))
            """))
            con.execute(text("alter table eventos drop column solicitante"))
            con.execute(text("""
                alter table eventos
                  add constraint eventos_solicitante_id_fkey
                  foreign key (solicitante_id) references solicitantes (id)
                  on delete set null
            """))
            con.execute(text(
                "create index if not exists ix_eventos_solicitante_id"
                " on eventos (solicitante_id)"))
            print("solicitantes migrados")

        if tinha_enum:
            con.execute(text(
                "alter table eventos add column if not exists tipo_servico_id integer"))
            con.execute(text("""
                update eventos e
                   set tipo_servico_id = t.id
                  from tipos_servico t
                 where upper(t.nome) = e.tipo_servico::text
            """))
            orfaos = con.execute(text(
                "select count(*) from eventos where tipo_servico_id is null")).scalar()
            if orfaos:
                raise SystemExit(
                    f"{orfaos} evento(s) com tipo sem correspondência — migração abortada")
            con.execute(text("alter table eventos drop column tipo_servico"))
            con.execute(text(
                "alter table eventos alter column tipo_servico_id set not null"))
            con.execute(text("""
                alter table eventos
                  add constraint eventos_tipo_servico_id_fkey
                  foreign key (tipo_servico_id) references tipos_servico (id)
                  on delete restrict
            """))
            con.execute(text(
                "create index if not exists ix_eventos_tipo_servico_id"
                " on eventos (tipo_servico_id)"))
            con.execute(text("drop type if exists tipo_servico"))
            print("tipos de serviço migrados")

    print("migração concluída")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
