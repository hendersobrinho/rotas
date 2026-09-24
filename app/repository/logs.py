"""Registro de atividades: só acrescenta linhas, nunca altera."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app import sessao as sessao_app
from app.models import AcaoLog, EntidadeLog, RegistroAtividade


def registrar(
    sessao: Session,
    acao: AcaoLog,
    entidade: EntidadeLog,
    descricao: str,
    entidade_id: int | None = None,
    usuario_id: int | None = None,
    usuario_nome: str | None = None,
) -> RegistroAtividade:
    """Anota uma atividade.

    Sem `usuario_id`/`usuario_nome`, usa quem estiver logado — é o caso das
    telas. O login informa explicitamente, porque ali ainda não há sessão.
    """
    registro = RegistroAtividade(
        acao=acao,
        entidade=entidade,
        descricao=descricao,
        entidade_id=entidade_id,
        usuario_id=usuario_id if usuario_id is not None else sessao_app.id_atual(),
        usuario_nome=usuario_nome or sessao_app.nome_atual(),
    )
    sessao.add(registro)
    sessao.flush()
    return registro


def listar(
    sessao: Session,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    usuario_id: int | None = None,
    acao: AcaoLog | None = None,
    entidade: EntidadeLog | None = None,
    termo: str | None = None,
    limite: int = 500,
) -> list[RegistroAtividade]:
    consulta = select(RegistroAtividade)
    if data_inicio is not None:
        consulta = consulta.where(
            RegistroAtividade.quando >= datetime.combine(data_inicio, time.min)
        )
    if data_fim is not None:
        consulta = consulta.where(
            RegistroAtividade.quando
            < datetime.combine(data_fim + timedelta(days=1), time.min)
        )
    if usuario_id is not None:
        consulta = consulta.where(RegistroAtividade.usuario_id == usuario_id)
    if acao is not None:
        consulta = consulta.where(RegistroAtividade.acao == acao)
    if entidade is not None:
        consulta = consulta.where(RegistroAtividade.entidade == entidade)
    if termo and termo.strip():
        padrao = f"%{termo.strip()}%"
        consulta = consulta.where(
            or_(
                RegistroAtividade.descricao.ilike(padrao),
                RegistroAtividade.usuario_nome.ilike(padrao),
            )
        )
    consulta = consulta.order_by(RegistroAtividade.quando.desc(), RegistroAtividade.id.desc())
    return list(sessao.scalars(consulta.limit(limite)).unique())


def contar(sessao: Session) -> int:
    return int(sessao.scalar(select(func.count(RegistroAtividade.id))) or 0)
