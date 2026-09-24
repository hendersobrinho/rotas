"""Conexão com o PostgreSQL e gerenciamento de sessões do SQLAlchemy."""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator
from urllib.parse import quote_plus

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session, sessionmaker

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def database_url() -> str:
    """Monta a URL de conexão a partir das variáveis de ambiente.

    Use ROTAS_DATABASE_URL para informar a URL completa ou, alternativamente,
    as variáveis separadas (ROTAS_DB_HOST, ROTAS_DB_PORT, ...).
    """
    url = os.getenv("ROTAS_DATABASE_URL")
    if url:
        return url

    usuario = quote_plus(os.getenv("ROTAS_DB_USER", "postgres"))
    senha = quote_plus(os.getenv("ROTAS_DB_PASSWORD", ""))
    host = os.getenv("ROTAS_DB_HOST", "localhost")
    porta = os.getenv("ROTAS_DB_PORT", "5432")
    banco = os.getenv("ROTAS_DB_NAME", "rotas")

    credenciais = usuario if not senha else f"{usuario}:{senha}"
    return f"postgresql+psycopg://{credenciais}@{host}:{porta}/{banco}"


def url_mascarada() -> str:
    """Mesma URL, com a senha escondida — segura para mensagens e logs."""
    return make_url(database_url()).render_as_string(hide_password=True)


def get_engine() -> Engine:
    """Engine único da aplicação, criado na primeira chamada."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            database_url(),
            echo=os.getenv("ROTAS_SQL_ECHO") == "1",
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        # expire_on_commit=False permite ler os atributos dos objetos depois de
        # a sessão ser fechada, o que simplifica muito o uso nas telas.
        _session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False)
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    """Abre uma sessão, faz commit no fim e rollback em caso de erro."""
    sessao = get_session_factory()()
    try:
        yield sessao
        sessao.commit()
    except Exception:
        sessao.rollback()
        raise
    finally:
        sessao.close()


def init_db() -> None:
    """Cria as tabelas que ainda não existem no banco."""
    from app.models import Base  # import local evita dependência circular

    Base.metadata.create_all(get_engine())
