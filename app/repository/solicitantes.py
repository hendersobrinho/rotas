"""Cadastro de quem pede os serviços: pessoas do escritório e seus setores."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AcaoLog, EntidadeLog, Evento, Solicitante
from app.repository import logs as repo_logs
from app.schemas import DadosSolicitante


def listar(sessao: Session, apenas_ativos: bool = False) -> list[Solicitante]:
    consulta = select(Solicitante)
    if apenas_ativos:
        consulta = consulta.where(Solicitante.ativo.is_(True))
    return list(
        sessao.scalars(
            consulta.order_by(
                func.lower(func.coalesce(Solicitante.setor, "")),
                func.lower(Solicitante.nome),
            )
        )
    )


def setores(sessao: Session) -> list[str]:
    """Setores já usados, para sugerir no formulário."""
    consulta = (
        select(Solicitante.setor)
        .where(Solicitante.setor.is_not(None))
        .distinct()
        .order_by(Solicitante.setor)
    )
    return [s for s in sessao.scalars(consulta) if s]


def obter(sessao: Session, solicitante_id: int) -> Solicitante | None:
    return sessao.get(Solicitante, solicitante_id)


def criar(sessao: Session, dados: DadosSolicitante) -> Solicitante:
    dados = dados.normalizado()
    _validar(sessao, dados)
    pessoa = Solicitante(nome=dados.nome, setor=dados.setor, ativo=dados.ativo)
    sessao.add(pessoa)
    sessao.flush()
    repo_logs.registrar(
        sessao, AcaoLog.CRIACAO, EntidadeLog.SOLICITANTE,
        f"Solicitante “{pessoa.nome_exibicao}”", pessoa.id,
    )
    return pessoa


def atualizar(sessao: Session, solicitante_id: int, dados: DadosSolicitante) -> Solicitante:
    pessoa = obter(sessao, solicitante_id)
    if pessoa is None:
        raise ValueError("Solicitante não encontrado.")
    dados = dados.normalizado()
    _validar(sessao, dados, ignorar_id=solicitante_id)
    pessoa.nome, pessoa.setor, pessoa.ativo = dados.nome, dados.setor, dados.ativo
    sessao.flush()
    repo_logs.registrar(
        sessao, AcaoLog.ALTERACAO, EntidadeLog.SOLICITANTE,
        f"Solicitante “{pessoa.nome_exibicao}”", pessoa.id,
    )
    return pessoa


def contar_uso(sessao: Session, solicitante_id: int) -> int:
    return int(
        sessao.scalar(
            select(func.count(Evento.id)).where(Evento.solicitante_id == solicitante_id)
        )
        or 0
    )


def excluir(sessao: Session, solicitante_id: int) -> None:
    """Apagar não destrói histórico: os serviços ficam sem solicitante."""
    pessoa = obter(sessao, solicitante_id)
    if pessoa is None:
        raise ValueError("Solicitante não encontrado.")
    nome = pessoa.nome_exibicao
    sessao.delete(pessoa)
    sessao.flush()
    repo_logs.registrar(
        sessao, AcaoLog.EXCLUSAO, EntidadeLog.SOLICITANTE,
        f"Solicitante “{nome}”", solicitante_id,
    )


def _validar(sessao: Session, dados: DadosSolicitante, ignorar_id: int | None = None) -> None:
    if not dados.nome:
        raise ValueError("Dê um nome ao solicitante.")
    consulta = select(Solicitante.id).where(
        func.lower(Solicitante.nome) == dados.nome.lower(),
        func.coalesce(func.lower(Solicitante.setor), "")
        == (dados.setor or "").lower(),
    )
    if ignorar_id is not None:
        consulta = consulta.where(Solicitante.id != ignorar_id)
    if sessao.scalars(consulta).first() is not None:
        raise ValueError(f"Já existe “{dados.nome}” nesse setor.")
