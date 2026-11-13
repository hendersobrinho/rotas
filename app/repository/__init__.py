"""Camada de acesso a dados: só SQLAlchemy, nada de interface."""

from app.repository import (
    clientes,
    eventos,
    lembrancinhas,
    logs,
    recorrencias,
    solicitantes,
    tipos_servico,
    usuarios,
)

__all__ = [
    "clientes",
    "eventos",
    "lembrancinhas",
    "logs",
    "recorrencias",
    "solicitantes",
    "tipos_servico",
    "usuarios",
]
