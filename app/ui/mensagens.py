"""Caixas de diálogo padronizadas (erros e confirmações)."""

from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWidget
from sqlalchemy.exc import IntegrityError, SQLAlchemyError


def mostrar_erro(parent: QWidget, erro: Exception, titulo: str = "Não foi possível") -> None:
    """Mostra um aviso para erro de regra e um erro técnico para falha de banco."""
    if isinstance(erro, ValueError):
        QMessageBox.warning(parent, titulo, str(erro))
    elif isinstance(erro, IntegrityError):
        QMessageBox.critical(
            parent,
            titulo,
            "O banco recusou a operação por violar uma restrição de integridade.\n\n"
            f"{getattr(erro, 'orig', erro)}",
        )
    elif isinstance(erro, SQLAlchemyError):
        QMessageBox.critical(parent, titulo, f"Erro de banco de dados:\n\n{erro}")
    else:
        QMessageBox.critical(parent, titulo, f"Erro inesperado:\n\n{erro!r}")


def confirmar(parent: QWidget, titulo: str, pergunta: str) -> bool:
    resposta = QMessageBox.question(
        parent,
        titulo,
        pergunta,
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    return resposta == QMessageBox.StandardButton.Yes
