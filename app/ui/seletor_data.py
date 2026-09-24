"""Mini calendário para escolher um dia — ou a semana inteira de uma vez."""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.ui.datas import (
    DIAS_SEMANA,
    inicio_da_semana,
    primeiro_dia_da_grade,
    titulo_mes,
)
from app.ui.estilo import CORES, FONTE_DADOS, marcar

LINHAS = 6


class _Celula(QLabel):
    """Um dia do mini calendário."""

    clicada = Signal(date)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setFixedHeight(30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dia: date | None = None

    def definir(
        self,
        dia: date,
        do_mes: bool,
        hoje: bool,
        escolhido: bool,
        ponta_esquerda: bool,
        ponta_direita: bool,
    ) -> None:
        self._dia = dia
        self.setText(str(dia.day))

        if escolhido:
            fundo, cor, peso = CORES["azul"], "#FFFFFF", 600
        elif not do_mes:
            fundo, cor, peso = "transparent", CORES["tinta_fraca"], 400
        else:
            fundo, cor, peso = "transparent", CORES["tinta"], 500

        esquerda = "9px" if ponta_esquerda else "0px"
        direita = "9px" if ponta_direita else "0px"
        contorno = (
            f"border: 1px solid {CORES['tinta']};"
            if hoje and not escolhido
            else "border: 1px solid transparent;"
        )
        self.setStyleSheet(
            f'_Celula {{ background: {fundo}; color: {cor};'
            f' font-family: "{FONTE_DADOS}"; font-size: 12px; font-weight: {peso};'
            f" border-top-left-radius: {esquerda};"
            f" border-bottom-left-radius: {esquerda};"
            f" border-top-right-radius: {direita};"
            f" border-bottom-right-radius: {direita}; {contorno} }}"
        )

    def mouseReleaseEvent(self, evento) -> None:  # noqa: N802
        super().mouseReleaseEvent(evento)
        if self._dia is not None and evento.button() == Qt.MouseButton.LeftButton:
            self.clicada.emit(self._dia)


class SeletorDeData(QWidget):
    """Grade do mês; no modo semana, a linha inteira acende."""

    escolhida = Signal(date)

    def __init__(self, parent: QWidget | None = None, por_semana: bool = False) -> None:
        super().__init__(parent)
        self._data = date.today()
        self._mes = self._data.replace(day=1)
        self._por_semana = por_semana

        self._titulo = QLabel()
        self._titulo.setStyleSheet(
            f"font-size: 14px; font-weight: 600; color: {CORES['tinta']};"
        )
        anterior = QPushButton("‹")
        proximo = QPushButton("›")
        for botao in (anterior, proximo):
            botao.setFixedWidth(30)
            marcar(botao, variante="fantasma")
            botao.setStyleSheet("font-size: 16px;")
        anterior.clicked.connect(lambda: self._andar(-1))
        proximo.clicked.connect(lambda: self._andar(1))
        hoje = QPushButton("Hoje")
        hoje.clicked.connect(lambda: self.definir_data(date.today()))

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(4)
        cabecalho.addWidget(self._titulo)
        cabecalho.addStretch(1)
        cabecalho.addWidget(anterior)
        cabecalho.addWidget(proximo)
        cabecalho.addWidget(hoje)

        moldura = QFrame()
        marcar(moldura, cartao="plano")
        interno = QVBoxLayout(moldura)
        interno.setContentsMargins(8, 8, 8, 8)
        interno.setSpacing(4)

        faixa = QHBoxLayout()
        faixa.setSpacing(0)
        for nome in DIAS_SEMANA:
            etiqueta = QLabel(nome.upper())
            etiqueta.setAlignment(Qt.AlignmentFlag.AlignCenter)
            marcar(etiqueta, papel="etiqueta")
            faixa.addWidget(etiqueta, 1)
        interno.addLayout(faixa)

        grade = QGridLayout()
        grade.setContentsMargins(0, 0, 0, 0)
        grade.setHorizontalSpacing(0)
        grade.setVerticalSpacing(2)
        self._celulas: list[_Celula] = []
        for linha in range(LINHAS):
            for coluna in range(7):
                celula = _Celula()
                celula.clicada.connect(self.definir_data)
                grade.addWidget(celula, linha, coluna)
                grade.setColumnStretch(coluna, 1)
                self._celulas.append(celula)
        interno.addLayout(grade)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addLayout(cabecalho)
        layout.addWidget(moldura)
        self._desenhar()

    # ---------------------------------------------------------------- estado
    def data(self) -> date:
        return self._data

    def intervalo(self) -> tuple[date, date]:
        if self._por_semana:
            inicio = inicio_da_semana(self._data)
            return inicio, inicio + timedelta(days=6)
        return self._data, self._data

    def definir_por_semana(self, valor: bool) -> None:
        self._por_semana = valor
        self._desenhar()

    def definir_data(self, dia: date) -> None:
        self._data = dia
        self._mes = dia.replace(day=1)
        self._desenhar()
        self.escolhida.emit(dia)

    def _andar(self, meses: int) -> None:
        mes = self._mes.month + meses
        ano = self._mes.year + (mes - 1) // 12
        self._mes = date(ano, (mes - 1) % 12 + 1, 1)
        self._desenhar()

    def _desenhar(self) -> None:
        self._titulo.setText(titulo_mes(self._mes))
        inicio = primeiro_dia_da_grade(self._mes)
        hoje = date.today()
        semana_escolhida = inicio_da_semana(self._data)

        for indice, celula in enumerate(self._celulas):
            dia = inicio + timedelta(days=indice)
            if self._por_semana:
                escolhido = inicio_da_semana(dia) == semana_escolhida
                ponta_esquerda = escolhido and indice % 7 == 0
                ponta_direita = escolhido and indice % 7 == 6
            else:
                escolhido = dia == self._data
                ponta_esquerda = ponta_direita = escolhido
            celula.definir(
                dia,
                do_mes=dia.month == self._mes.month,
                hoje=dia == hoje,
                escolhido=escolhido,
                ponta_esquerda=ponta_esquerda,
                ponta_direita=ponta_direita,
            )
