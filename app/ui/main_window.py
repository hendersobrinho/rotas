"""Janela principal com as abas de Clientes e Serviços."""

from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import QMainWindow, QTabWidget, QWidget

from app.db import url_mascarada
from app.ui.clientes_tab import ClientesTab
from app.ui.eventos_tab import EventosTab


class MainWindow(QMainWindow):
    ABA_CLIENTES = 0
    ABA_EVENTOS = 1

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Agenda do motoboy")
        self.resize(1280, 860)
        self.setMinimumSize(1160, 720)

        self.aba_clientes = ClientesTab()
        self.aba_eventos = EventosTab()

        self.abas = QTabWidget()
        self.abas.setDocumentMode(True)
        self.abas.addTab(self.aba_clientes, "Clientes")
        self.abas.addTab(self.aba_eventos, "Agenda")
        self.abas.setCurrentIndex(self.ABA_EVENTOS)
        self.abas.currentChanged.connect(self._ao_trocar_aba)
        self.setCentralWidget(self.abas)

        # Cada aba avisa a outra quando muda algo que a outra exibe.
        self.aba_clientes.dados_alterados.connect(self.aba_eventos.recarregar_clientes)
        self.aba_clientes.dados_alterados.connect(self.aba_eventos.recarregar)
        self.aba_clientes.abrir_dia.connect(self._mostrar_dia)
        self.aba_eventos.dados_alterados.connect(self.aba_clientes.recarregar)

        self.statusBar().showMessage(f"Conectado em {url_mascarada()}")

    def _ao_trocar_aba(self, indice: int) -> None:
        # Reler ao entrar na aba evita listas desatualizadas.
        if indice == self.ABA_CLIENTES:
            self.aba_clientes.recarregar()
        elif indice == self.ABA_EVENTOS:
            self.aba_eventos.recarregar_clientes()
            self.aba_eventos.recarregar()

    def _mostrar_dia(self, dia: date) -> None:
        self.abas.setCurrentIndex(self.ABA_EVENTOS)
        self.aba_eventos.abrir_dia(dia)
