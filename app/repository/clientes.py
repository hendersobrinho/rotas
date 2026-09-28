"""Operações de banco relacionadas a clientes e seus endereços."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import AcaoLog, Cliente, Endereco, EntidadeLog, TipoEndereco
from app.repository import logs as repo_logs
from app.schemas import DadosCliente, DadosEndereco

_CAMPOS_ENDERECO = (
    "tipo",
    "rotulo",
    "logradouro",
    "numero",
    "complemento",
    "bairro",
    "cidade",
    "cep",
    "observacao",
)


def listar_clientes(sessao: Session, termo: str | None = None) -> list[Cliente]:
    """Lista clientes ordenados pelo nome de exibição.

    Quando `termo` é informado, filtra por nome ou apelido (sem diferenciar
    maiúsculas/minúsculas).
    """
    consulta = select(Cliente)
    if termo and termo.strip():
        padrao = f"%{termo.strip()}%"
        consulta = consulta.where(
            or_(Cliente.nome.ilike(padrao), Cliente.apelido.ilike(padrao))
        )
    consulta = consulta.order_by(
        func.lower(func.coalesce(Cliente.apelido, Cliente.nome))
    )
    return list(sessao.scalars(consulta))


def obter_cliente(sessao: Session, cliente_id: int) -> Cliente | None:
    return sessao.get(Cliente, cliente_id)


def criar_cliente(sessao: Session, dados: DadosCliente) -> Cliente:
    dados = dados.normalizado()
    validar(dados)

    cliente = Cliente(
        tipo=dados.tipo,
        nome=dados.nome,
        apelido=dados.apelido,
        telefone=dados.telefone,
        observacao=dados.observacao,
    )
    sessao.add(cliente)
    _aplicar_enderecos(cliente, dados.enderecos)
    sessao.flush()
    repo_logs.registrar(
        sessao, AcaoLog.CRIACAO, EntidadeLog.CLIENTE,
        f"Cliente “{cliente.nome_exibicao}”", cliente.id,
    )
    return cliente


def atualizar_cliente(sessao: Session, cliente_id: int, dados: DadosCliente) -> Cliente:
    cliente = obter_cliente(sessao, cliente_id)
    if cliente is None:
        raise ValueError(f"Cliente {cliente_id} não encontrado.")

    dados = dados.normalizado()
    validar(dados)

    cliente.tipo = dados.tipo
    cliente.nome = dados.nome
    cliente.apelido = dados.apelido
    cliente.telefone = dados.telefone
    cliente.observacao = dados.observacao
    _aplicar_enderecos(cliente, dados.enderecos)
    sessao.flush()
    repo_logs.registrar(
        sessao, AcaoLog.ALTERACAO, EntidadeLog.CLIENTE,
        f"Cliente “{cliente.nome_exibicao}”", cliente.id,
    )
    return cliente


def excluir_cliente(sessao: Session, cliente_id: int) -> None:
    """Remove o cliente junto com seus endereços e eventos (cascade)."""
    cliente = obter_cliente(sessao, cliente_id)
    if cliente is None:
        raise ValueError(f"Cliente {cliente_id} não encontrado.")
    nome = cliente.nome_exibicao
    sessao.delete(cliente)
    sessao.flush()
    repo_logs.registrar(
        sessao, AcaoLog.EXCLUSAO, EntidadeLog.CLIENTE,
        f"Cliente “{nome}” e todo o histórico dele", cliente_id,
    )


def validar(dados: DadosCliente) -> None:
    """As regras do cadastro, antes de gravar.

    É pública porque a importação por planilha confere as mesmas regras na
    prévia, antes de gravar linha nenhuma (ver app/importacao_clientes.py).
    """
    if not dados.nome:
        raise ValueError("O nome (ou razão social) é obrigatório.")

    # Vários endereços do mesmo tipo são permitidos, mas com rótulos
    # diferentes — senão ninguém distingue um do outro na hora de marcar.
    rotulos: dict[TipoEndereco, set[str]] = {}
    for endereco in dados.enderecos:
        if endereco.esta_vazio():
            continue
        limpo = (endereco.rotulo or "").strip().casefold()
        usados = rotulos.setdefault(endereco.tipo, set())
        if limpo in usados:
            nome = (endereco.rotulo or "").strip() or endereco.tipo.value
            raise ValueError(
                f"Há dois endereços chamados “{nome}”. "
                "Dê um nome diferente para cada um."
            )
        usados.add(limpo)


def _aplicar_enderecos(cliente: Cliente, enderecos: list[DadosEndereco]) -> None:
    """Sincroniza a lista de endereços com o que a tela mandou.

    A tela manda a lista inteira: quem tem `id` já existe, quem não tem é
    novo, e quem ficou de fora (ou veio em branco) foi removido na tela e sai
    do banco — o `delete-orphan` apaga a linha.
    """
    existentes = {endereco.id: endereco for endereco in cliente.enderecos}
    mantidos: set[int] = set()

    for dados in enderecos:
        if dados.esta_vazio():
            continue

        atual = existentes.get(dados.id) if dados.id is not None else None
        if atual is None:
            atual = Endereco()
            cliente.enderecos.append(atual)
        else:
            mantidos.add(atual.id)

        for campo in _CAMPOS_ENDERECO:
            setattr(atual, campo, getattr(dados, campo))

    for identificador, endereco in existentes.items():
        if identificador not in mantidos:
            cliente.enderecos.remove(endereco)


def endereco_do_cliente(
    sessao: Session, cliente_id: int, tipo: TipoEndereco
) -> Endereco | None:
    consulta = select(Endereco).where(
        Endereco.cliente_id == cliente_id, Endereco.tipo == tipo
    )
    return sessao.scalars(consulta).first()
