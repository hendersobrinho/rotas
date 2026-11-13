"""Lembrancinhas de fim de ano: destinatários e a entrega de cada ano."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models import (
    AcaoLog,
    Cliente,
    DestinatarioLembrancinha,
    EntidadeLog,
    EntregaLembrancinha,
    SituacaoLembrancinha,
    TipoEndereco,
)
from app.repository import logs as repo_logs
from app.schemas import DadosDestinatario

# No registro de atividades, a lembrancinha entra como "Cliente" — o enum do
# banco não tem uma entidade própria, e criar uma exigiria alterar o tipo em
# todo banco já instalado. A descrição deixa claro do que se trata.
_ENTIDADE = EntidadeLog.CLIENTE
_PREFIXO = "Lembrancinha"


def listar(
    sessao: Session, termo: str | None = None, incluir_inativos: bool = True
) -> list[DestinatarioLembrancinha]:
    consulta = select(DestinatarioLembrancinha)
    if termo and termo.strip():
        padrao = f"%{termo.strip()}%"
        consulta = consulta.where(
            or_(
                DestinatarioLembrancinha.nome.ilike(padrao),
                DestinatarioLembrancinha.contato.ilike(padrao),
                DestinatarioLembrancinha.bairro.ilike(padrao),
                DestinatarioLembrancinha.cidade.ilike(padrao),
            )
        )
    if not incluir_inativos:
        consulta = consulta.where(DestinatarioLembrancinha.ativo.is_(True))
    consulta = consulta.order_by(func.lower(DestinatarioLembrancinha.nome))
    return list(sessao.scalars(consulta))


def obter(sessao: Session, destinatario_id: int) -> DestinatarioLembrancinha | None:
    return sessao.get(DestinatarioLembrancinha, destinatario_id)


def _validar(sessao: Session, dados: DadosDestinatario, ignorar_id: int | None = None) -> None:
    if not dados.nome:
        raise ValueError("Informe o nome de quem recebe a lembrancinha.")
    if dados.cliente_id is not None and sessao.get(Cliente, dados.cliente_id) is None:
        raise ValueError("O cliente ligado a este destinatário não existe mais.")
    repetido = sessao.scalar(
        select(DestinatarioLembrancinha.id).where(
            DestinatarioLembrancinha.nome == dados.nome,
            DestinatarioLembrancinha.id != (ignorar_id or 0),
        )
    )
    if repetido is not None:
        raise ValueError(f"“{dados.nome}” já está na lista de lembrancinhas.")


def _aplicar(destinatario: DestinatarioLembrancinha, dados: DadosDestinatario) -> None:
    for campo in DadosDestinatario.CAMPOS_DE_TEXTO:
        setattr(destinatario, campo, getattr(dados, campo))
    destinatario.cliente_id = dados.cliente_id
    destinatario.ativo = dados.ativo


def criar(sessao: Session, dados: DadosDestinatario) -> DestinatarioLembrancinha:
    dados = dados.normalizado()
    _validar(sessao, dados)
    destinatario = DestinatarioLembrancinha()
    _aplicar(destinatario, dados)
    sessao.add(destinatario)
    sessao.flush()
    repo_logs.registrar(
        sessao, AcaoLog.CRIACAO, _ENTIDADE,
        f"{_PREFIXO}: {destinatario.nome}", destinatario.id,
    )
    return destinatario


def atualizar(
    sessao: Session, destinatario_id: int, dados: DadosDestinatario
) -> DestinatarioLembrancinha:
    destinatario = obter(sessao, destinatario_id)
    if destinatario is None:
        raise ValueError("Este destinatário não existe mais.")
    dados = dados.normalizado()
    _validar(sessao, dados, ignorar_id=destinatario_id)
    _aplicar(destinatario, dados)
    sessao.flush()
    repo_logs.registrar(
        sessao, AcaoLog.ALTERACAO, _ENTIDADE,
        f"{_PREFIXO}: {destinatario.nome}", destinatario.id,
    )
    return destinatario


def excluir(sessao: Session, destinatario_id: int) -> None:
    destinatario = obter(sessao, destinatario_id)
    if destinatario is None:
        return
    nome = destinatario.nome
    sessao.delete(destinatario)
    sessao.flush()
    repo_logs.registrar(
        sessao, AcaoLog.EXCLUSAO, _ENTIDADE, f"{_PREFIXO}: {nome}", destinatario_id
    )


def definir_situacao(
    sessao: Session,
    destinatario_id: int,
    ano: int,
    situacao: SituacaoLembrancinha,
    entregue_em: date | None = None,
) -> EntregaLembrancinha | None:
    """Marca a situação do ano. Voltar para "a entregar" apaga a anotação."""
    destinatario = obter(sessao, destinatario_id)
    if destinatario is None:
        raise ValueError("Este destinatário não existe mais.")
    entrega = destinatario.entrega_do_ano(ano)

    if situacao is SituacaoLembrancinha.A_ENTREGAR:
        if entrega is not None:
            destinatario.entregas.remove(entrega)
            sessao.delete(entrega)
    else:
        if entrega is None:
            entrega = EntregaLembrancinha(ano=ano)
            destinatario.entregas.append(entrega)
        entrega.situacao = situacao.name
        entrega.entregue_em = (
            (entregue_em or date.today())
            if situacao is SituacaoLembrancinha.ENTREGUE
            else None
        )
    sessao.flush()
    repo_logs.registrar(
        sessao, AcaoLog.ALTERACAO, _ENTIDADE,
        f"{_PREFIXO} {ano}: {destinatario.nome} — {situacao.value}",
        destinatario.id,
    )
    return None if situacao is SituacaoLembrancinha.A_ENTREGAR else entrega


def resumo_do_ano(
    destinatarios: list[DestinatarioLembrancinha], ano: int
) -> dict[SituacaoLembrancinha, int]:
    """Quantos em cada situação, contando só os ativos."""
    contagem = {situacao: 0 for situacao in SituacaoLembrancinha}
    for destinatario in destinatarios:
        if destinatario.ativo:
            contagem[destinatario.situacao_no_ano(ano)] += 1
    return contagem


def dados_do_cliente(cliente: Cliente) -> DadosDestinatario:
    """Começa um destinatário a partir de um cliente da agenda.

    O endereço comercial tem preferência — é para lá que o presente vai.
    """
    endereco = (
        cliente.endereco_por_tipo(TipoEndereco.COMERCIAL)
        or (cliente.enderecos[0] if cliente.enderecos else None)
    )
    return DadosDestinatario(
        nome=cliente.nome,
        contato=cliente.apelido,
        telefone=cliente.telefone,
        logradouro=endereco.logradouro if endereco else None,
        numero=endereco.numero if endereco else None,
        complemento=endereco.complemento if endereco else None,
        bairro=endereco.bairro if endereco else None,
        cidade=endereco.cidade if endereco else None,
        cep=endereco.cep if endereco else None,
        cliente_id=cliente.id,
    )
