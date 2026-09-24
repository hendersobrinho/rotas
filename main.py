"""Ponto de entrada do sistema de rotas do motoboy."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from app import sessao as sessao_app
from app.db import init_db, session_scope, url_mascarada
from app.repository import tipos_servico as repo_tipos
from app.ui.estilo import aplicar_tema
from app.ui.login import LoginDialog, entrar_pelo_token
from app.ui.main_window import MainWindow


def _carregar_env() -> None:
    """Carrega um arquivo .env, se python-dotenv estiver instalado."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def _preparar_banco() -> bool:
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
        return False
    return True


def _entrar() -> bool:
    """Entra pela sessão salva ou pela tela de login."""
    usuario = entrar_pelo_token()
    if usuario is None:
        dialogo = LoginDialog()
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return False
        usuario = dialogo.usuario
    sessao_app.definir_usuario(usuario)
    return True


def main() -> int:
    _carregar_env()

    app = QApplication(sys.argv)
    app.setApplicationName("Agenda do motoboy")
    app.setOrganizationName("Escritório de Contabilidade")
    aplicar_tema(app)

    if not _preparar_banco():
        return 1

    # Sair pelo botão volta para a tela de entrada em vez de fechar o programa.
    while _entrar():
        janela = MainWindow()
        janela.show()
        app.exec()
        if not janela.saiu_pelo_logout:
            return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
