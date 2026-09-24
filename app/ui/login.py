"""Tela de entrada: login, senha e o 'continuar conectado' deste computador."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app import sessao as sessao_app
from app.db import session_scope
from app.repository import usuarios as repo_usuarios
from app.schemas import DadosUsuario
from app.ui.estilo import CORES, FONTE_DADOS, marcar
from app.ui.mensagens import mostrar_erro
from app.ui.widgets import rotulo


class LoginDialog(QDialog):
    """Entra no sistema — ou cria o primeiro usuário, quando não há nenhum."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.usuario: sessao_app.UsuarioLogado | None = None

        try:
            with session_scope() as sessao:
                self.primeiro_acesso = not repo_usuarios.existe_algum(sessao)
        except Exception as erro:
            mostrar_erro(self, erro, "Erro ao falar com o banco")
            self.primeiro_acesso = False

        self.setWindowTitle("Agenda do motoboy")
        self.setMinimumWidth(420)
        self.setStyleSheet(f"QDialog {{ background: {CORES['papel']}; }}")

        marca = QLabel("Agenda do motoboy")
        marca.setStyleSheet(
            f"font-size: 22px; font-weight: 600; color: {CORES['tinta']};"
        )
        subtitulo = rotulo(
            "Crie o usuário que vai administrar o sistema."
            if self.primeiro_acesso
            else "Entre para ver a agenda.",
            "fraco",
        )

        self.campo_nome = QLineEdit()
        self.campo_nome.setPlaceholderText("Seu nome completo")
        self.campo_login = QLineEdit()
        self.campo_login.setPlaceholderText("nome.sobrenome")
        self.campo_senha = QLineEdit()
        self.campo_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_senha.setPlaceholderText("Senha")
        self.campo_confirmacao = QLineEdit()
        self.campo_confirmacao.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_confirmacao.setPlaceholderText("Repita a senha")
        self.lembrar = QCheckBox("Continuar conectado neste computador")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 26, 28, 22)
        layout.setSpacing(8)
        layout.addWidget(marca)
        layout.addWidget(subtitulo)
        layout.addSpacing(12)

        if self.primeiro_acesso:
            layout.addWidget(rotulo("Nome", "campo"))
            layout.addWidget(self.campo_nome)
        layout.addWidget(rotulo("Login", "campo"))
        layout.addWidget(self.campo_login)
        layout.addWidget(rotulo("Senha", "campo"))
        layout.addWidget(self.campo_senha)
        if self.primeiro_acesso:
            layout.addWidget(rotulo("Confirmação", "campo"))
            layout.addWidget(self.campo_confirmacao)
        else:
            layout.addSpacing(6)
            layout.addWidget(self.lembrar)
            layout.addWidget(
                rotulo(
                    "Fica guardado só nesta máquina, e por 30 dias.", "fraco"
                )
            )

        self.aviso = QLabel()
        self.aviso.setWordWrap(True)
        self.aviso.setStyleSheet(
            f'color: {CORES["vermelho"]}; font-family: "{FONTE_DADOS}";'
            "font-size: 11px;"
        )
        self.aviso.setVisible(False)
        layout.addSpacing(6)
        layout.addWidget(self.aviso)
        layout.addSpacing(8)

        entrar = QPushButton("Criar usuário" if self.primeiro_acesso else "Entrar")
        marcar(entrar, variante="primario")
        entrar.setDefault(True)
        entrar.clicked.connect(self._entrar)
        sair = QPushButton("Fechar")
        sair.clicked.connect(self.reject)

        rodape = QHBoxLayout()
        rodape.addStretch(1)
        rodape.addWidget(sair)
        rodape.addWidget(entrar)
        layout.addLayout(rodape)

        anterior = sessao_app.ler_token()
        if anterior and not self.primeiro_acesso:
            self.campo_login.setText(anterior[0])
            self.lembrar.setChecked(True)
        (self.campo_nome if self.primeiro_acesso else self.campo_login).setFocus()
        if self.campo_login.text():
            self.campo_senha.setFocus()

    def _avisar(self, texto: str) -> None:
        self.aviso.setText(texto)
        self.aviso.setVisible(True)

    def _entrar(self) -> None:
        self.aviso.setVisible(False)
        try:
            with session_scope() as sessao:
                if self.primeiro_acesso:
                    if self.campo_senha.text() != self.campo_confirmacao.text():
                        raise ValueError("As duas senhas não são iguais.")
                    usuario = repo_usuarios.criar(
                        sessao,
                        DadosUsuario(
                            nome=self.campo_nome.text(),
                            login=self.campo_login.text(),
                            senha=self.campo_senha.text(),
                        ),
                    )
                    usuario = repo_usuarios.autenticar(
                        sessao, usuario.login, self.campo_senha.text()
                    )
                else:
                    usuario = repo_usuarios.autenticar(
                        sessao, self.campo_login.text(), self.campo_senha.text()
                    )

                lembrar = self.lembrar.isChecked() and not self.primeiro_acesso
                if lembrar:
                    token = repo_usuarios.criar_sessao_salva(
                        sessao, usuario, sessao_app.nome_da_maquina()
                    )
                else:
                    token = None
                self.usuario = sessao_app.UsuarioLogado(
                    id=usuario.id, nome=usuario.nome, login=usuario.login
                )
        except ValueError as erro:
            self._avisar(str(erro))
            self.campo_senha.clear()
            self.campo_senha.setFocus()
            return
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para entrar")
            return

        if token:
            sessao_app.salvar_token(self.usuario.login, token)
        else:
            sessao_app.limpar_token()
        self.accept()

    def keyPressEvent(self, evento) -> None:  # noqa: N802
        if evento.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._entrar()
            return
        super().keyPressEvent(evento)


def entrar_pelo_token() -> sessao_app.UsuarioLogado | None:
    """Tenta entrar com o 'continuar conectado' guardado neste computador."""
    guardado = sessao_app.ler_token()
    if guardado is None:
        return None
    _login, token = guardado
    try:
        with session_scope() as sessao:
            repo_usuarios.limpar_sessoes_expiradas(sessao)
            usuario = repo_usuarios.usuario_do_token(sessao, token)
            if usuario is None:
                return None
            from app.models import AcaoLog, EntidadeLog
            from app.repository import logs as repo_logs

            repo_logs.registrar(
                sessao, AcaoLog.LOGIN, EntidadeLog.SISTEMA,
                "Entrou por sessão salva neste computador",
                usuario_id=usuario.id, usuario_nome=usuario.nome,
            )
            return sessao_app.UsuarioLogado(
                id=usuario.id, nome=usuario.nome, login=usuario.login
            )
    except Exception:
        # Banco fora do ar ou token estragado: cai na tela de login normal.
        return None


def esquecer_neste_computador() -> None:
    """Apaga o token daqui e do banco."""
    guardado = sessao_app.ler_token()
    if guardado is not None:
        try:
            with session_scope() as sessao:
                repo_usuarios.encerrar_sessao_salva(sessao, guardado[1])
        except Exception:
            pass
    sessao_app.limpar_token()
