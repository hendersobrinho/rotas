"""A marca do escritório: cores e desenho do logotipo.

O arquivo vetorial vive em `app/recursos/`. Para a tela, ele vira QPixmap no
tamanho pedido; para o PDF, vira uma imagem em resolução alta, registrada como
recurso do documento.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app import caminhos
from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QWidget

LOGO = caminhos.recurso("logo.svg")      # símbolo + palavra + seta
SIMBOLO = caminhos.recurso("marca.svg")  # só o símbolo
ICONE = caminhos.recurso("icone.svg")    # o motoboy, ícone do programa

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


def imagem_icone(lado: int) -> QImage:
    """O ícone do programa no maior tamanho que couber num quadrado de `lado`.

    O desenho é deitado e o espaço que o sistema reserva para um ícone é
    quadrado, então ele entra centralizado, esticado até encostar nas laterais
    — mantendo a proporção, que distorcer para preencher ficaria torto. Desenha
    grande e reduz com suavização: nos tamanhos pequenos os traços finos do
    contorno somem se forem desenhados direto.
    """
    renderizador = QSvgRenderer(str(ICONE))
    tamanho = renderizador.defaultSize()

    grande = max(lado * 4, 512)
    escala = min(grande / tamanho.width(), grande / tamanho.height())
    largura = tamanho.width() * escala
    altura = tamanho.height() * escala

    quadro = QImage(QSize(grande, grande), QImage.Format.Format_ARGB32_Premultiplied)
    quadro.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(quadro)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    pintor.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    renderizador.render(
        pintor, QRectF((grande - largura) / 2, (grande - altura) / 2, largura, altura)
    )
    pintor.end()

    if grande == lado:
        return quadro
    return quadro.scaled(
        lado, lado,
        Qt.AspectRatioMode.IgnoreAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )


@lru_cache(maxsize=16)
def pixmap(altura: int, simbolo: bool = False) -> QPixmap:
    return QPixmap.fromImage(imagem(altura, simbolo))


@lru_cache(maxsize=1)
def icone() -> QIcon:
    """Ícone do programa, nos tamanhos que os ambientes costumam pedir.

    É o mesmo desenho do atalho da área de trabalho — ver
    `scripts/gerar_icones.py`, que gera o .ico do Windows e os PNGs do Linux.
    """
    icone_marca = QIcon()
    for lado in (16, 24, 32, 48, 64, 128, 256, 512):
        icone_marca.addPixmap(QPixmap.fromImage(imagem_icone(lado)))
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
