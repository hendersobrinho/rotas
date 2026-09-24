"""Ponto de entrada do sistema de rotas do motoboy."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

from app.db import init_db, session_scope, url_mascarada
from app.repository import tipos_servico as repo_tipos
from app.ui.estilo import aplicar_tema
from app.ui.main_window import MainWindow


def _carregar_env() -> None:
    """Carrega um arquivo .env, se python-dotenv estiver instalado."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def main() -> int:
    _carregar_env()

    app = QApplication(sys.argv)
    app.setApplicationName("Rotas do Motoboy")
    app.setOrganizationName("Escritório de Contabilidade")
    aplicar_tema(app)

    try:
        init_db()
        with session_scope() as sessao:
            repo_tipos.garantir_padrao(sessao)
    except Exception as erro:
        QMessageBox.critical(
            None,
            "Erro de conexão",
            "Não foi possível conectar ao PostgreSQL e preparar as tabelas.\n\n"
            f"URL: {url_mascarada()}\n\n{erro}",
        )
        return 1

    janela = MainWindow()
    janela.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
