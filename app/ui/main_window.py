"""Janela principal com as abas do sistema."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QWidget,
)

from app import sessao as sessao_app

from app.db import session_scope, url_mascarada
from app.repository import usuarios as repo_usuarios
from app.ui.login import esquecer_neste_computador
from app.ui.cadastros import CadastrosTab
from app.ui import marca as marca_visual
from app.ui.clientes_tab import ClientesTab
from app.ui.eventos_tab import EventosTab
from app.ui.mensagens import confirmar
from app.ui.painel_tab import PainelTab
from app.ui.registro_tab import RegistroTab
from app.ui.estilo import marcar
from app.ui.widgets import rotulo


class MainWindow(QMainWindow):
    ABA_AGENDA = 0
    ABA_CLIENTES = 1
    ABA_PAINEL = 2
    ABA_CADASTROS = 3
    ABA_REGISTRO = 4

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Agenda do motoboy")
        self.setWindowIcon(marca_visual.icone())
        self.resize(1320, 880)
        self.setMinimumSize(1160, 720)

        self.aba_eventos = EventosTab()
        self.aba_clientes = ClientesTab()
        self.aba_painel = PainelTab()
        self.aba_cadastros = CadastrosTab()
        self.aba_registro = RegistroTab()
        self.saiu_pelo_logout = False

        self.abas = QTabWidget()
        self.abas.setDocumentMode(True)
        self.abas.addTab(self.aba_eventos, "Agenda")
        self.abas.addTab(self.aba_clientes, "Clientes")
        self.abas.addTab(self.aba_painel, "Painel")
        self.abas.addTab(self.aba_cadastros, "Cadastros")
        self.abas.addTab(self.aba_registro, "Registro")
        self.abas.setCornerWidget(self._canto_usuario())
        self.abas.setCornerWidget(self._canto_marca(), Qt.Corner.TopLeftCorner)
        self.abas.currentChanged.connect(self._ao_trocar_aba)
        central = QWidget()
        coluna = QVBoxLayout(central)
        coluna.setContentsMargins(0, 0, 0, 0)
        coluna.setSpacing(0)
        coluna.addWidget(self.abas)
        coluna.addWidget(marca_visual.faixa(3), 0)
        self.setCentralWidget(central)

        # Cada aba avisa as outras quando muda algo que elas exibem.
        self.aba_clientes.dados_alterados.connect(self.aba_eventos.recarregar_clientes)
        self.aba_clientes.dados_alterados.connect(self.aba_eventos.recarregar)
        self.aba_clientes.abrir_dia.connect(self._mostrar_dia)
        self.aba_eventos.dados_alterados.connect(self.aba_clientes.recarregar)
        self.aba_cadastros.dados_alterados.connect(self.aba_eventos.recarregar_clientes)
        self.aba_cadastros.dados_alterados.connect(self.aba_eventos.recarregar)
        self.aba_cadastros.dados_alterados.connect(self.aba_registro.recarregar_usuarios)

        usuario = sessao_app.usuario_atual()
        quem = f"{usuario.nome} ({usuario.login})" if usuario else "sem usuário"
        self.statusBar().showMessage(f"{quem} · {url_mascarada()}")

    def _ao_trocar_aba(self, indice: int) -> None:
        # Reler ao entrar na aba evita listas desatualizadas.
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

    def _canto_marca(self) -> QWidget:
        """O símbolo da casa, à esquerda das abas."""
        caixa = QWidget()
        linha = QHBoxLayout(caixa)
        linha.setContentsMargins(14, 2, 10, 2)
        simbolo = QLabel()
        simbolo.setPixmap(marca_visual.pixmap(20, simbolo=True))
        linha.addWidget(simbolo)
        return caixa

    def _canto_usuario(self) -> QWidget:
        """Quem está conectado e o botão de sair, no canto da barra de abas."""
        usuario = sessao_app.usuario_atual()
        caixa = QWidget()
        linha = QHBoxLayout(caixa)
        linha.setContentsMargins(0, 0, 8, 0)
        linha.setSpacing(8)
        linha.addWidget(rotulo(usuario.nome if usuario else "—", "apoio"))
        sair = QPushButton("Sair")
        marcar(sair, variante="fantasma")
        sair.clicked.connect(self._sair)
        linha.addWidget(sair)
        return caixa

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
