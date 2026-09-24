"""Vocabulário de datas em português e agrupamento de serviços por período."""

from __future__ import annotations

import enum
from datetime import date, timedelta
from typing import Iterable, Sequence

from app.models import Evento

MESES = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)
DIAS_SEMANA = ("dom", "seg", "ter", "qua", "qui", "sex", "sáb")
DIAS_POR_EXTENSO = (
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
)


def data_por_extenso(dia: date) -> str:
    """Ex.: 'quarta-feira, 23 de setembro de 2026'."""
    return (
        f"{DIAS_POR_EXTENSO[dia.weekday()]}, {dia.day} de "
        f"{MESES[dia.month - 1]} de {dia.year}"
    )


def titulo_mes(mes: date) -> str:
    return f"{MESES[mes.month - 1].capitalize()} de {mes.year}"


def inicio_da_semana(dia: date) -> date:
    """Domingo da semana do dia — a semana aqui começa no domingo."""
    return dia - timedelta(days=(dia.weekday() + 1) % 7)


class Agrupamento(enum.Enum):
    """Como o histórico do cliente é dividido na tela."""

    SEMANA = "Semana"
    MES = "Mês"
    ANO = "Ano"


def inicio_do_periodo(dia: date, modo: Agrupamento) -> date:
    """Primeiro dia do período a que o dia pertence — é a chave do grupo."""
    if modo is Agrupamento.SEMANA:
        return inicio_da_semana(dia)
    if modo is Agrupamento.MES:
        return dia.replace(day=1)
    return dia.replace(month=1, day=1)


def rotulo_do_periodo(inicio: date, modo: Agrupamento) -> str:
    if modo is Agrupamento.ANO:
        return str(inicio.year)
    if modo is Agrupamento.MES:
        return titulo_mes(inicio)

    fim = inicio + timedelta(days=6)
    if inicio.month == fim.month:
        return f"{inicio.day} a {fim.day} de {MESES[fim.month - 1]} de {fim.year}"
    if inicio.year == fim.year:
        return (
            f"{inicio.day} de {MESES[inicio.month - 1]} a "
            f"{fim.day} de {MESES[fim.month - 1]} de {fim.year}"
        )
    return (
        f"{inicio.day}/{inicio.month}/{inicio.year} a "
        f"{fim.day}/{fim.month}/{fim.year}"
    )


def agrupar(
    eventos: Iterable[Evento], modo: Agrupamento
) -> list[tuple[str, Sequence[Evento]]]:
    """Divide os serviços em períodos, mantendo a ordem em que chegaram.

    O histórico já vem do mais recente para o mais antigo, então os grupos
    saem na mesma ordem.
    """
    grupos: dict[date, list[Evento]] = {}
    for evento in eventos:
        grupos.setdefault(inicio_do_periodo(evento.data, modo), []).append(evento)
    return [
        (rotulo_do_periodo(inicio, modo), lista) for inicio, lista in grupos.items()
    ]
