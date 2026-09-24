"""Modelos SQLAlchemy: cliente, endereços e eventos de coleta/retirada."""

from __future__ import annotations

import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# O *nome* do membro (PF, PJ, ...) é o que vai para o banco; o *valor* é o
# rótulo mostrado na interface.
class TipoCliente(enum.Enum):
    PF = "Pessoa Física"
    PJ = "Pessoa Jurídica"


class TipoEndereco(enum.Enum):
    RESIDENCIAL = "Residencial"
    COMERCIAL = "Comercial"


class Periodo(enum.Enum):
    MANHA = "Manhã"
    TARDE = "Tarde"


class StatusEvento(enum.Enum):
    PENDENTE = "Pendente"
    CONCLUIDO = "Concluído"
    CANCELADO = "Cancelado"


class TipoServico(Base):
    """Tipo de serviço cadastrável: Coleta, Retirada, o que o escritório criar."""

    __tablename__ = "tipos_servico"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(60), nullable=False, unique=True)
    # Chave de uma cor da paleta (app/ui/estilo.py), não um código de cor:
    # assim o tema pode mudar sem precisar mexer nos dados.
    estilo: Mapped[str] = mapped_column(String(20), nullable=False, default="azul")
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    eventos: Mapped[list["Evento"]] = relationship(back_populates="tipo_servico")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<TipoServico id={self.id} nome={self.nome!r}>"


class Solicitante(Base):
    """Quem pede o serviço: uma pessoa do escritório, com o setor dela."""

    __tablename__ = "solicitantes"
    __table_args__ = (UniqueConstraint("nome", "setor", name="uq_solicitante_nome_setor"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(120), nullable=False)
    setor: Mapped[str | None] = mapped_column(String(80))
    ativo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    eventos: Mapped[list["Evento"]] = relationship(back_populates="solicitante")

    @property
    def nome_exibicao(self) -> str:
        return f"{self.nome} · {self.setor}" if self.setor else self.nome

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Solicitante id={self.id} nome={self.nome!r}>"


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[TipoCliente] = mapped_column(
        SAEnum(TipoCliente, name="tipo_cliente"), nullable=False
    )
    nome: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    apelido: Mapped[str | None] = mapped_column(String(120), index=True)
    telefone: Mapped[str | None] = mapped_column(String(40))
    observacao: Mapped[str | None] = mapped_column(Text)
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    enderecos: Mapped[list["Endereco"]] = relationship(
        back_populates="cliente",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="Endereco.tipo",
    )
    eventos: Mapped[list["Evento"]] = relationship(
        back_populates="cliente",
        cascade="all, delete-orphan",
        order_by="Evento.data.desc()",
    )

    @property
    def nome_exibicao(self) -> str:
        """Apelido quando existir, senão o nome/razão social."""
        return self.apelido or self.nome

    def endereco_por_tipo(self, tipo: TipoEndereco) -> "Endereco | None":
        for endereco in self.enderecos:
            if endereco.tipo is tipo:
                return endereco
        return None

    def __repr__(self) -> str:  # pragma: no cover - ajuda no debug
        return f"<Cliente id={self.id} nome={self.nome!r}>"


class Endereco(Base):
    __tablename__ = "enderecos"
    # Garante no máximo um endereço residencial e um comercial por cliente.
    __table_args__ = (
        UniqueConstraint("cliente_id", "tipo", name="uq_endereco_cliente_tipo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tipo: Mapped[TipoEndereco] = mapped_column(
        SAEnum(TipoEndereco, name="tipo_endereco"), nullable=False
    )
    logradouro: Mapped[str | None] = mapped_column(String(200))
    numero: Mapped[str | None] = mapped_column(String(20))
    complemento: Mapped[str | None] = mapped_column(String(100))
    bairro: Mapped[str | None] = mapped_column(String(100))
    cidade: Mapped[str | None] = mapped_column(String(100))
    cep: Mapped[str | None] = mapped_column(String(15))
    observacao: Mapped[str | None] = mapped_column(Text)

    cliente: Mapped[Cliente] = relationship(back_populates="enderecos")
    eventos: Mapped[list["Evento"]] = relationship(back_populates="endereco")

    def resumo(self) -> str:
        """Uma linha com o endereço, para listas e combos."""
        partes: list[str] = []
        if self.logradouro:
            partes.append(
                f"{self.logradouro}, {self.numero}" if self.numero else self.logradouro
            )
        for campo in (self.complemento, self.bairro, self.cidade):
            if campo:
                partes.append(campo)
        if self.cep:
            partes.append(f"CEP {self.cep}")
        return " - ".join(partes) or "(endereço sem dados)"

    def esta_vazio(self) -> bool:
        campos = (
            self.logradouro,
            self.numero,
            self.complemento,
            self.bairro,
            self.cidade,
            self.cep,
            self.observacao,
        )
        return not any(campo and campo.strip() for campo in campos)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Endereco id={self.id} tipo={self.tipo.name}>"


class Evento(Base):
    __tablename__ = "eventos"

    id: Mapped[int] = mapped_column(primary_key=True)
    cliente_id: Mapped[int] = mapped_column(
        ForeignKey("clientes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    endereco_id: Mapped[int | None] = mapped_column(
        ForeignKey("enderecos.id", ondelete="SET NULL"), index=True
    )
    tipo_servico_id: Mapped[int] = mapped_column(
        ForeignKey("tipos_servico.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    data: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    periodo: Mapped[Periodo] = mapped_column(
        SAEnum(Periodo, name="periodo"), nullable=False
    )
    solicitante_id: Mapped[int | None] = mapped_column(
        ForeignKey("solicitantes.id", ondelete="SET NULL"), index=True
    )
    status: Mapped[StatusEvento] = mapped_column(
        SAEnum(StatusEvento, name="status_evento"),
        nullable=False,
        default=StatusEvento.PENDENTE,
    )
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    atualizado_em: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    cliente: Mapped[Cliente] = relationship(back_populates="eventos", lazy="joined")
    endereco: Mapped[Endereco | None] = relationship(
        back_populates="eventos", lazy="joined"
    )
    tipo_servico: Mapped[TipoServico] = relationship(
        back_populates="eventos", lazy="joined"
    )
    solicitante: Mapped[Solicitante | None] = relationship(
        back_populates="eventos", lazy="joined"
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Evento id={self.id} data={self.data} status={self.status.name}>"
