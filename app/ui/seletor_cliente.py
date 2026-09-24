"""Janela de escolha de cliente, com busca — no lugar da lista suspensa."""

from __future__ import annotations

import unicodedata

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from app.models import Cliente
from app.ui.estilo import CORES, marcar
from app.ui.widgets import (
    configurar_tabela,
    dado_da_linha,
    preencher_linha,
    rotulo,
)

COLUNAS = ("Cliente", "Tipo", "Telefone", "Cidade")


def sem_acento(texto: str) -> str:
    """'João' e 'joao' passam a casar na busca."""
    decomposto = unicodedata.normalize("NFD", texto or "")
    return "".join(c for c in decomposto if not unicodedata.combining(c)).casefold()


def _cidade(cliente: Cliente) -> str:
    for endereco in cliente.enderecos:
        if endereco.cidade:
            return endereco.cidade
    return "—"


class SeletorClienteDialog(QDialog):
    """Escolhe um cliente da lista, filtrando por nome ou apelido."""

    def __init__(
        self,
        parent: QWidget | None,
        clientes: list[Cliente],
        cliente_id: int | None = None,
    ) -> None:
        super().__init__(parent)
        self._clientes = clientes
        self.cliente_id: int | None = None

        self.setWindowTitle("Escolher cliente")
        self.setMinimumSize(560, 460)
        self.setStyleSheet(f"QDialog {{ background: {CORES['papel']}; }}")

        self.busca = QLineEdit()
        self.busca.setPlaceholderText("Digite parte do nome ou do apelido")
        self.busca.setClearButtonEnabled(True)
        self.busca.textChanged.connect(lambda _t: self._filtrar())
        self.busca.returnPressed.connect(self._escolher)

        self.tabela = QTableWidget()
        configurar_tabela(self.tabela, COLUNAS, coluna_elastica=0)
        self.tabela.doubleClicked.connect(lambda _i: self._escolher())
        self.tabela.itemSelectionChanged.connect(self._ao_selecionar)

        self.contador = rotulo("", "fraco")

        self.btn_escolher = QPushButton("Escolher")
        marcar(self.btn_escolher, variante="primario")
        self.btn_escolher.setDefault(True)
        self.btn_escolher.setEnabled(False)
        self.btn_escolher.clicked.connect(self._escolher)
        fechar = QPushButton("Descartar")
        fechar.clicked.connect(self.reject)

        rodape = QHBoxLayout()
        rodape.addWidget(self.contador)
        rodape.addStretch(1)
        rodape.addWidget(fechar)
        rodape.addWidget(self.btn_escolher)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(10)
        layout.addWidget(rotulo("Escolher cliente", "titulo"))
        layout.addWidget(
            rotulo("Clique duas vezes no cliente, ou escolha e confirme.", "fraco")
        )
        layout.addSpacing(6)
        layout.addWidget(self.busca)
        layout.addWidget(self.tabela, 1)
        layout.addLayout(rodape)

        self._filtrar(selecionar=cliente_id)
        self.busca.setFocus()

    # ----------------------------------------------------------------- dados
    def _filtrar(self, selecionar: int | None = None) -> None:
        termo = sem_acento(self.busca.text().strip())
        encontrados = [
            cliente
            for cliente in self._clientes
            if not termo
            or termo in sem_acento(cliente.nome)
            or termo in sem_acento(cliente.apelido or "")
        ]

        self.tabela.setRowCount(len(encontrados))
        for linha, cliente in enumerate(encontrados):
            preencher_linha(
                self.tabela,
                linha,
                (
                    cliente.nome_exibicao,
                    cliente.tipo.name,
                    cliente.telefone or "—",
                    _cidade(cliente),
                ),
                dado=cliente.id,
            )
            item = self.tabela.item(linha, 0)
            if item is not None and cliente.apelido and cliente.apelido != cliente.nome:
                item.setToolTip(cliente.nome)

        total = len(self._clientes)
        self.contador.setText(
            f"{len(encontrados)} de {total} cliente(s)"
            if len(encontrados) != total
            else f"{total} cliente(s)"
        )

        alvo = selecionar if selecionar is not None else None
        if alvo is not None:
            for linha in range(self.tabela.rowCount()):
                if dado_da_linha(self.tabela, linha) == alvo:
                    self.tabela.selectRow(linha)
                    return
        if self.tabela.rowCount():
            self.tabela.selectRow(0)

    def _ao_selecionar(self) -> None:
        self.btn_escolher.setEnabled(bool(self.tabela.selectionModel().selectedRows()))

    def _escolher(self) -> None:
        linhas = self.tabela.selectionModel().selectedRows()
        if not linhas:
            return
        escolhido = dado_da_linha(self.tabela, linhas[0].row())
        if escolhido is None:
            return
        self.cliente_id = int(escolhido)
        self.accept()

    def keyPressEvent(self, evento) -> None:  # noqa: N802
        # Setas navegam na lista mesmo com o foco na busca.
        if evento.key() in (Qt.Key.Key_Down, Qt.Key.Key_Up) and self.busca.hasFocus():
            self.tabela.setFocus()
            self.tabela.keyPressEvent(evento)
            return
        super().keyPressEvent(evento)
