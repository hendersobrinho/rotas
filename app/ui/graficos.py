"""Gráficos desenhados à mão com QPainter, no mesmo tema do resto do app.

Regras seguidas aqui (guia de visualização de dados):
marca fina com ponta arredondada de 4px ancorada na linha de base, folga de
2px entre barras, eixo discreto, rótulo direto em vez de legenda solta, e
dica ao passar o mouse com o número exato.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath
from PySide6.QtWidgets import QSizePolicy, QToolTip, QWidget

from app.ui.estilo import CORES, FONTE_DADOS, FONTE_UI

RAIO = 4.0
FOLGA = 2.0


@dataclass
class Fatia:
    """Uma marca do gráfico: rótulo, valor e cor de preenchimento."""

    rotulo: str
    valor: int
    cor: str = CORES["azul"]
    detalhe: str = ""


def _fonte(tamanho: int, peso: QFont.Weight = QFont.Weight.Normal, dados: bool = False) -> QFont:
    fonte = QFont(FONTE_DADOS if dados else FONTE_UI, tamanho)
    fonte.setWeight(peso)
    return fonte


def _ponta_arredondada(
    retangulo: QRectF, horizontal: bool, raio: float = RAIO
) -> QPainterPath:
    """Barra com a ponta de fora arredondada e a base reta, colada no eixo."""
    caminho = QPainterPath()
    r = min(raio, retangulo.height() / 2, retangulo.width() / 2)
    if r <= 0.5:
        caminho.addRect(retangulo)
        return caminho
    x, y, w, h = (
        retangulo.x(),
        retangulo.y(),
        retangulo.width(),
        retangulo.height(),
    )
    if horizontal:  # cresce para a direita
        caminho.moveTo(x, y)
        caminho.lineTo(x + w - r, y)
        caminho.quadTo(QPointF(x + w, y), QPointF(x + w, y + r))
        caminho.lineTo(x + w, y + h - r)
        caminho.quadTo(QPointF(x + w, y + h), QPointF(x + w - r, y + h))
        caminho.lineTo(x, y + h)
    else:  # cresce para cima
        caminho.moveTo(x, y + h)
        caminho.lineTo(x, y + r)
        caminho.quadTo(QPointF(x, y), QPointF(x + r, y))
        caminho.lineTo(x + w - r, y)
        caminho.quadTo(QPointF(x + w, y), QPointF(x + w, y + r))
        caminho.lineTo(x + w, y + h)
    caminho.closeSubpath()
    return caminho


class _GraficoBase(QWidget):
    vazio_texto = "Nada neste período"

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._fatias: list[Fatia] = []
        self._areas: list[tuple[QRectF, Fatia]] = []
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def definir(self, fatias: list[Fatia]) -> None:
        self._fatias = [f for f in fatias]
        self.update()

    def _desenhar_vazio(self, pintor: QPainter) -> None:
        pintor.setPen(QColor(CORES["tinta_fraca"]))
        pintor.setFont(_fonte(12))
        pintor.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.vazio_texto)

    def mouseMoveEvent(self, evento) -> None:  # noqa: N802
        posicao = evento.position()
        for area, fatia in self._areas:
            if area.contains(posicao):
                texto = f"{fatia.rotulo}: {fatia.valor}"
                if fatia.detalhe:
                    texto += f"\n{fatia.detalhe}"
                QToolTip.showText(evento.globalPosition().toPoint(), texto, self)
                return
        QToolTip.hideText()
        super().mouseMoveEvent(evento)


class BarrasHorizontais(_GraficoBase):
    """Magnitude por categoria: nome à esquerda, número na ponta da barra."""

    ALTURA_BARRA = 22

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(140)

    def sizeHint(self):  # noqa: N802
        base = super().sizeHint()
        altura = max(140, len(self._fatias) * (self.ALTURA_BARRA + 10) + 16)
        base.setHeight(altura)
        return base

    def paintEvent(self, _evento) -> None:  # noqa: N802
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._areas = []
        if not self._fatias:
            self._desenhar_vazio(pintor)
            return

        fonte_rotulo = _fonte(12)
        fonte_valor = _fonte(12, QFont.Weight.DemiBold, dados=True)
        metricas = QFontMetrics(fonte_rotulo)
        largura_rotulo = min(
            160,
            max(metricas.horizontalAdvance(f.rotulo) for f in self._fatias) + 12,
        )
        largura_valor = 44
        x0 = largura_rotulo
        largura_util = max(10.0, self.width() - x0 - largura_valor)
        maior = max(1, max(f.valor for f in self._fatias))
        passo = (self.ALTURA_BARRA + 10)

        for indice, fatia in enumerate(self._fatias):
            y = indice * passo + 6
            comprimento = largura_util * fatia.valor / maior
            barra = QRectF(x0, y, max(comprimento, 3.0), self.ALTURA_BARRA)

            pintor.setPen(QColor(CORES["tinta_media"]))
            pintor.setFont(fonte_rotulo)
            texto = metricas.elidedText(
                fatia.rotulo, Qt.TextElideMode.ElideRight, int(largura_rotulo - 10)
            )
            pintor.drawText(
                QRectF(0, y, largura_rotulo - 10, self.ALTURA_BARRA),
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                texto,
            )

            pintor.setPen(Qt.PenStyle.NoPen)
            pintor.setBrush(QColor(fatia.cor))
            pintor.drawPath(_ponta_arredondada(barra, horizontal=True))

            pintor.setPen(QColor(CORES["tinta"]))
            pintor.setFont(fonte_valor)
            pintor.drawText(
                QRectF(barra.right() + 8, y, largura_valor - 8, self.ALTURA_BARRA),
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                str(fatia.valor),
            )
            self._areas.append((QRectF(0, y, self.width(), self.ALTURA_BARRA), fatia))
        pintor.end()


class BarrasVerticais(_GraficoBase):
    """Quantidade ao longo do tempo: uma coluna por fatia do período."""

    ALTURA_EIXO = 26

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumHeight(180)

    def paintEvent(self, _evento) -> None:  # noqa: N802
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._areas = []
        if not self._fatias:
            self._desenhar_vazio(pintor)
            return

        fonte_eixo = _fonte(9, dados=True)
        fonte_valor = _fonte(10, QFont.Weight.DemiBold, dados=True)
        base_y = self.height() - self.ALTURA_EIXO
        topo = 20.0
        maior = max(1, max(f.valor for f in self._fatias))
        largura_fatia = self.width() / len(self._fatias)
        largura_barra = max(3.0, min(26.0, largura_fatia - FOLGA * 2 - 4))

        # eixo discreto: uma linha fina, sem grade
        pintor.setPen(QColor(CORES["pauta"]))
        pintor.drawLine(QPointF(0, base_y), QPointF(self.width(), base_y))

        metricas = QFontMetrics(fonte_eixo)
        cabe_todos = metricas.horizontalAdvance("00") + 6 <= largura_fatia
        for indice, fatia in enumerate(self._fatias):
            centro = largura_fatia * (indice + 0.5)
            altura = (base_y - topo) * fatia.valor / maior
            barra = QRectF(
                centro - largura_barra / 2,
                base_y - max(altura, 2.0 if fatia.valor else 0.0),
                largura_barra,
                max(altura, 2.0 if fatia.valor else 0.0),
            )
            if fatia.valor:
                pintor.setPen(Qt.PenStyle.NoPen)
                pintor.setBrush(QColor(fatia.cor))
                pintor.drawPath(_ponta_arredondada(barra, horizontal=False))
                pintor.setPen(QColor(CORES["tinta_media"]))
                pintor.setFont(fonte_valor)
                pintor.drawText(
                    QRectF(centro - largura_fatia / 2, barra.top() - 16,
                           largura_fatia, 14),
                    Qt.AlignmentFlag.AlignCenter,
                    str(fatia.valor),
                )

            if cabe_todos or indice % 2 == 0:
                pintor.setPen(QColor(CORES["tinta_fraca"]))
                pintor.setFont(fonte_eixo)
                pintor.drawText(
                    QRectF(centro - largura_fatia / 2, base_y + 4,
                           largura_fatia, self.ALTURA_EIXO - 4),
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
                    fatia.rotulo,
                )
            self._areas.append(
                (QRectF(centro - largura_fatia / 2, topo, largura_fatia,
                        base_y - topo), fatia)
            )
        pintor.end()
