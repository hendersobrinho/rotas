"""Camada de acesso a dados: só SQLAlchemy, nada de interface."""

from app.repository import clientes, eventos

__all__ = ["clientes", "eventos"]
