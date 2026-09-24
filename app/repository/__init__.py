"""Camada de acesso a dados: só SQLAlchemy, nada de interface."""

from app.repository import (
    clientes,
    eventos,
    logs,
    recorrencias,
    solicitantes,
    tipos_servico,
    usuarios,
)

__all__ = [
    "clientes",
    "eventos",
    "logs",
    "recorrencias",
    "solicitantes",
    "tipos_servico",
    "usuarios",
]
