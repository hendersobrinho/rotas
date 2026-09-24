"""Camada de acesso a dados: só SQLAlchemy, nada de interface."""

from app.repository import clientes, eventos, solicitantes, tipos_servico

__all__ = ["clientes", "eventos", "solicitantes", "tipos_servico"]
