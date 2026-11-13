"""Tela de abertura: aparece enquanto o programa conecta ao banco e monta a
janela, para ninguém achar que o clique no atalho não fez nada."""

from __future__ import annotations

import threading
from typing import Callable, TypeVar

from PySide6.QtCore import QElapsedTimer, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QGuiApplication, QPainter, QPainterPath
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QVBoxLayout, QWidget

from app import __version__
from app.ui import marca as marca_visual
from app.ui.estilo import CORES, FONTE_DADOS

T = TypeVar("T")


class FaixaAnimada(QWidget):
    """A faixa tricolor correndo, como um carregamento sem fim definido."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(4)
        self._relogio = QElapsedTimer()
        self._relogio.start()
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self.update)
        self._timer.start()

    def paintEvent(self, _evento) -> None:  # noqa: N802
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        largura, altura = self.width(), self.height()
        trilho = QPainterPath()
        trilho.addRoundedRect(QRectF(0, 0, largura, altura), 2, 2)
        pintor.fillPath(trilho, QColor(255, 255, 255, 28))
        pintor.setClipPath(trilho)

        # Um bloco de 40% da largura atravessa o trilho a cada 1,4 s.
        fase = (self._relogio.elapsed() % 1400) / 1400
        tamanho = largura * 0.4
        inicio = -tamanho + fase * (largura + tamanho)
        total = sum(marca_visual.PROPORCOES_FAIXA)
        x = inicio
        for cor, peso in zip(marca_visual.CORES_FAIXA, marca_visual.PROPORCOES_FAIXA):
            pedaco = tamanho * peso / total
            pintor.fillRect(QRectF(x, 0, pedaco, altura), QColor(cor))
            x += pedaco
        pintor.end()


class TelaAbertura(QFrame):
    """Janela sem moldura, marinho, com o logotipo e o que está acontecendo."""

    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.SplashScreen
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setObjectName("abertura")
        self.setFixedSize(520, 320)
        self.setStyleSheet(
            f"QFrame#abertura {{ background: {CORES['marca']};"
            " border: 1px solid #2E4677; }"
            "QFrame#abertura QLabel { background: transparent; }"
        )

        logotipo = QLabel()
        logotipo.setPixmap(marca_visual.pixmap(84, escuro=True, assinado=True))
        logotipo.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.texto = QLabel("Abrindo…")
        self.texto.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.texto.setStyleSheet(f"color: {CORES['lateral_texto']}; font-size: 13px;")

        versao = QLabel(f"versão {__version__}")
        versao.setAlignment(Qt.AlignmentFlag.AlignCenter)
        versao.setStyleSheet(
            f'color: #7F8FB6; font-family: "{FONTE_DADOS}"; font-size: 10px;'
        )

        self.barra = FaixaAnimada()
        self.barra.setFixedWidth(220)

        # Sem margem nas laterais: a faixa do rodapé encosta nas bordas.
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 46, 0, 0)
        layout.setSpacing(0)
        layout.addStretch(1)
        layout.addWidget(logotipo)
        layout.addSpacing(34)
        layout.addWidget(self.barra, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addSpacing(14)
        layout.addWidget(self.texto)
        layout.addStretch(1)
        layout.addWidget(versao)
        layout.addSpacing(18)

    def mostrar(self, texto: str | None = None) -> None:
        if texto:
            self.texto.setText(texto)
        tela = QGuiApplication.primaryScreen()
        if tela is not None:
            area = tela.availableGeometry()
            self.move(area.center() - self.rect().center())
        self.show()
        self.raise_()
        QApplication.processEvents()

    def mensagem(self, texto: str) -> None:
        self.texto.setText(texto)
        QApplication.processEvents()

    def esperar(self, funcao: Callable[[], T], texto: str | None = None) -> T:
        """Roda `funcao` numa thread, com a animação viva enquanto isso.

        Só para trabalho sem tela (banco, rede). Erro dentro dela volta aqui.
        """
        if texto:
            self.mensagem(texto)
        resultado: dict = {}

        def rodar() -> None:
            try:
                resultado["valor"] = funcao()
            except BaseException as erro:  # noqa: BLE001 - devolve para quem chamou
                resultado["erro"] = erro

        linha = threading.Thread(target=rodar, daemon=True)
        linha.start()
        while linha.is_alive():
            QApplication.processEvents()
            linha.join(0.016)
        if "erro" in resultado:
            raise resultado["erro"]
        return resultado.get("valor")
