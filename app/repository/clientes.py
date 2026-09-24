"""Operações de banco relacionadas a clientes e seus endereços."""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import AcaoLog, Cliente, Endereco, EntidadeLog, TipoEndereco
from app.repository import logs as repo_logs
from app.schemas import DadosCliente, DadosEndereco

_CAMPOS_ENDERECO = (
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
    _validar(dados)

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
    _validar(dados)

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


def _validar(dados: DadosCliente) -> None:
    if not dados.nome:
        raise ValueError("O nome (ou razão social) é obrigatório.")

    tipos = [endereco.tipo for endereco in dados.enderecos]
    if len(tipos) != len(set(tipos)):
        raise ValueError("Cada cliente aceita no máximo um endereço de cada tipo.")


def _aplicar_enderecos(cliente: Cliente, enderecos: list[DadosEndereco]) -> None:
    """Cria, atualiza ou remove os endereços informados.

    Um endereço com todos os campos em branco significa "não tenho este
    endereço" e, se já existir no banco, é removido.
    """
    for dados in enderecos:
        atual = cliente.endereco_por_tipo(dados.tipo)

        if dados.esta_vazio():
            if atual is not None:
                cliente.enderecos.remove(atual)  # delete-orphan apaga a linha
            continue

        if atual is None:
            atual = Endereco(tipo=dados.tipo)
            cliente.enderecos.append(atual)

        for campo in _CAMPOS_ENDERECO:
            setattr(atual, campo, getattr(dados, campo))


def endereco_do_cliente(
    sessao: Session, cliente_id: int, tipo: TipoEndereco
) -> Endereco | None:
    consulta = select(Endereco).where(
        Endereco.cliente_id == cliente_id, Endereco.tipo == tipo
    )
    return sessao.scalars(consulta).first()
