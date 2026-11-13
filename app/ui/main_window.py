"""Janela principal: barra lateral marinho com a marca e as telas do sistema."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app import __version__
from app import atualizacao
from app import sessao as sessao_app
from app.db import session_scope, url_mascarada
from app.repository import eventos as repo_eventos
from app.repository import usuarios as repo_usuarios
from app.ui import icones
from app.ui import marca as marca_visual
from app.ui.atualizacao import VerificadorDeAtualizacao
from app.ui.baixas_tab import BaixasTab
from app.ui.cadastros import CadastrosTab
from app.ui.clientes_tab import ClientesTab
from app.ui import estilo
from app.ui.estilo import CORES, FONTE_DADOS, FONTE_TITULO, marcar
from app.ui.eventos_tab import EventosTab
from app.ui.lembrancinhas_tab import LembrancinhasTab
from app.ui.login import esquecer_neste_computador
from app.ui.mensagens import confirmar
from app.ui.painel_tab import PainelTab
from app.ui.registro_tab import RegistroTab

def _iniciais(nome: str) -> str:
    partes = [p for p in nome.split() if p]
    if not partes:
        return "?"
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[-1][0]).upper()


class BotaoNavegacao(QPushButton):
    """Item da barra lateral, com ícone e, se preciso, um contador."""

    def __init__(self, texto: str, icone: str, parent: QWidget | None = None) -> None:
        super().__init__(texto, parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setIcon(icones.icone(icone, CORES["lateral_texto"], CORES["laranja"]))
        self.setIconSize(QSize(18, 18))
        marcar(self, nav=True)
        self.setMinimumHeight(40)

        self._contador = QLabel(self)
        self._contador.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._contador.setStyleSheet(
            f"background: {CORES['laranja']}; color: {CORES['sobre_laranja']};"
            f'border-radius: 9px; font-family: "{FONTE_DADOS}"; font-size: 10px;'
            "font-weight: 700; padding: 0 6px;"
        )
        self._contador.setFixedHeight(18)
        self._contador.hide()

    def definir_contador(self, valor: int) -> None:
        self._contador.setText(str(valor) if valor < 100 else "99+")
        self._contador.adjustSize()
        self._contador.setVisible(valor > 0)
        self._posicionar()

    def _posicionar(self) -> None:
        largura = max(18, self._contador.sizeHint().width())
        self._contador.setFixedWidth(largura)
        self._contador.move(
            self.width() - largura - 10, (self.height() - self._contador.height()) // 2
        )

    def resizeEvent(self, evento) -> None:  # noqa: N802
        super().resizeEvent(evento)
        self._posicionar()


class MainWindow(QMainWindow):
    # Posição de cada tela na pilha. As cinco primeiras mantêm os números de
    # antes, de quando eram abas; a ordem na barra lateral é outra.
    ABA_AGENDA = 0
    ABA_CLIENTES = 1
    ABA_PAINEL = 2
    ABA_CADASTROS = 3
    ABA_REGISTRO = 4
    ABA_BAIXAS = 5
    ABA_LEMBRANCINHAS = 6

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Rotas · Agenda do motoboy")
        self.setWindowIcon(marca_visual.icone())
        self.resize(1360, 880)
        self.setMinimumSize(1180, 720)

        self.aba_eventos = EventosTab()
        self.aba_clientes = ClientesTab()
        self.aba_painel = PainelTab()
        self.aba_cadastros = CadastrosTab()
        self.aba_registro = RegistroTab()
        self.aba_baixas = BaixasTab()
        self.aba_lembrancinhas = LembrancinhasTab()
        self.saiu_pelo_logout = False
        # Trocar de tema remonta a janela (ver main.py): as telas leem as cores
        # quando são montadas.
        self.trocou_tema = False

        # `abas` continua com esse nome: é uma pilha de telas, que a barra
        # lateral troca — e quem já chamava abas.setCurrentIndex segue igual.
        self.abas = QStackedWidget()
        for tela in (
            self.aba_eventos, self.aba_clientes, self.aba_painel,
            self.aba_cadastros, self.aba_registro, self.aba_baixas,
            self.aba_lembrancinhas,
        ):
            self.abas.addWidget(tela)
        self.abas.currentChanged.connect(self._ao_trocar_aba)

        self.atualizador = VerificadorDeAtualizacao(self)
        self.atualizador.encontrou.connect(self._mostrar_atualizacao)

        conteudo = QWidget()
        coluna = QVBoxLayout(conteudo)
        coluna.setContentsMargins(0, 0, 0, 0)
        coluna.setSpacing(0)
        coluna.addWidget(marca_visual.faixa(3))
        coluna.addWidget(self.abas, 1)

        central = QWidget()
        linha = QHBoxLayout(central)
        linha.setContentsMargins(0, 0, 0, 0)
        linha.setSpacing(0)
        linha.addWidget(self._barra_lateral())
        linha.addWidget(conteudo, 1)
        self.setCentralWidget(central)

        # Cada tela avisa as outras quando muda algo que elas exibem.
        self.aba_clientes.dados_alterados.connect(self.aba_eventos.recarregar_clientes)
        self.aba_clientes.dados_alterados.connect(self.aba_eventos.recarregar)
        self.aba_clientes.abrir_dia.connect(self._mostrar_dia)
        self.aba_eventos.dados_alterados.connect(self.aba_clientes.recarregar)
        self.aba_eventos.dados_alterados.connect(self._atualizar_contador_baixas)
        self.aba_eventos.abrir_baixas.connect(
            lambda: self.abas.setCurrentIndex(self.ABA_BAIXAS)
        )
        self.aba_baixas.dados_alterados.connect(self.aba_eventos.recarregar)
        self.aba_baixas.contagem_mudou.connect(self._definir_contador_baixas)
        self.aba_cadastros.dados_alterados.connect(self.aba_eventos.recarregar_clientes)
        self.aba_cadastros.dados_alterados.connect(self.aba_eventos.recarregar)
        self.aba_cadastros.dados_alterados.connect(self.aba_registro.recarregar_usuarios)

        usuario = sessao_app.usuario_atual()
        quem = f"{usuario.nome} ({usuario.login})" if usuario else "sem usuário"
        self.statusBar().showMessage(
            f"Rotas {__version__} · {quem} · {url_mascarada()}"
        )

        self.abas.setCurrentIndex(self.ABA_AGENDA)
        self._marcar_navegacao(self.ABA_AGENDA)
        self._atualizar_contador_baixas()

        # Contador da barra lateral em dia mesmo com a janela parada: o dia
        # vira, outro computador dá baixa.
        self._relogio = QTimer(self)
        self._relogio.setInterval(5 * 60 * 1000)
        self._relogio.timeout.connect(self._atualizar_contador_baixas)
        self._relogio.start()

        # Atualização: depois de a tela estar de pé, uma consulta discreta ao
        # GitHub (só no programa instalado; ver app/atualizacao.py).
        if atualizacao.verificacao_automatica_ligada():
            QTimer.singleShot(4000, self.atualizador.verificar)

    # ------------------------------------------------------- barra lateral
    def _barra_lateral(self) -> QFrame:
        barra = QFrame()
        barra.setObjectName("barraLateral")
        barra.setFixedWidth(236)

        self.logotipo = QLabel()
        self.logotipo.setPixmap(marca_visual.pixmap(38, escuro=True))
        self.logotipo.setContentsMargins(10, 0, 0, 0)

        self._grupo_nav = QButtonGroup(self)
        self._grupo_nav.setExclusive(True)
        self.navegacao: dict[int, BotaoNavegacao] = {}

        def item(texto: str, icone: str, indice: int) -> BotaoNavegacao:
            botao = BotaoNavegacao(texto, icone)
            botao.clicked.connect(lambda: self.abas.setCurrentIndex(indice))
            self._grupo_nav.addButton(botao)
            self.navegacao[indice] = botao
            return botao

        def secao(texto: str) -> QLabel:
            rotulo_secao = QLabel(texto)
            marcar(rotulo_secao, papel="lateral_secao")
            return rotulo_secao

        layout = QVBoxLayout(barra)
        layout.setContentsMargins(14, 22, 14, 16)
        layout.setSpacing(3)
        layout.addWidget(self.logotipo)
        layout.addSpacing(26)

        layout.addWidget(secao("ROTAS"))
        layout.addSpacing(4)
        layout.addWidget(item("Agenda", "agenda", self.ABA_AGENDA))
        layout.addWidget(item("Rota e baixas", "baixas", self.ABA_BAIXAS))
        layout.addWidget(item("Clientes", "clientes", self.ABA_CLIENTES))
        layout.addSpacing(14)
        layout.addWidget(secao("ESCRITÓRIO"))
        layout.addSpacing(4)
        layout.addWidget(item("Lembrancinhas", "lembrancinhas", self.ABA_LEMBRANCINHAS))
        layout.addWidget(item("Painel", "painel", self.ABA_PAINEL))
        layout.addWidget(item("Cadastros", "cadastros", self.ABA_CADASTROS))
        layout.addWidget(item("Registro", "registro", self.ABA_REGISTRO))
        layout.addStretch(1)

        # Aparece só quando o GitHub tem versão nova.
        self.btn_atualizacao = QPushButton("Atualização disponível")
        self.btn_atualizacao.setIcon(icones.icone("atualizar", CORES["sobre_laranja"]))
        self.btn_atualizacao.setIconSize(QSize(16, 16))
        self.btn_atualizacao.setCursor(Qt.CursorShape.PointingHandCursor)
        marcar(self.btn_atualizacao, variante="primario")
        self.btn_atualizacao.clicked.connect(self.atualizador.abrir)
        self.btn_atualizacao.hide()
        layout.addWidget(self.btn_atualizacao)
        layout.addSpacing(10)

        layout.addWidget(self._cartao_usuario())
        layout.addSpacing(8)

        rodape = QHBoxLayout()
        rodape.setSpacing(4)
        versao = QPushButton(f"v{__version__} · buscar atualização")
        versao.setToolTip("Ver no GitHub se há uma versão nova do Rotas")
        versao.setCursor(Qt.CursorShape.PointingHandCursor)
        versao.setStyleSheet(
            "QPushButton { background: transparent; border: none;"
            f" color: {CORES['lateral_fraco']};"
            f' font-family: "{FONTE_DADOS}"; font-size: 10px; text-align: left;'
            " padding: 2px 4px; }"
            "QPushButton:hover { color: #FFFFFF; }"
        )
        versao.clicked.connect(lambda: self.atualizador.verificar(manual=True))
        rodape.addWidget(versao, 1)

        noturno = estilo.escuro()
        self.btn_tema = QPushButton()
        self.btn_tema.setIcon(
            icones.icone("sol" if noturno else "lua", CORES["lateral_texto"], "#FFFFFF")
        )
        self.btn_tema.setIconSize(QSize(16, 16))
        self.btn_tema.setFixedSize(30, 26)
        self.btn_tema.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_tema.setToolTip(
            "Voltar para o tema claro" if noturno else "Usar o tema escuro"
        )
        self.btn_tema.setStyleSheet(
            "QPushButton { background: transparent;"
            f" border: 1px solid {CORES['lateral_borda']}; border-radius: 8px; }}"
            f"QPushButton:hover {{ background: {CORES['lateral_hover']}; }}"
        )
        self.btn_tema.clicked.connect(self.alternar_tema)
        rodape.addWidget(self.btn_tema)
        layout.addLayout(rodape)
        return barra

    def alternar_tema(self) -> None:
        """Claro ↔ escuro. Guarda a escolha e pede para a janela ser remontada."""
        novo = estilo.CLARO if estilo.escuro() else estilo.ESCURO
        estilo.salvar_tema(novo)
        self.trocou_tema = True
        self.close()

    def tela_atual(self) -> int:
        return self.abas.currentIndex()

    def ir_para(self, indice: int) -> None:
        self.abas.setCurrentIndex(indice)

    def _cartao_usuario(self) -> QFrame:
        usuario = sessao_app.usuario_atual()
        nome = usuario.nome if usuario else "—"

        cartao = QFrame()
        cartao.setObjectName("cartaoUsuario")
        cartao.setStyleSheet(
            "QFrame#cartaoUsuario { background: rgba(255, 255, 255, 0.06);"
            " border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; }"
        )
        avatar = QLabel(_iniciais(nome))
        avatar.setFixedSize(34, 34)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setStyleSheet(
            f"background: {CORES['laranja']}; color: {CORES['tinta']};"
            f'border-radius: 17px; font-family: "{FONTE_TITULO}"; font-size: 12px;'
            "font-weight: 800;"
        )
        nome_rotulo = QLabel(nome)
        marcar(nome_rotulo, papel="lateral_nome")
        login = QLabel(usuario.login if usuario else "")
        login.setStyleSheet("font-size: 11px;")

        textos = QVBoxLayout()
        textos.setSpacing(0)
        textos.addWidget(nome_rotulo)
        textos.addWidget(login)

        sair = QPushButton()
        sair.setIcon(icones.icone("sair", CORES["lateral_texto"], "#FFFFFF"))
        sair.setIconSize(QSize(18, 18))
        sair.setFixedSize(32, 32)
        sair.setToolTip("Sair e voltar para a tela de entrada")
        sair.setCursor(Qt.CursorShape.PointingHandCursor)
        sair.setStyleSheet(
            "QPushButton { background: transparent; border: none; border-radius: 8px; }"
            f"QPushButton:hover {{ background: {CORES['lateral_hover']}; }}"
        )
        sair.clicked.connect(self._sair)

        linha = QHBoxLayout(cartao)
        linha.setContentsMargins(10, 9, 6, 9)
        linha.setSpacing(10)
        linha.addWidget(avatar)
        linha.addLayout(textos, 1)
        linha.addWidget(sair)
        return cartao

    def _marcar_navegacao(self, indice: int) -> None:
        botao = self.navegacao.get(indice)
        if botao is not None:
            botao.setChecked(True)

    def _definir_contador_baixas(self, total: int) -> None:
        self.navegacao[self.ABA_BAIXAS].definir_contador(total)

    def _atualizar_contador_baixas(self) -> None:
        """Atrasados + não realizados sem remarcação: o que pede ação."""
        try:
            with session_scope() as sessao:
                total = repo_eventos.contar_sem_baixa(
                    sessao, date.today()
                ) + repo_eventos.contar_pendencias(sessao)
        except Exception:
            return
        self._definir_contador_baixas(total)

    def _mostrar_atualizacao(self, nova) -> None:
        self.btn_atualizacao.setText(f"Atualizar para {nova.versao}")
        self.btn_atualizacao.setToolTip("Há uma versão nova do Rotas no GitHub")
        self.btn_atualizacao.show()

    # -------------------------------------------------------------- telas
    def _ao_trocar_aba(self, indice: int) -> None:
        self._marcar_navegacao(indice)
        # Reler ao entrar na tela evita listas desatualizadas.
        if indice == self.ABA_CLIENTES:
            self.aba_clientes.recarregar()
        elif indice == self.ABA_AGENDA:
            self.aba_eventos.recarregar_clientes()
            self.aba_eventos.recarregar()
        elif indice == self.ABA_PAINEL:
            self.aba_painel.recarregar()
        elif indice == self.ABA_CADASTROS:
            self.aba_cadastros.recarregar()
        elif indice == self.ABA_REGISTRO:
            self.aba_registro.recarregar_usuarios()
            self.aba_registro.recarregar()
        elif indice == self.ABA_BAIXAS:
            self.aba_baixas.recarregar()
        elif indice == self.ABA_LEMBRANCINHAS:
            self.aba_lembrancinhas.recarregar()

    def _sair(self) -> None:
        if not confirmar(self, "Sair", "Sair do sistema e voltar para a tela de entrada?"):
            return
        usuario = sessao_app.usuario_atual()
        try:
            with session_scope() as sessao:
                registrado = (
                    repo_usuarios.obter(sessao, usuario.id) if usuario else None
                )
                repo_usuarios.registrar_saida(
                    sessao, registrado, usuario.nome if usuario else "Sistema"
                )
        except Exception:
            pass
        esquecer_neste_computador()
        sessao_app.definir_usuario(None)
        self.saiu_pelo_logout = True
        self.close()

    def _mostrar_dia(self, dia: date) -> None:
        self.abas.setCurrentIndex(self.ABA_AGENDA)
        self.aba_eventos.abrir_dia(dia)
