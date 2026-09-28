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


# Quanto esperar por um servidor que não responde. Sem isto, um banco fora do
# ar numa rede que engole o pacote (firewall que descarta em vez de recusar)
# deixa o programa preso no connect do sistema operacional — no Windows isso
# passa de vinte segundos, e antes da primeira janela: o processo abre e não
# aparece nada na tela. Com o limite, o erro chega rápido e a tela de Conexão
# assume. O libpq não aceita menos de 2 segundos.
ESPERA_CONEXAO = max(2, int(os.getenv("ROTAS_DB_TIMEOUT", "5")))


def get_engine() -> Engine:
    """Engine único da aplicação, criado na primeira chamada."""
    global _engine
    if _engine is None:
        _engine = create_engine(
            database_url(),
            echo=os.getenv("ROTAS_SQL_ECHO") == "1",
            pool_pre_ping=True,
            connect_args={"connect_timeout": ESPERA_CONEXAO},
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


def reiniciar() -> None:
    """Esquece a conexão atual — usado quando a configuração muda."""
    global _engine, _session_factory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _session_factory = None


def init_db() -> None:
    """Cria as tabelas que ainda não existem no banco."""
    from app.models import Base  # import local evita dependência circular

    Base.metadata.create_all(get_engine())
