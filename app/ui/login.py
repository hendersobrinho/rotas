"""Tela de entrada: login, senha e o 'continuar conectado' deste computador."""

from __future__ import annotations

from PySide6.QtCore import QEvent, Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFrame,
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
from app.ui import marca as marca_visual
from app.ui.estilo import CORES, FONTE_DADOS, FONTE_TITULO, marcar
from app.ui.mensagens import mostrar_erro
from app.ui.teclado import caps_lock_ligado, inferir_do_evento
from app.ui.widgets import rotulo


def painel_da_marca(largura: int = 340) -> QFrame:
    """O lado marinho das telas de entrada: logotipo, frase e a faixa."""
    painel = QFrame()
    painel.setObjectName("painelMarca")
    painel.setFixedWidth(largura)
    painel.setStyleSheet(
        f"QFrame#painelMarca {{ background: {CORES['marca']}; border: none; }}"
        "QFrame#painelMarca QLabel { background: transparent; }"
    )
    logotipo = QLabel()
    logotipo.setPixmap(marca_visual.pixmap(64, escuro=True, assinado=True))

    frase = QLabel("Do pedido à baixa,\ntoda rota no lugar.")
    frase.setStyleSheet(
        f'font-family: "{FONTE_TITULO}"; font-size: 22px; font-weight: 800;'
        "color: #FFFFFF;"
    )
    itens = QLabel(
        "".join(
            f'<p style="margin:0 0 8px 0;"><span style="color:{CORES["laranja"]};">●'
            f"</span>&nbsp;&nbsp;{texto}</p>"
            for texto in (
                "Agenda do motoboy, dia a dia",
                "Baixas conferidas num quadro só",
                "Lembrancinhas de fim de ano",
            )
        )
    )
    itens.setStyleSheet(f"color: {CORES['lateral_texto']}; font-size: 13px;")

    conteudo = QVBoxLayout()
    conteudo.setContentsMargins(34, 40, 34, 34)
    conteudo.setSpacing(0)
    conteudo.addWidget(logotipo)
    conteudo.addStretch(1)
    conteudo.addWidget(frase)
    conteudo.addSpacing(18)
    conteudo.addWidget(itens)

    coluna = QVBoxLayout(painel)
    coluna.setContentsMargins(0, 0, 0, 0)
    coluna.addLayout(conteudo, 1)
    return painel


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

        self.setWindowTitle("Rotas · Entrar")
        self.setFixedWidth(820)
        self.setStyleSheet(f"QDialog {{ background: {CORES['papel']}; }}")

        titulo = rotulo(
            "Primeiro acesso" if self.primeiro_acesso else "Bem-vindo de volta",
            "titulo",
        )
        subtitulo = rotulo(
            "Crie o usuário que vai administrar o sistema."
            if self.primeiro_acesso
            else "Entre para ver a agenda do motoboy.",
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

        # Fica sempre no layout, mudando só o texto: assim a janela não pula
        # de altura quando o aviso aparece.
        self.aviso_caps = QLabel()
        self.aviso_caps.setFixedHeight(18)
        self.aviso_caps.setStyleSheet(
            f"color: {CORES['carimbo']}; font-size: 11px; font-weight: 500;"
        )
        self._caps = False

        formulario = QWidget()
        layout = QVBoxLayout(formulario)
        layout.setContentsMargins(40, 40, 40, 28)
        layout.setSpacing(8)
        layout.addStretch(1)
        layout.addWidget(titulo)
        layout.addWidget(subtitulo)
        layout.addSpacing(18)

        if self.primeiro_acesso:
            layout.addWidget(rotulo("Nome", "campo"))
            layout.addWidget(self.campo_nome)
        layout.addWidget(rotulo("Login", "campo"))
        layout.addWidget(self.campo_login)
        layout.addWidget(rotulo("Senha", "campo"))
        layout.addWidget(self.campo_senha)
        layout.addWidget(self.aviso_caps)
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

        # O botão principal é âmbar, cheio na largura: é a única ação da tela.
        entrar = QPushButton("Criar usuário" if self.primeiro_acesso else "Entrar")
        marcar(entrar, variante="primario")
        entrar.setMinimumHeight(42)
        entrar.setCursor(Qt.CursorShape.PointingHandCursor)
        entrar.setStyleSheet("font-size: 14px;")
        entrar.setDefault(True)
        entrar.clicked.connect(self._entrar)
        layout.addWidget(entrar)
        layout.addStretch(1)

        sair = QPushButton("Fechar")
        marcar(sair, variante="fantasma")
        sair.clicked.connect(self.reject)
        conexao = QPushButton("Conexão com o banco...")
        marcar(conexao, variante="fantasma")
        conexao.setToolTip("Configurar onde fica o banco de dados")
        conexao.clicked.connect(self._configurar_conexao)

        rodape = QHBoxLayout()
        rodape.addWidget(conexao)
        rodape.addStretch(1)
        rodape.addWidget(sair)
        layout.addSpacing(12)
        layout.addLayout(rodape)

        lados = QHBoxLayout()
        lados.setContentsMargins(0, 0, 0, 0)
        lados.setSpacing(0)
        lados.addWidget(painel_da_marca(), 0)
        lados.addWidget(formulario, 1)
        # A faixa atravessa a janela inteira: no fundo marinho o pedaço
        # marinho dela sumiria.
        tudo = QVBoxLayout(self)
        tudo.setContentsMargins(0, 0, 0, 0)
        tudo.setSpacing(0)
        tudo.addLayout(lados, 1)
        tudo.addWidget(marca_visual.faixa(4))

        # As teclas vão para o campo, não para o diálogo: é preciso escutá-las lá.
        for campo in (self.campo_login, self.campo_senha, self.campo_confirmacao):
            campo.installEventFilter(self)

        self._relogio = QTimer(self)
        self._relogio.setInterval(400)
        self._relogio.timeout.connect(self._conferir_caps)
        self._relogio.start()
        self._conferir_caps()

        anterior = sessao_app.ler_token()
        if anterior and not self.primeiro_acesso:
            self.campo_login.setText(anterior[0])
            self.lembrar.setChecked(True)
        (self.campo_nome if self.primeiro_acesso else self.campo_login).setFocus()
        if self.campo_login.text():
            self.campo_senha.setFocus()

    def eventFilter(self, objeto, evento) -> bool:  # noqa: N802 (API do Qt)
        if evento.type() == QEvent.Type.KeyPress:
            self._conferir_caps(
                inferir_do_evento(
                    evento.text(),
                    bool(evento.modifiers() & Qt.KeyboardModifier.ShiftModifier),
                )
            )
        return super().eventFilter(objeto, evento)

    def _conferir_caps(self, deduzido: bool | None = None) -> None:
        """Pergunta ao teclado; se não der, usa o que a digitação deixou ver."""
        estado = caps_lock_ligado()
        if estado is None:
            estado = deduzido if deduzido is not None else self._caps
        self._caps = estado
        self.aviso_caps.setText("⇪  Caps Lock ligado" if estado else "")

    def _configurar_conexao(self) -> None:
        """Dá para arrumar o banco sem estar logado — é antes do login."""
        from app.ui.conexao_dialog import ConexaoDialog

        if ConexaoDialog(self).exec() != QDialog.DialogCode.Accepted:
            return
        try:
            with session_scope() as sessao:
                self.primeiro_acesso = not repo_usuarios.existe_algum(sessao)
        except Exception as erro:
            mostrar_erro(self, erro, "Ainda não deu para falar com o banco")
            return
        self._avisar("Conexão salva. Entre de novo.")

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
        self._conferir_caps(
            inferir_do_evento(
                evento.text(),
                bool(evento.modifiers() & Qt.KeyboardModifier.ShiftModifier),
            )
        )
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
