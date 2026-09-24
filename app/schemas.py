"""Estruturas simples usadas para levar dados da interface até o repository.

A UI monta um destes objetos a partir dos campos do formulário; o repository
recebe apenas dados, sem saber que existe PySide6.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from app.models import Periodo, StatusEvento, TipoCliente, TipoEndereco


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
class DadosTipoServico:
    nome: str
    estilo: str = "azul"
    ativo: bool = True

    def normalizado(self) -> "DadosTipoServico":
        return DadosTipoServico(
            nome=(self.nome or "").strip(),
            estilo=(self.estilo or "azul").strip(),
            ativo=self.ativo,
        )


@dataclass
class DadosSolicitante:
    nome: str
    setor: str | None = None
    ativo: bool = True

    def normalizado(self) -> "DadosSolicitante":
        return DadosSolicitante(
            nome=(self.nome or "").strip(),
            setor=_limpar(self.setor),
            ativo=self.ativo,
        )


@dataclass
class DadosUsuario:
    nome: str
    login: str
    senha: str | None = None   # vazio ao editar = mantém a senha atual
    ativo: bool = True

    def normalizado(self) -> "DadosUsuario":
        return DadosUsuario(
            nome=(self.nome or "").strip(),
            login=(self.login or "").strip().lower(),
            senha=self.senha or None,
            ativo=self.ativo,
        )


@dataclass
class DadosEvento:
    cliente_id: int
    tipo_servico_id: int
    data: date
    periodo: Periodo
    endereco_id: int | None = None
    solicitante_id: int | None = None
    status: StatusEvento = StatusEvento.PENDENTE

    def normalizado(self) -> "DadosEvento":
        return DadosEvento(
            cliente_id=self.cliente_id,
            tipo_servico_id=self.tipo_servico_id,
            data=self.data,
            periodo=self.periodo,
            endereco_id=self.endereco_id,
            solicitante_id=self.solicitante_id,
            status=self.status,
        )


@dataclass
class FiltroEventos:
    """Filtros opcionais da listagem de eventos."""

    cliente_id: int | None = None
    status: StatusEvento | None = None
    tipo_servico_id: int | None = None
    solicitante_id: int | None = None
    data_inicio: date | None = None
    data_fim: date | None = None
