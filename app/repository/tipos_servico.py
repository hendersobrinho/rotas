"""Cadastro dos tipos de serviço (Coleta, Retirada, o que o escritório criar)."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Evento, TipoServico
from app.schemas import DadosTipoServico

PADRAO = (("Coleta", "azul"), ("Retirada", "laranja"))


def listar(sessao: Session, apenas_ativos: bool = False) -> list[TipoServico]:
    consulta = select(TipoServico)
    if apenas_ativos:
        consulta = consulta.where(TipoServico.ativo.is_(True))
    return list(sessao.scalars(consulta.order_by(func.lower(TipoServico.nome))))


def obter(sessao: Session, tipo_id: int) -> TipoServico | None:
    return sessao.get(TipoServico, tipo_id)


def criar(sessao: Session, dados: DadosTipoServico) -> TipoServico:
    dados = dados.normalizado()
    _validar(sessao, dados)
    tipo = TipoServico(nome=dados.nome, estilo=dados.estilo, ativo=dados.ativo)
    sessao.add(tipo)
    sessao.flush()
    return tipo


def atualizar(sessao: Session, tipo_id: int, dados: DadosTipoServico) -> TipoServico:
    tipo = obter(sessao, tipo_id)
    if tipo is None:
        raise ValueError("Tipo de serviço não encontrado.")
    dados = dados.normalizado()
    _validar(sessao, dados, ignorar_id=tipo_id)
    tipo.nome, tipo.estilo, tipo.ativo = dados.nome, dados.estilo, dados.ativo
    sessao.flush()
    return tipo


def contar_uso(sessao: Session, tipo_id: int) -> int:
    return int(
        sessao.scalar(
            select(func.count(Evento.id)).where(Evento.tipo_servico_id == tipo_id)
        )
        or 0
    )


def excluir(sessao: Session, tipo_id: int) -> None:
    """Só apaga tipo que nunca foi usado; o resto se desativa."""
    tipo = obter(sessao, tipo_id)
    if tipo is None:
        raise ValueError("Tipo de serviço não encontrado.")
    em_uso = contar_uso(sessao, tipo_id)
    if em_uso:
        raise ValueError(
            f"“{tipo.nome}” está em {em_uso} serviço(s) e não pode ser excluído.\n\n"
            "Desmarque “Ativo” para tirá-lo das novas marcações sem perder o histórico."
        )
    sessao.delete(tipo)
    sessao.flush()


def garantir_padrao(sessao: Session) -> list[TipoServico]:
    """Cria Coleta e Retirada quando o cadastro está vazio."""
    if sessao.scalar(select(func.count(TipoServico.id))):
        return listar(sessao)
    for nome, estilo in PADRAO:
        sessao.add(TipoServico(nome=nome, estilo=estilo))
    sessao.flush()
    return listar(sessao)


def _validar(sessao: Session, dados: DadosTipoServico, ignorar_id: int | None = None) -> None:
    if not dados.nome:
        raise ValueError("Dê um nome ao tipo de serviço.")
    consulta = select(TipoServico.id).where(func.lower(TipoServico.nome) == dados.nome.lower())
    if ignorar_id is not None:
        consulta = consulta.where(TipoServico.id != ignorar_id)
    if sessao.scalars(consulta).first() is not None:
        raise ValueError(f"Já existe um tipo de serviço chamado “{dados.nome}”.")
