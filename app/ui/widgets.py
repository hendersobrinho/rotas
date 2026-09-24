"""Peças de interface reaproveitadas pelas telas."""

from __future__ import annotations

from enum import Enum
from typing import Any, Iterable, Type

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models import Endereco, TipoEndereco
from app.schemas import DadosEndereco
from app.ui.estilo import CORES, marcar


def combo_enum(
    enum_cls: Type[Enum],
    incluir_vazio: bool = False,
    texto_vazio: str = "Todos",
) -> QComboBox:
    """Combo com um item por membro do enum; o dado do item é o próprio membro."""
    combo = QComboBox()
    if incluir_vazio:
        combo.addItem(texto_vazio, None)
    for membro in enum_cls:
        combo.addItem(membro.value, membro)
    return combo


def selecionar_dado(combo: QComboBox, valor: Any) -> None:
    """Seleciona o item cujo `userData` é igual a `valor`."""
    indice = combo.findData(valor)
    combo.setCurrentIndex(indice if indice >= 0 else 0)


def rotulo(texto: str, papel: str = "apoio") -> QLabel:
    """Atalho para um QLabel já marcado com seu papel na folha de estilo."""
    etiqueta = QLabel(texto)
    marcar(etiqueta, papel=papel)
    return etiqueta


def linha_divisoria(horizontal: bool = True) -> QFrame:
    divisor = QFrame()
    if horizontal:
        divisor.setFixedHeight(1)
    else:
        divisor.setFixedWidth(1)
    marcar(divisor, separador=True)
    return divisor


def cartao(plano: bool = False) -> QFrame:
    """Container branco de cantos arredondados usado como bloco de conteúdo."""
    quadro = QFrame()
    marcar(quadro, cartao="plano" if plano else True)
    return quadro


class Etiqueta(QLabel):
    """Pastilha colorida para status e tipo de serviço."""

    def __init__(self, texto: str = "", parent: QWidget | None = None) -> None:
        super().__init__(texto, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.definir(texto, CORES["tinta_media"], CORES["cinza_claro"])

    def definir(self, texto: str, cor: str, fundo: str, riscado: bool = False) -> None:
        self.setText(texto)
        self.setStyleSheet(
            f"background: {fundo}; color: {cor}; border-radius: 6px;"
            "padding: 2px 8px; font-size: 11px; font-weight: 600;"
        )
        fonte = self.font()
        fonte.setStrikeOut(riscado)
        self.setFont(fonte)


class Segmentado(QFrame):
    """Alternativa aos combos para enums curtos: botões lado a lado."""

    mudou = Signal(object)

    def __init__(self, enum_cls: Type[Enum], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        marcar(self, grupo="segmentado")
        self._grupo = QButtonGroup(self)
        self._grupo.setExclusive(True)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(3)

        for indice, membro in enumerate(enum_cls):
            botao = QPushButton(membro.value)
            botao.setCheckable(True)
            botao.setCursor(Qt.CursorShape.PointingHandCursor)
            marcar(botao, variante="segmento")
            self._grupo.addButton(botao, indice)
            layout.addWidget(botao)

        self._botoes = {
            membro: self._grupo.button(indice)
            for indice, membro in enumerate(enum_cls)
        }
        self._grupo.idClicked.connect(self._ao_clicar)
        self._membros = list(enum_cls)
        self.definir_valor(self._membros[0])

    def _ao_clicar(self, indice: int) -> None:
        self.mudou.emit(self._membros[indice])

    def valor(self) -> Any:
        for membro, botao in self._botoes.items():
            if botao.isChecked():
                return membro
        return self._membros[0]

    def definir_valor(self, valor: Any) -> None:
        botao = self._botoes.get(valor)
        (botao or self._botoes[self._membros[0]]).setChecked(True)

    def somente_leitura(self, valor: bool) -> None:
        """Mostra a opção escolhida sem deixar trocar."""
        for botao in self._botoes.values():
            botao.setEnabled(not valor)


def configurar_tabela(
    tabela: QTableWidget,
    colunas: Iterable[str],
    coluna_elastica: int | None = None,
) -> None:
    """Prepara a tabela: só leitura, seleção por linha e colunas ajustadas."""
    colunas = [c.upper() for c in colunas]
    tabela.setColumnCount(len(colunas))
    tabela.setHorizontalHeaderLabels(colunas)
    tabela.verticalHeader().setVisible(False)
    tabela.verticalHeader().setDefaultSectionSize(34)
    tabela.setShowGrid(False)
    tabela.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    tabela.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    tabela.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    tabela.setFocusPolicy(Qt.FocusPolicy.NoFocus)

    cabecalho = tabela.horizontalHeader()
    cabecalho.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    cabecalho.setHighlightSections(False)
    if coluna_elastica is None:
        cabecalho.setStretchLastSection(True)
    else:
        cabecalho.setStretchLastSection(False)
        cabecalho.setSectionResizeMode(coluna_elastica, QHeaderView.ResizeMode.Stretch)


def preencher_linha(
    tabela: QTableWidget, linha: int, textos: Iterable[str], dado: Any = None
) -> None:
    """Escreve uma linha na tabela, guardando `dado` na primeira coluna."""
    for coluna, texto in enumerate(textos):
        item = QTableWidgetItem(texto)
        if coluna == 0 and dado is not None:
            item.setData(Qt.ItemDataRole.UserRole, dado)
        tabela.setItem(linha, coluna, item)


def dado_da_linha(tabela: QTableWidget, linha: int) -> Any:
    item = tabela.item(linha, 0)
    return None if item is None else item.data(Qt.ItemDataRole.UserRole)


class EnderecoForm(QFrame):
    """Bloco de campos de um endereço (residencial ou comercial)."""

    def __init__(self, tipo: TipoEndereco, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        marcar(self, cartao="plano")
        self.tipo = tipo

        self.logradouro = QLineEdit()
        self.numero = QLineEdit()
        self.numero.setMinimumWidth(90)
        self.numero.setMaximumWidth(120)
        self.complemento = QLineEdit()
        self.bairro = QLineEdit()
        self.cidade = QLineEdit()
        self.cep = QLineEdit()
        self.cep.setMinimumWidth(110)
        self.cep.setMaximumWidth(140)
        self.cep.setMaxLength(9)
        self.cep.setPlaceholderText("00000-000")
        self.observacao = QPlainTextEdit()
        self.observacao.setMaximumHeight(56)

        coluna = QVBoxLayout(self)
        coluna.setContentsMargins(16, 14, 16, 14)
        coluna.setSpacing(10)

        topo = QHBoxLayout()
        topo.addWidget(rotulo(f"Endereço {tipo.value.lower()}", "secao"))
        topo.addStretch(1)
        topo.addWidget(
            rotulo("em branco = o cliente não tem este endereço", "fraco")
        )
        coluna.addLayout(topo)

        grade = QGridLayout()
        grade.setHorizontalSpacing(12)
        grade.setVerticalSpacing(8)
        grade.addWidget(rotulo("Logradouro", "campo"), 0, 0)
        grade.addWidget(self.logradouro, 0, 1)
        grade.addWidget(rotulo("Número", "campo"), 0, 2)
        grade.addWidget(self.numero, 0, 3)
        grade.addWidget(rotulo("Complemento", "campo"), 1, 0)
        grade.addWidget(self.complemento, 1, 1)
        grade.addWidget(rotulo("Bairro", "campo"), 1, 2)
        grade.addWidget(self.bairro, 1, 3)
        grade.addWidget(rotulo("Cidade", "campo"), 2, 0)
        grade.addWidget(self.cidade, 2, 1)
        grade.addWidget(rotulo("CEP", "campo"), 2, 2)
        grade.addWidget(self.cep, 2, 3)
        grade.addWidget(rotulo("Observação", "campo"), 3, 0)
        grade.addWidget(self.observacao, 3, 1, 1, 3)
        grade.setColumnStretch(1, 3)
        grade.setColumnStretch(3, 1)
        coluna.addLayout(grade)

    def limpar(self) -> None:
        for campo in (
            self.logradouro,
            self.numero,
            self.complemento,
            self.bairro,
            self.cidade,
            self.cep,
        ):
            campo.clear()
        self.observacao.clear()

    def preencher(self, endereco: Endereco | None) -> None:
        self.limpar()
        if endereco is None:
            return
        self.logradouro.setText(endereco.logradouro or "")
        self.numero.setText(endereco.numero or "")
        self.complemento.setText(endereco.complemento or "")
        self.bairro.setText(endereco.bairro or "")
        self.cidade.setText(endereco.cidade or "")
        self.cep.setText(endereco.cep or "")
        self.observacao.setPlainText(endereco.observacao or "")

    def somente_leitura(self, valor: bool) -> None:
        for campo in (
            self.logradouro,
            self.numero,
            self.complemento,
            self.bairro,
            self.cidade,
            self.cep,
        ):
            campo.setReadOnly(valor)
        self.observacao.setReadOnly(valor)

    def dados(self) -> DadosEndereco:
        return DadosEndereco(
            tipo=self.tipo,
            logradouro=self.logradouro.text(),
            numero=self.numero.text(),
            complemento=self.complemento.text(),
            bairro=self.bairro.text(),
            cidade=self.cidade.text(),
            cep=self.cep.text(),
            observacao=self.observacao.toPlainText(),
        )
