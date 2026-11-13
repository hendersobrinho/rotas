"""A marca do Rotas: cores, logotipo e ícone.

Os arquivos vetoriais vêm da pasta da marca (`rotas-marca/`) e vivem em
`app/recursos/marca/`. Para a tela, viram QPixmap no tamanho pedido; para o
PDF, viram uma imagem em resolução alta, registrada como recurso do documento.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app import caminhos
from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QFrame, QHBoxLayout, QWidget

# O logotipo "claro" é o que vai em fundo claro (PDF, diálogos); o "escuro",
# no fundo marinho (barra lateral, tela de entrada). "Assinado" traz a linha
# de assinatura embaixo da palavra.
LOGO = caminhos.recurso("marca", "rotas-logo-claro-sem-assinatura.svg")
LOGO_ASSINADO = caminhos.recurso("marca", "rotas-logo-claro.svg")
LOGO_ESCURO = caminhos.recurso("marca", "rotas-logo-escuro-sem-assinatura.svg")
LOGO_ESCURO_ASSINADO = caminhos.recurso("marca", "rotas-logo-escuro.svg")
SIMBOLO = caminhos.recurso("marca", "rotas-simbolo-claro.svg")
SIMBOLO_ESCURO = caminhos.recurso("marca", "rotas-simbolo-escuro.svg")
ICONE = caminhos.recurso("icone.svg")  # o R com o pino, no quadrado marinho

# Cores da marca (ver rotas-marca/LEIA-ME.md).
AZUL_MARCA = "#203461"   # Marinho Métodos: base, textos, fundo do ícone
AZUL_TINTA = "#16244A"   # Tinta: títulos fortes, texto sobre âmbar
CIANO = "#4BBDCD"        # Ciano Rota: o traço; destaque e seleção, nunca texto
LARANJA = "#F9B259"      # Âmbar Destino: pino, botão principal, pendente
ARDOSIA = "#5B6782"      # texto secundário
NEVOA = "#F4F6FA"        # fundo da janela
LINHA = "#E1E6F0"        # bordas
CIANO_CLARO = "#E6F6F8"
AZUL_MARCA_CLARO = "#E8ECF5"
LARANJA_CLARO = "#FEF1DF"

# Faixa tricolor: âmbar 25% · ciano 33% · marinho 42%.
CORES_FAIXA = (LARANJA, CIANO, AZUL_MARCA)
PROPORCOES_FAIXA = (25, 33, 42)


def _caminho(simbolo: bool, escuro: bool = False, assinado: bool = False) -> Path:
    if simbolo:
        return SIMBOLO_ESCURO if escuro else SIMBOLO
    if escuro:
        return LOGO_ESCURO_ASSINADO if assinado else LOGO_ESCURO
    return LOGO_ASSINADO if assinado else LOGO


def imagem(
    altura: int, simbolo: bool = False, escuro: bool = False, assinado: bool = False
) -> QImage:
    """Desenha o logotipo com a altura pedida, mantendo a proporção."""
    renderizador = QSvgRenderer(str(_caminho(simbolo, escuro, assinado)))
    tamanho = renderizador.defaultSize()
    largura = max(1, round(altura * tamanho.width() / tamanho.height()))

    quadro = QImage(QSize(largura, altura), QImage.Format.Format_ARGB32_Premultiplied)
    quadro.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(quadro)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderizador.render(pintor)
    pintor.end()
    return quadro


@lru_cache(maxsize=8)
def proporcao(
    simbolo: bool = False, escuro: bool = False, assinado: bool = False
) -> float:
    """Largura ÷ altura do desenho — para reservar o espaço certo no PDF."""
    tamanho = QSvgRenderer(str(_caminho(simbolo, escuro, assinado))).defaultSize()
    return tamanho.width() / max(1, tamanho.height())


def imagem_icone(lado: int) -> QImage:
    """O ícone do programa num quadrado de `lado`.

    Desenha grande e reduz com suavização: nos tamanhos pequenos os traços
    ficam mais limpos do que desenhados direto.
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


def _escala_da_tela() -> float:
    from PySide6.QtGui import QGuiApplication

    if QGuiApplication.instance() is None:
        return 1.0
    tela = QGuiApplication.primaryScreen()
    return max(1.0, tela.devicePixelRatio()) if tela is not None else 1.0


@lru_cache(maxsize=16)
def pixmap(
    altura: int, simbolo: bool = False, escuro: bool = False, assinado: bool = False
) -> QPixmap:
    """O logotipo para a tela, nítido também em monitor de alta densidade."""
    escala = _escala_da_tela()
    quadro = QPixmap.fromImage(
        imagem(round(altura * escala), simbolo, escuro, assinado)
    )
    quadro.setDevicePixelRatio(escala)
    return quadro


@lru_cache(maxsize=1)
def icone() -> QIcon:
    """Ícone do programa, nos tamanhos que os ambientes costumam pedir.

    É o mesmo desenho do atalho da área de trabalho e do .ico do executável
    (`app/recursos/rotas.ico`, que vem pronto da pasta da marca).
    """
    icone_marca = QIcon()
    for lado in (16, 24, 32, 48, 64, 128, 256, 512):
        icone_marca.addPixmap(QPixmap.fromImage(imagem_icone(lado)))
    return icone_marca


def fio_imagem(largura: int, altura: int,
               proporcoes: tuple[int, int, int] = PROPORCOES_FAIXA) -> QImage:
    """A faixa tricolor como imagem, para quando o layout não estica sozinho."""
    quadro = QImage(QSize(max(1, largura), max(1, altura)),
                    QImage.Format.Format_RGB32)
    pintor = QPainter(quadro)
    total = sum(proporcoes)
    x = 0
    for indice, cor in enumerate(CORES_FAIXA):
        fim = largura if indice == len(proporcoes) - 1 else round(largura * sum(
            proporcoes[: indice + 1]) / total)
        pintor.fillRect(x, 0, fim - x, altura, QColor(cor))
        x = fim
    pintor.end()
    return quadro


def faixa(altura: int = 3,
          proporcoes: tuple[int, int, int] = PROPORCOES_FAIXA) -> QWidget:
    """A faixa de três cores da marca: âmbar, ciano e marinho, nessa ordem."""
    caixa = QWidget()
    caixa.setFixedHeight(altura)
    layout = QHBoxLayout(caixa)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    for cor, peso in zip(CORES_FAIXA, proporcoes):
        pedaco = QFrame()
        pedaco.setStyleSheet(f"background: {cor}; border: none;")
        layout.addWidget(pedaco, peso)
    return caixa
