"""Vínculos entre pessoas e empresas (sócios, administradores...)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AcaoLog, Cliente, EntidadeLog, TipoCliente, VinculoSocio
from app.repository import logs as repo_logs

PAPEL_PADRAO = "Sócio"
PAPEIS_SUGERIDOS = (
    "Sócio",
    "Sócio-administrador",
    "Administrador",
    "Procurador",
    "Responsável",
)


def socios_da_empresa(sessao: Session, empresa_id: int) -> list[VinculoSocio]:
    consulta = select(VinculoSocio).where(VinculoSocio.empresa_id == empresa_id)
    vinculos = list(sessao.scalars(consulta).unique())
    return sorted(vinculos, key=lambda v: v.pessoa.nome_exibicao.casefold())


def empresas_da_pessoa(sessao: Session, pessoa_id: int) -> list[VinculoSocio]:
    consulta = select(VinculoSocio).where(VinculoSocio.pessoa_id == pessoa_id)
    vinculos = list(sessao.scalars(consulta).unique())
    return sorted(vinculos, key=lambda v: v.empresa.nome_exibicao.casefold())


def vinculos_do_cliente(sessao: Session, cliente_id: int) -> list[VinculoSocio]:
    """Todos os vínculos em que o cliente aparece, de um lado ou do outro."""
    return socios_da_empresa(sessao, cliente_id) + empresas_da_pessoa(sessao, cliente_id)


def contagem_por_cliente(sessao: Session) -> dict[int, int]:
    """Quantos vínculos cada cliente tem — para a lista de clientes."""
    contagem: dict[int, int] = {}
    for empresa_id, pessoa_id in sessao.execute(
        select(VinculoSocio.empresa_id, VinculoSocio.pessoa_id)
    ):
        contagem[empresa_id] = contagem.get(empresa_id, 0) + 1
        contagem[pessoa_id] = contagem.get(pessoa_id, 0) + 1
    return contagem


def vincular(
    sessao: Session, empresa_id: int, pessoa_id: int, papel: str | None = None
) -> VinculoSocio:
    """Liga a pessoa à empresa. A empresa tem de ser PJ; ninguém é sócio de si."""
    if empresa_id == pessoa_id:
        raise ValueError("Um cliente não pode ser sócio dele mesmo.")
    empresa = sessao.get(Cliente, empresa_id)
    pessoa = sessao.get(Cliente, pessoa_id)
    if empresa is None or pessoa is None:
        raise ValueError("Cliente não encontrado.")
    if empresa.tipo is not TipoCliente.PJ:
        raise ValueError(
            f"“{empresa.nome_exibicao}” é pessoa física — o vínculo é sempre"
            " com uma empresa (PJ)."
        )
    existente = sessao.scalar(
        select(VinculoSocio).where(
            VinculoSocio.empresa_id == empresa_id, VinculoSocio.pessoa_id == pessoa_id
        )
    )
    if existente is not None:
        raise ValueError(
            f"“{pessoa.nome_exibicao}” já está ligado a “{empresa.nome_exibicao}”."
        )
    vinculo = VinculoSocio(
        empresa_id=empresa_id,
        pessoa_id=pessoa_id,
        papel=_papel(papel),
    )
    sessao.add(vinculo)
    sessao.flush()
    repo_logs.registrar(
        sessao, AcaoLog.CRIACAO, EntidadeLog.CLIENTE,
        f"Vínculo: “{pessoa.nome_exibicao}” ({vinculo.papel}) em"
        f" “{empresa.nome_exibicao}”",
        empresa_id,
    )
    return vinculo


def alterar_papel(sessao: Session, vinculo_id: int, papel: str) -> VinculoSocio:
    vinculo = sessao.get(VinculoSocio, vinculo_id)
    if vinculo is None:
        raise ValueError("Vínculo não encontrado.")
    vinculo.papel = _papel(papel)
    sessao.flush()
    repo_logs.registrar(
        sessao, AcaoLog.ALTERACAO, EntidadeLog.CLIENTE,
        f"Vínculo: “{vinculo.pessoa.nome_exibicao}” agora {vinculo.papel} em"
        f" “{vinculo.empresa.nome_exibicao}”",
        vinculo.empresa_id,
    )
    return vinculo


def desvincular(sessao: Session, vinculo_id: int) -> None:
    vinculo = sessao.get(VinculoSocio, vinculo_id)
    if vinculo is None:
        return
    descricao = (
        f"Vínculo desfeito: “{vinculo.pessoa.nome_exibicao}” e"
        f" “{vinculo.empresa.nome_exibicao}”"
    )
    empresa_id = vinculo.empresa_id
    sessao.delete(vinculo)
    sessao.flush()
    repo_logs.registrar(
        sessao, AcaoLog.EXCLUSAO, EntidadeLog.CLIENTE, descricao, empresa_id
    )


def _papel(papel: str | None) -> str:
    texto = " ".join((papel or "").split())
    if not texto:
        return PAPEL_PADRAO
    # Papel é rótulo, não cadastro: guarda como foi escrito, só a primeira
    # letra maiúscula e com limite de tamanho.
    return (texto[0].upper() + texto[1:])[:60]


__all__ = [
    "PAPEIS_SUGERIDOS",
    "alterar_papel",
    "contagem_por_cliente",
    "desvincular",
    "empresas_da_pessoa",
    "socios_da_empresa",
    "vinculos_do_cliente",
    "vincular",
]
