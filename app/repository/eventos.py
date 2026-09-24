"""Operações de banco relacionadas aos eventos de coleta/retirada."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Cliente, Evento, StatusEvento
from app.schemas import DadosEvento, FiltroEventos

_CAMPOS_EVENTO = (
    "cliente_id",
    "endereco_id",
    "tipo_servico",
    "data",
    "periodo",
    "solicitante",
    "status",
)


def listar_eventos(
    sessao: Session, filtro: FiltroEventos | None = None
) -> list[Evento]:
    """Lista eventos (mais recentes primeiro) aplicando os filtros informados."""
    filtro = filtro or FiltroEventos()
    consulta = select(Evento)

    if filtro.cliente_id is not None:
        consulta = consulta.where(Evento.cliente_id == filtro.cliente_id)
    if filtro.status is not None:
        consulta = consulta.where(Evento.status == filtro.status)
    if filtro.tipo_servico is not None:
        consulta = consulta.where(Evento.tipo_servico == filtro.tipo_servico)
    if filtro.data_inicio is not None:
        consulta = consulta.where(Evento.data >= filtro.data_inicio)
    if filtro.data_fim is not None:
        consulta = consulta.where(Evento.data <= filtro.data_fim)
    if filtro.termo and filtro.termo.strip():
        padrao = f"%{filtro.termo.strip()}%"
        consulta = consulta.where(Evento.solicitante.ilike(padrao))

    consulta = consulta.order_by(Evento.data.desc(), Evento.id.desc())
    return list(sessao.scalars(consulta).unique())


def historico_cliente(
    sessao: Session, cliente_id: int, mais_recente_primeiro: bool = True
) -> list[Evento]:
    """Histórico do cliente: seus eventos ordenados por data."""
    ordem = Evento.data.desc() if mais_recente_primeiro else Evento.data.asc()
    consulta = (
        select(Evento).where(Evento.cliente_id == cliente_id).order_by(ordem, Evento.id)
    )
    return list(sessao.scalars(consulta).unique())


def contar_eventos_do_cliente(sessao: Session, cliente_id: int) -> int:
    consulta = select(func.count(Evento.id)).where(Evento.cliente_id == cliente_id)
    return int(sessao.scalar(consulta) or 0)


def obter_evento(sessao: Session, evento_id: int) -> Evento | None:
    return sessao.get(Evento, evento_id)


def criar_evento(sessao: Session, dados: DadosEvento) -> Evento:
    dados = dados.normalizado()
    _validar(sessao, dados)

    evento = Evento(**{campo: getattr(dados, campo) for campo in _CAMPOS_EVENTO})
    sessao.add(evento)
    sessao.flush()
    return evento


def atualizar_evento(sessao: Session, evento_id: int, dados: DadosEvento) -> Evento:
    evento = obter_evento(sessao, evento_id)
    if evento is None:
        raise ValueError(f"Evento {evento_id} não encontrado.")

    dados = dados.normalizado()
    _validar(sessao, dados)

    for campo in _CAMPOS_EVENTO:
        setattr(evento, campo, getattr(dados, campo))
    sessao.flush()
    return evento


def alterar_status(sessao: Session, evento_id: int, status: StatusEvento) -> Evento:
    evento = obter_evento(sessao, evento_id)
    if evento is None:
        raise ValueError(f"Evento {evento_id} não encontrado.")
    evento.status = status
    sessao.flush()
    return evento


def cancelar_evento(sessao: Session, evento_id: int) -> Evento:
    """Cancelar não apaga o registro: só muda o status para Cancelado."""
    return alterar_status(sessao, evento_id, StatusEvento.CANCELADO)


def concluir_evento(sessao: Session, evento_id: int) -> Evento:
    return alterar_status(sessao, evento_id, StatusEvento.CONCLUIDO)


def excluir_evento(sessao: Session, evento_id: int) -> None:
    evento = obter_evento(sessao, evento_id)
    if evento is None:
        raise ValueError(f"Evento {evento_id} não encontrado.")
    sessao.delete(evento)
    sessao.flush()


def _validar(sessao: Session, dados: DadosEvento) -> None:
    cliente = sessao.get(Cliente, dados.cliente_id)
    if cliente is None:
        raise ValueError("Selecione um cliente válido para o evento.")
    if dados.data is None:
        raise ValueError("A data do evento é obrigatória.")

    if dados.endereco_id is not None:
        ids_validos = {endereco.id for endereco in cliente.enderecos}
        if dados.endereco_id not in ids_validos:
            raise ValueError("O endereço escolhido não pertence a este cliente.")
