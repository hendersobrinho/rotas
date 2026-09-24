"""Janela principal com as abas do sistema."""

from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import QMainWindow, QTabWidget, QWidget

from app.db import url_mascarada
from app.ui.cadastros import CadastrosTab
from app.ui.clientes_tab import ClientesTab
from app.ui.eventos_tab import EventosTab
from app.ui.painel_tab import PainelTab


class MainWindow(QMainWindow):
    ABA_AGENDA = 0
    ABA_CLIENTES = 1
    ABA_PAINEL = 2
    ABA_CADASTROS = 3

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Agenda do motoboy")
        self.resize(1320, 880)
        self.setMinimumSize(1160, 720)

        self.aba_eventos = EventosTab()
        self.aba_clientes = ClientesTab()
        self.aba_painel = PainelTab()
        self.aba_cadastros = CadastrosTab()

        self.abas = QTabWidget()
        self.abas.setDocumentMode(True)
        self.abas.addTab(self.aba_eventos, "Agenda")
        self.abas.addTab(self.aba_clientes, "Clientes")
        self.abas.addTab(self.aba_painel, "Painel")
        self.abas.addTab(self.aba_cadastros, "Cadastros")
        self.abas.currentChanged.connect(self._ao_trocar_aba)
        self.setCentralWidget(self.abas)

        # Cada aba avisa as outras quando muda algo que elas exibem.
        self.aba_clientes.dados_alterados.connect(self.aba_eventos.recarregar_clientes)
        self.aba_clientes.dados_alterados.connect(self.aba_eventos.recarregar)
        self.aba_clientes.abrir_dia.connect(self._mostrar_dia)
        self.aba_eventos.dados_alterados.connect(self.aba_clientes.recarregar)
        self.aba_cadastros.dados_alterados.connect(self.aba_eventos.recarregar_clientes)
        self.aba_cadastros.dados_alterados.connect(self.aba_eventos.recarregar)

        self.statusBar().showMessage(f"Conectado em {url_mascarada()}")

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

    def _mostrar_dia(self, dia: date) -> None:
        self.abas.setCurrentIndex(self.ABA_AGENDA)
        self.aba_eventos.abrir_dia(dia)
