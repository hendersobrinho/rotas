"""Estruturas simples usadas para levar dados da interface até o repository.

A UI monta um destes objetos a partir dos campos do formulário; o repository
recebe apenas dados, sem saber que existe PySide6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.models import Periodo, StatusEvento, TipoCliente, TipoEndereco, TipoServico


def _limpar(texto: str | None) -> str | None:
    """Converte string vazia/espaços em None e remove sobras nas pontas."""
    if texto is None:
        return None
    texto = texto.strip()
    return texto or None


@dataclass
class DadosEndereco:
    tipo: TipoEndereco
    logradouro: str | None = None
    numero: str | None = None
    complemento: str | None = None
    bairro: str | None = None
    cidade: str | None = None
    cep: str | None = None
    observacao: str | None = None

    def normalizado(self) -> "DadosEndereco":
        return DadosEndereco(
            tipo=self.tipo,
            logradouro=_limpar(self.logradouro),
            numero=_limpar(self.numero),
            complemento=_limpar(self.complemento),
            bairro=_limpar(self.bairro),
            cidade=_limpar(self.cidade),
            cep=_limpar(self.cep),
            observacao=_limpar(self.observacao),
        )

    def esta_vazio(self) -> bool:
        dados = self.normalizado()
        return not any(
            (
                dados.logradouro,
                dados.numero,
                dados.complemento,
                dados.bairro,
                dados.cidade,
                dados.cep,
                dados.observacao,
            )
        )


@dataclass
class DadosCliente:
    tipo: TipoCliente
    nome: str
    apelido: str | None = None
    telefone: str | None = None
    observacao: str | None = None
    enderecos: list[DadosEndereco] = field(default_factory=list)

    def normalizado(self) -> "DadosCliente":
        return DadosCliente(
            tipo=self.tipo,
            nome=(self.nome or "").strip(),
            apelido=_limpar(self.apelido),
            telefone=_limpar(self.telefone),
            observacao=_limpar(self.observacao),
            enderecos=[e.normalizado() for e in self.enderecos],
        )


@dataclass
class DadosEvento:
    cliente_id: int
    tipo_servico: TipoServico
    data: date
    periodo: Periodo
    endereco_id: int | None = None
    solicitante: str | None = None
    status: StatusEvento = StatusEvento.PENDENTE

    def normalizado(self) -> "DadosEvento":
        return DadosEvento(
            cliente_id=self.cliente_id,
            tipo_servico=self.tipo_servico,
            data=self.data,
            periodo=self.periodo,
            endereco_id=self.endereco_id,
            solicitante=_limpar(self.solicitante),
            status=self.status,
        )


@dataclass
class FiltroEventos:
    """Filtros opcionais da listagem de eventos."""

    cliente_id: int | None = None
    status: StatusEvento | None = None
    tipo_servico: TipoServico | None = None
    data_inicio: date | None = None
    data_fim: date | None = None
    termo: str | None = None
