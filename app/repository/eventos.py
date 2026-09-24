"""Operações de banco relacionadas aos eventos de coleta/retirada."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    AcaoLog,
    Cliente,
    EntidadeLog,
    Evento,
    StatusEvento,
    TipoServico,
)
from app.repository import logs as repo_logs
from app.schemas import DadosEvento, FiltroEventos

_CAMPOS_EVENTO = (
    "cliente_id",
    "endereco_id",
    "tipo_servico_id",
    "data",
    "periodo",
    "solicitante_id",
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
    if filtro.tipo_servico_id is not None:
        consulta = consulta.where(Evento.tipo_servico_id == filtro.tipo_servico_id)
    if filtro.solicitante_id is not None:
        consulta = consulta.where(Evento.solicitante_id == filtro.solicitante_id)
    if filtro.data_inicio is not None:
        consulta = consulta.where(Evento.data >= filtro.data_inicio)
    if filtro.data_fim is not None:
        consulta = consulta.where(Evento.data <= filtro.data_fim)

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
    repo_logs.registrar(
        sessao, AcaoLog.CRIACAO, EntidadeLog.EVENTO, _descrever(evento), evento.id
    )
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
    repo_logs.registrar(
        sessao, AcaoLog.ALTERACAO, EntidadeLog.EVENTO, _descrever(evento), evento.id
    )
    return evento


def alterar_status(sessao: Session, evento_id: int, status: StatusEvento) -> Evento:
    evento = obter_evento(sessao, evento_id)
    if evento is None:
        raise ValueError(f"Evento {evento_id} não encontrado.")
    anterior = evento.status
    evento.status = status
    sessao.flush()
    repo_logs.registrar(
        sessao, AcaoLog.ALTERACAO, EntidadeLog.EVENTO,
        f"{_descrever(evento)} — de {anterior.value} para {status.value}", evento.id,
    )
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
    descricao = _descrever(evento)
    sessao.delete(evento)
    sessao.flush()
    repo_logs.registrar(
        sessao, AcaoLog.EXCLUSAO, EntidadeLog.EVENTO, descricao, evento_id
    )


def _descrever(evento: Evento) -> str:
    """Uma linha que explica o serviço no registro de atividades."""
    return (
        f"{evento.tipo_servico.nome} para {evento.cliente.nome_exibicao} "
        f"em {evento.data.strftime('%d/%m/%Y')} ({evento.periodo.value})"
    )


def _validar(sessao: Session, dados: DadosEvento) -> None:
    cliente = sessao.get(Cliente, dados.cliente_id)
    if cliente is None:
        raise ValueError("Selecione um cliente válido para o evento.")
    if dados.data is None:
        raise ValueError("A data do evento é obrigatória.")

    if sessao.get(TipoServico, dados.tipo_servico_id) is None:
        raise ValueError("Escolha um tipo de serviço válido.")

    if dados.endereco_id is not None:
        ids_validos = {endereco.id for endereco in cliente.enderecos}
        if dados.endereco_id not in ids_validos:
            raise ValueError("O endereço escolhido não pertence a este cliente.")


# --------------------------------------------------------------- indicadores
def resumo_por_tipo(
    sessao: Session, inicio: date, fim: date
) -> list[tuple[str, str, int]]:
    """(nome do tipo, estilo, quantidade) no intervalo, do maior para o menor."""
    consulta = (
        select(TipoServico.nome, TipoServico.estilo, func.count(Evento.id))
        .join(Evento, Evento.tipo_servico_id == TipoServico.id)
        .where(Evento.data.between(inicio, fim))
        .group_by(TipoServico.nome, TipoServico.estilo)
        .order_by(func.count(Evento.id).desc(), TipoServico.nome)
    )
    return [(nome, estilo, int(total)) for nome, estilo, total in sessao.execute(consulta)]


def resumo_por_status(
    sessao: Session, inicio: date, fim: date
) -> dict[StatusEvento, int]:
    consulta = (
        select(Evento.status, func.count(Evento.id))
        .where(Evento.data.between(inicio, fim))
        .group_by(Evento.status)
    )
    return {status: int(total) for status, total in sessao.execute(consulta)}


def resumo_por_cliente(
    sessao: Session, inicio: date, fim: date, limite: int = 8
) -> list[tuple[str, int]]:
    rotulo = func.coalesce(Cliente.apelido, Cliente.nome)
    consulta = (
        select(rotulo, func.count(Evento.id))
        .join(Evento, Evento.cliente_id == Cliente.id)
        .where(Evento.data.between(inicio, fim))
        .group_by(rotulo)
        .order_by(func.count(Evento.id).desc(), rotulo)
        .limit(limite)
    )
    return [(nome, int(total)) for nome, total in sessao.execute(consulta)]


def resumo_por_solicitante(
    sessao: Session, inicio: date, fim: date, limite: int = 8
) -> list[tuple[str, int]]:
    from app.models import Solicitante

    rotulo = func.concat(
        Solicitante.nome,
        func.coalesce(func.concat(" · ", Solicitante.setor), ""),
    )
    consulta = (
        select(rotulo, func.count(Evento.id))
        .join(Evento, Evento.solicitante_id == Solicitante.id)
        .where(Evento.data.between(inicio, fim))
        .group_by(rotulo)
        .order_by(func.count(Evento.id).desc(), rotulo)
        .limit(limite)
    )
    return [(nome, int(total)) for nome, total in sessao.execute(consulta)]


def contagem_por_dia(sessao: Session, inicio: date, fim: date) -> dict[date, int]:
    """Serviços por dia no intervalo — base das barras do painel."""
    consulta = (
        select(Evento.data, func.count(Evento.id))
        .where(Evento.data.between(inicio, fim))
        .group_by(Evento.data)
    )
    return {dia: int(total) for dia, total in sessao.execute(consulta)}
