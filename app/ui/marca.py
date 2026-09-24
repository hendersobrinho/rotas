"""A marca do escritório: cores e desenho do logotipo.

O arquivo vetorial vive em `app/recursos/`. Para a tela, ele vira QPixmap no
tamanho pedido; para o PDF, vira uma imagem em resolução alta, registrada como
recurso do documento.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QWidget

RECURSOS = Path(__file__).resolve().parents[1] / "recursos"
LOGO = RECURSOS / "logo.svg"      # símbolo + palavra + seta
SIMBOLO = RECURSOS / "marca.svg"  # só o símbolo

# As cores saem do próprio logotipo.
AZUL_MARCA = "#203461"
AZUL_TINTA = "#1C2066"
CIANO = "#4BBDCD"
LARANJA = "#F9B259"
CIANO_CLARO = "#E8F6F8"
AZUL_MARCA_CLARO = "#E8ECF5"
LARANJA_CLARO = "#FEF1DF"


def _caminho(simbolo: bool) -> Path:
    return SIMBOLO if simbolo else LOGO


def imagem(altura: int, simbolo: bool = False) -> QImage:
    """Desenha o logotipo com a altura pedida, mantendo a proporção."""
    renderizador = QSvgRenderer(str(_caminho(simbolo)))
    tamanho = renderizador.defaultSize()
    largura = max(1, round(altura * tamanho.width() / tamanho.height()))

    quadro = QImage(QSize(largura, altura), QImage.Format.Format_ARGB32_Premultiplied)
    quadro.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(quadro)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderizador.render(pintor)
    pintor.end()
    return quadro


@lru_cache(maxsize=16)
def pixmap(altura: int, simbolo: bool = False) -> QPixmap:
    return QPixmap.fromImage(imagem(altura, simbolo))


@lru_cache(maxsize=1)
def icone() -> QIcon:
    """Ícone da janela, nos tamanhos que os ambientes costumam pedir."""
    icone_marca = QIcon()
    for lado in (16, 24, 32, 48, 64, 128, 256):
        icone_marca.addPixmap(QPixmap.fromImage(imagem(lado, simbolo=True)))
    return icone_marca


def fio_imagem(largura: int, altura: int,
               proporcoes: tuple[int, int, int] = (5, 3, 2)) -> QImage:
    """O fio tricolor como imagem, para quando o layout não estica sozinho."""
    from PySide6.QtGui import QColor

    quadro = QImage(QSize(max(1, largura), max(1, altura)),
                    QImage.Format.Format_RGB32)
    pintor = QPainter(quadro)
    total = sum(proporcoes)
    x = 0
    for indice, (cor, peso) in enumerate(zip((AZUL_MARCA, CIANO, LARANJA), proporcoes)):
        fim = largura if indice == len(proporcoes) - 1 else round(largura * sum(
            proporcoes[: indice + 1]) / total)
        pintor.fillRect(x, 0, fim - x, altura, QColor(cor))
        x = fim
    pintor.end()
    return quadro


def faixa(altura: int = 3, proporcoes: tuple[int, int, int] = (5, 3, 2)) -> QWidget:
    """Fio de três cores da marca — azul, ciano e laranja, nessa ordem."""

    caixa = QWidget()
    caixa.setFixedHeight(altura)
    layout = QHBoxLayout(caixa)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    for cor, peso in zip((AZUL_MARCA, CIANO, LARANJA), proporcoes):
        pedaco = QFrame()
        pedaco.setStyleSheet(f"background: {cor};")
        layout.addWidget(pedaco, peso)
    return caixa
