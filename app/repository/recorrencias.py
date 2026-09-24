"""Serviços fixos: a regra de repetição e a abertura automática na agenda."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    AcaoLog,
    Cliente,
    EntidadeLog,
    Evento,
    FrequenciaRecorrencia,
    Recorrencia,
    StatusEvento,
    TipoServico,
)
from app.repository import logs as repo_logs
from app.schemas import DadosRecorrencia

DIAS_SEMANA_NOMES = (
    "segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
    "sexta-feira", "sábado", "domingo",
)
ORDINAIS = {1: "primeira", 2: "segunda", 3: "terceira", 4: "quarta", 5: "quinta",
            -1: "última"}
DIAS_PARA_FRENTE = 60

_CAMPOS = (
    "cliente_id",
    "endereco_id",
    "tipo_servico_id",
    "solicitante_id",
    "periodo",
    "frequencia",
    "dia_semana",
    "ordinal",
    "dia_mes",
    "apenas_util",
    "ativo",
)


# --------------------------------------------------------------- as datas
def _proximo_util(dia: date) -> date:
    """Sábado e domingo caem para a segunda seguinte."""
    while dia.weekday() >= 5:
        dia += timedelta(days=1)
    return dia


def _ordinal_do_mes(ano: int, mes: int, dia_semana: int, ordinal: int) -> date | None:
    """A N-ésima ocorrência de um dia da semana no mês (ordinal -1 = a última)."""
    ultimo = monthrange(ano, mes)[1]
    dias = [
        date(ano, mes, numero)
        for numero in range(1, ultimo + 1)
        if date(ano, mes, numero).weekday() == dia_semana
    ]
    if not dias:
        return None
    if ordinal == -1:
        return dias[-1]
    if 1 <= ordinal <= len(dias):
        return dias[ordinal - 1]
    return None  # pediram a 5ª e o mês só tem 4


def ocorrencias(regra: Recorrencia, inicio: date, fim: date) -> list[date]:
    """Todas as datas em que a regra cai, dentro do intervalo."""
    if inicio > fim:
        return []
    datas: list[date] = []

    if regra.frequencia is FrequenciaRecorrencia.SEMANAL:
        if regra.dia_semana is None:
            return []
        dia = inicio + timedelta(days=(regra.dia_semana - inicio.weekday()) % 7)
        while dia <= fim:
            datas.append(dia)
            dia += timedelta(days=7)
        return datas

    # As duas mensais caminham mês a mês.
    ano, mes = inicio.year, inicio.month
    while date(ano, mes, 1) <= fim:
        if regra.frequencia is FrequenciaRecorrencia.MENSAL_ORDINAL:
            if regra.dia_semana is not None and regra.ordinal is not None:
                dia = _ordinal_do_mes(ano, mes, regra.dia_semana, regra.ordinal)
            else:
                dia = None
        else:
            numero = min(regra.dia_mes or 1, monthrange(ano, mes)[1])
            dia = date(ano, mes, numero)
            if regra.apenas_util:
                dia = _proximo_util(dia)

        if dia is not None and inicio <= dia <= fim:
            datas.append(dia)
        mes += 1
        if mes > 12:
            ano, mes = ano + 1, 1
    return datas


def descrever(regra: Recorrencia) -> str:
    """A regra em português, do jeito que aparece na tela."""
    if regra.frequencia is FrequenciaRecorrencia.SEMANAL:
        dia = DIAS_SEMANA_NOMES[regra.dia_semana or 0]
        return f"Toda {dia}"
    if regra.frequencia is FrequenciaRecorrencia.MENSAL_ORDINAL:
        ordinal = ORDINAIS.get(regra.ordinal or 1, "primeira")
        dia = DIAS_SEMANA_NOMES[regra.dia_semana or 0]
        return f"Na {ordinal} {dia} do mês"
    complemento = " (pulando fim de semana)" if regra.apenas_util else ""
    return f"Todo dia {regra.dia_mes} do mês{complemento}"


# ------------------------------------------------------------------ CRUD
def listar(sessao: Session, cliente_id: int | None = None) -> list[Recorrencia]:
    consulta = select(Recorrencia)
    if cliente_id is not None:
        consulta = consulta.where(Recorrencia.cliente_id == cliente_id)
    return list(sessao.scalars(consulta.order_by(Recorrencia.id)).unique())


def obter(sessao: Session, recorrencia_id: int) -> Recorrencia | None:
    return sessao.get(Recorrencia, recorrencia_id)


def criar(sessao: Session, dados: DadosRecorrencia) -> Recorrencia:
    dados = dados.normalizado()
    _validar(sessao, dados)
    regra = Recorrencia(**{campo: getattr(dados, campo) for campo in _CAMPOS})
    sessao.add(regra)
    sessao.flush()
    repo_logs.registrar(
        sessao, AcaoLog.CRIACAO, EntidadeLog.EVENTO,
        f"Serviço fixo de {regra.cliente.nome_exibicao}: {descrever(regra)}",
        regra.id,
    )
    return regra


def atualizar(
    sessao: Session, recorrencia_id: int, dados: DadosRecorrencia
) -> Recorrencia:
    regra = obter(sessao, recorrencia_id)
    if regra is None:
        raise ValueError("Serviço fixo não encontrado.")
    dados = dados.normalizado()
    _validar(sessao, dados)
    for campo in _CAMPOS:
        setattr(regra, campo, getattr(dados, campo))
    sessao.flush()
    repo_logs.registrar(
        sessao, AcaoLog.ALTERACAO, EntidadeLog.EVENTO,
        f"Serviço fixo de {regra.cliente.nome_exibicao}: {descrever(regra)}",
        regra.id,
    )
    return regra


def excluir(sessao: Session, recorrencia_id: int) -> None:
    """Apagar a regra não apaga os serviços que ela já abriu."""
    regra = obter(sessao, recorrencia_id)
    if regra is None:
        raise ValueError("Serviço fixo não encontrado.")
    descricao = f"Serviço fixo de {regra.cliente.nome_exibicao}: {descrever(regra)}"
    sessao.delete(regra)
    sessao.flush()
    repo_logs.registrar(
        sessao, AcaoLog.EXCLUSAO, EntidadeLog.EVENTO, descricao, recorrencia_id
    )


# ------------------------------------------------------------- a geração
def gerar(
    sessao: Session,
    ate: date | None = None,
    a_partir_de: date | None = None,
    cliente_id: int | None = None,
) -> list[Evento]:
    """Abre na agenda os serviços fixos que ainda não existem.

    Nunca cria duas vezes a mesma data da mesma regra, e não mexe no que já
    está marcado — inclusive se alguém tiver cancelado ou remarcado.
    """
    inicio = a_partir_de or date.today()
    fim = ate or (inicio + timedelta(days=DIAS_PARA_FRENTE))

    consulta = select(Recorrencia).where(Recorrencia.ativo.is_(True))
    if cliente_id is not None:
        consulta = consulta.where(Recorrencia.cliente_id == cliente_id)
    regras = list(sessao.scalars(consulta.options(joinedload(Recorrencia.cliente))).unique())

    criados: list[Evento] = []
    ignoradas: list[Recorrencia] = []
    for regra in regras:
        # A geração não passa por criar_evento, então a régua do endereço
        # precisa valer aqui também: regra sem endereço fica parada.
        datas = ocorrencias(regra, inicio, fim)
        if regra.endereco_id is None:
            # Só vira aviso a regra que teria aberto algo na janela; do
            # contrário o registro ganharia uma linha igual a cada login.
            if datas:
                ignoradas.append(regra)
            continue
        if not datas:
            continue
        ja_existem = set(
            sessao.scalars(
                select(Evento.data).where(
                    Evento.recorrencia_id == regra.id, Evento.data.in_(datas)
                )
            )
        )
        for dia in datas:
            if dia in ja_existem:
                continue
            evento = Evento(
                cliente_id=regra.cliente_id,
                endereco_id=regra.endereco_id,
                tipo_servico_id=regra.tipo_servico_id,
                solicitante_id=regra.solicitante_id,
                data=dia,
                periodo=regra.periodo,
                status=StatusEvento.PENDENTE,
                recorrencia_id=regra.id,
            )
            sessao.add(evento)
            criados.append(evento)

    if criados:
        sessao.flush()
        repo_logs.registrar(
            sessao, AcaoLog.CRIACAO, EntidadeLog.EVENTO,
            f"{len(criados)} serviço(s) aberto(s) automaticamente até "
            f"{fim.strftime('%d/%m/%Y')}",
        )
    if ignoradas:
        repo_logs.registrar(
            sessao, AcaoLog.ALTERACAO, EntidadeLog.EVENTO,
            f"{len(ignoradas)} serviço(s) fixo(s) sem endereço não foram"
            " abertos: "
            + ", ".join(sorted({r.cliente.nome_exibicao for r in ignoradas})),
        )
    return criados


def listar_sem_endereco(sessao: Session) -> list[Recorrencia]:
    """Regras ligadas que perderam o endereço — não abrem nada até arrumar."""
    consulta = select(Recorrencia).where(
        Recorrencia.ativo.is_(True), Recorrencia.endereco_id.is_(None)
    )
    return list(sessao.scalars(consulta).unique())


def contar_gerados(sessao: Session, recorrencia_id: int) -> int:
    consulta = select(func.count(Evento.id)).where(
        Evento.recorrencia_id == recorrencia_id
    )
    return int(sessao.scalar(consulta) or 0)


def _validar(sessao: Session, dados: DadosRecorrencia) -> None:
    if sessao.get(Cliente, dados.cliente_id) is None:
        raise ValueError("Escolha um cliente válido.")
    if sessao.get(TipoServico, dados.tipo_servico_id) is None:
        raise ValueError("Escolha um tipo de serviço válido.")

    if dados.frequencia is FrequenciaRecorrencia.SEMANAL:
        if dados.dia_semana is None or not 0 <= dados.dia_semana <= 6:
            raise ValueError("Escolha o dia da semana.")
    elif dados.frequencia is FrequenciaRecorrencia.MENSAL_ORDINAL:
        if dados.dia_semana is None or not 0 <= dados.dia_semana <= 6:
            raise ValueError("Escolha o dia da semana.")
        if dados.ordinal not in ORDINAIS:
            raise ValueError("Escolha qual semana do mês.")
    else:
        if dados.dia_mes is None or not 1 <= dados.dia_mes <= 31:
            raise ValueError("O dia do mês precisa estar entre 1 e 31.")

    cliente = sessao.get(Cliente, dados.cliente_id)
    if dados.endereco_id is not None:
        if dados.endereco_id not in {e.id for e in cliente.enderecos}:
            raise ValueError("O endereço escolhido não pertence a este cliente.")
    elif dados.ativo:
        # Só a regra ligada precisa de endereço. Sem essa folga, uma regra que
        # perdeu o endereço não poderia nem ser desligada.
        if not cliente.enderecos:
            raise ValueError(
                f"“{cliente.nome_exibicao}” não tem endereço cadastrado.\n\n"
                "Cadastre o endereço, ou desmarque “abrir automaticamente”."
            )
        raise ValueError(
            "Escolha o endereço do serviço fixo, ou desmarque"
            " “abrir automaticamente”."
        )
