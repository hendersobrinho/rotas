"""Ponto de entrada do sistema de rotas do motoboy."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication, QDialog

from app import __version__
from app import erros
from app import sessao as sessao_app
from app.db import init_db, session_scope, url_mascarada
from app.repository import recorrencias as repo_recorrencias
from app.repository import tipos_servico as repo_tipos
from app.ui import marca as marca_visual
from app.ui.conexao_dialog import ConexaoDialog
from app.ui.estilo import aplicar_tema
from app.ui.login import LoginDialog, entrar_pelo_token
from app.ui.main_window import MainWindow


def _carregar_env() -> None:
    """Lê a configuração de conexão de onde ela estiver guardada."""
    from app import configuracao

    configuracao.carregar_env()


def _preparar_banco() -> bool:
    """Prepara o banco; se não conectar, abre a tela de conexão e tenta de novo."""
    while True:
        try:
            init_db()
            with session_scope() as sessao:
                repo_tipos.garantir_padrao(sessao)
            return True
        except Exception as erro:
            dialogo = ConexaoDialog(
                None,
                aviso=(
                    f"Não deu para falar com o banco em {url_mascarada()}.\n"
                    f"{str(getattr(erro, 'orig', erro)).splitlines()[0]}"
                ),
            )
            if dialogo.exec() != QDialog.DialogCode.Accepted:
                return False


def _entrar() -> bool:
    """Entra pela sessão salva ou pela tela de login."""
    usuario = entrar_pelo_token()
    if usuario is None:
        dialogo = LoginDialog()
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return False
        usuario = dialogo.usuario
    sessao_app.definir_usuario(usuario)
    _abrir_servicos_fixos()
    return True


def _abrir_servicos_fixos() -> None:
    """Os clientes fixos já entram na agenda assim que alguém abre o sistema."""
    try:
        with session_scope() as sessao:
            criados = repo_recorrencias.gerar(sessao)
        if criados:
            print(f"{len(criados)} serviço(s) fixo(s) abertos na agenda")
    except Exception as erro:  # não impede de usar o sistema
        print("não deu para abrir os serviços fixos:", erro)


def _executar() -> int:
    _carregar_env()

    app = QApplication(sys.argv)
    app.setApplicationName("Agenda do motoboy")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("Escritório de Contabilidade")
    # O ícone vale para toda janela do programa — inclusive o login e a tela de
    # conexão, que aparecem antes da principal. No Linux o nome do .desktop é o
    # que amarra a janela ao atalho, senão a barra de tarefas mostra um genérico.
    app.setWindowIcon(marca_visual.icone())
    app.setDesktopFileName("rotas")
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


def main() -> int:
    """Roda o programa; se algo escapar, o erro fica gravado em vez de sumir.

    Empacotado não há console: sem isto, uma falha antes da primeira janela
    aparece para quem usa como "o processo abre e não acontece nada".
    """
    erros.instalar()
    try:
        return _executar()
    except Exception as erro:
        erros.relatar(erro, "falha ao abrir o programa")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
