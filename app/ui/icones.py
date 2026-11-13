"""Ícones de traço da interface, desenhados com o QPainter.

Todos numa grade de 24×24, traço de 1,8 com pontas redondas — o mesmo
desenho do traço do logotipo, em escala de ícone. Desenhar aqui evita trazer
um pacote de ícones e deixa a cor sempre igual à do texto ao lado.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap


def _agenda(p: QPainter) -> None:
    p.drawRoundedRect(QRectF(3.5, 5, 17, 15.5), 3, 3)
    p.drawLine(QPointF(3.5, 10), QPointF(20.5, 10))
    p.drawLine(QPointF(8, 3), QPointF(8, 7))
    p.drawLine(QPointF(16, 3), QPointF(16, 7))
    p.drawPoint(QPointF(8.5, 14.5))
    p.drawPoint(QPointF(12, 14.5))
    p.drawPoint(QPointF(15.5, 14.5))


def _baixas(p: QPainter) -> None:
    # Quadro de colunas com um visto: o kanban das confirmações.
    p.drawRoundedRect(QRectF(3.5, 3.5, 17, 17), 3.5, 3.5)
    caminho = QPainterPath(QPointF(8, 12.2))
    caminho.lineTo(QPointF(10.8, 15))
    caminho.lineTo(QPointF(16.2, 9))
    p.drawPath(caminho)


def _clientes(p: QPainter) -> None:
    p.drawEllipse(QPointF(9.5, 8.5), 3.3, 3.3)
    caminho = QPainterPath(QPointF(3.5, 19.5))
    caminho.cubicTo(QPointF(3.8, 15.5), QPointF(6.5, 14), QPointF(9.5, 14))
    caminho.cubicTo(QPointF(12.5, 14), QPointF(15.2, 15.5), QPointF(15.5, 19.5))
    p.drawPath(caminho)
    p.drawArc(QRectF(13.2, 4.8, 6.4, 6.6), 110 * 16, -220 * 16)
    segundo = QPainterPath(QPointF(17.2, 14.2))
    segundo.cubicTo(QPointF(19.2, 14.6), QPointF(20.4, 16.4), QPointF(20.5, 19.5))
    p.drawPath(segundo)


def _lembrancinhas(p: QPainter) -> None:
    p.drawRoundedRect(QRectF(4.5, 11, 15, 9.5), 2, 2)
    p.drawRoundedRect(QRectF(3.5, 7.5, 17, 3.5), 1.5, 1.5)
    p.drawLine(QPointF(12, 7.5), QPointF(12, 20.5))
    laco = QPainterPath(QPointF(12, 7.5))
    laco.cubicTo(QPointF(10, 3), QPointF(6, 4), QPointF(7.5, 7.5))
    laco.moveTo(QPointF(12, 7.5))
    laco.cubicTo(QPointF(14, 3), QPointF(18, 4), QPointF(16.5, 7.5))
    p.drawPath(laco)


def _painel(p: QPainter) -> None:
    p.drawLine(QPointF(4, 20), QPointF(20, 20))
    for x, topo in ((7, 13), (12, 6), (17, 10)):
        p.drawLine(QPointF(x, 17), QPointF(x, topo))


def _cadastros(p: QPainter) -> None:
    for y, x in ((7, 15), (12, 9), (17, 13)):
        p.drawLine(QPointF(4, y), QPointF(20, y))
        p.save()
        p.setBrush(QColor(p.pen().color()))
        p.drawEllipse(QPointF(x, y), 1.9, 1.9)
        p.restore()


def _registro(p: QPainter) -> None:
    p.drawArc(QRectF(4, 4, 16, 16), 200 * 16, -310 * 16)
    seta = QPainterPath(QPointF(3.4, 8.6))
    seta.lineTo(QPointF(4.4, 12.4))
    seta.lineTo(QPointF(8, 11.2))
    p.drawPath(seta)
    p.drawLine(QPointF(12, 8), QPointF(12, 12))
    p.drawLine(QPointF(12, 12), QPointF(14.8, 14))


def _sair(p: QPainter) -> None:
    caminho = QPainterPath(QPointF(13, 4))
    caminho.lineTo(QPointF(6, 4))
    caminho.quadTo(QPointF(4, 4), QPointF(4, 6))
    caminho.lineTo(QPointF(4, 18))
    caminho.quadTo(QPointF(4, 20), QPointF(6, 20))
    caminho.lineTo(QPointF(13, 20))
    p.drawPath(caminho)
    p.drawLine(QPointF(10, 12), QPointF(20, 12))
    seta = QPainterPath(QPointF(16.5, 8.5))
    seta.lineTo(QPointF(20, 12))
    seta.lineTo(QPointF(16.5, 15.5))
    p.drawPath(seta)


def _atualizar(p: QPainter) -> None:
    p.drawLine(QPointF(12, 4), QPointF(12, 15))
    seta = QPainterPath(QPointF(7.5, 10.5))
    seta.lineTo(QPointF(12, 15))
    seta.lineTo(QPointF(16.5, 10.5))
    p.drawPath(seta)
    base = QPainterPath(QPointF(4.5, 15.5))
    base.lineTo(QPointF(4.5, 18.5))
    base.quadTo(QPointF(4.5, 20), QPointF(6, 20))
    base.lineTo(QPointF(18, 20))
    base.quadTo(QPointF(19.5, 20), QPointF(19.5, 18.5))
    base.lineTo(QPointF(19.5, 15.5))
    p.drawPath(base)


def _check(p: QPainter) -> None:
    caminho = QPainterPath(QPointF(5, 12.5))
    caminho.lineTo(QPointF(10, 17.5))
    caminho.lineTo(QPointF(19.5, 7))
    p.drawPath(caminho)


def _lua(p: QPainter) -> None:
    # Crescente: um círculo com outro "mordendo" o lado direito.
    caminho = QPainterPath(QPointF(15.5, 4.2))
    caminho.cubicTo(QPointF(9.5, 3.2), QPointF(4.2, 7.6), QPointF(4.2, 13))
    caminho.cubicTo(QPointF(4.2, 17.6), QPointF(8, 20.8), QPointF(12.4, 20.8))
    caminho.cubicTo(QPointF(16.2, 20.8), QPointF(19.2, 18.6), QPointF(20.2, 15.4))
    caminho.cubicTo(QPointF(14.6, 16.8), QPointF(10.4, 11), QPointF(15.5, 4.2))
    p.drawPath(caminho)


def _sol(p: QPainter) -> None:
    p.drawEllipse(QPointF(12, 12), 4, 4)
    for x1, y1, x2, y2 in (
        (12, 2.5, 12, 4.5), (12, 19.5, 12, 21.5), (2.5, 12, 4.5, 12),
        (19.5, 12, 21.5, 12), (5.3, 5.3, 6.7, 6.7), (17.3, 17.3, 18.7, 18.7),
        (5.3, 18.7, 6.7, 17.3), (17.3, 6.7, 18.7, 5.3),
    ):
        p.drawLine(QPointF(x1, y1), QPointF(x2, y2))


DESENHOS: dict[str, Callable[[QPainter], None]] = {
    "lua": _lua,
    "sol": _sol,
    "agenda": _agenda,
    "baixas": _baixas,
    "clientes": _clientes,
    "lembrancinhas": _lembrancinhas,
    "painel": _painel,
    "cadastros": _cadastros,
    "registro": _registro,
    "sair": _sair,
    "atualizar": _atualizar,
    "check": _check,
}


def pixmap(nome: str, cor: str, lado: int = 18, escala: float = 2.0) -> QPixmap:
    real = round(lado * escala)
    quadro = QPixmap(real, real)
    quadro.fill(Qt.GlobalColor.transparent)
    pintor = QPainter(quadro)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    pintor.scale(real / 24, real / 24)
    caneta = QPen(QColor(cor), 1.8)
    caneta.setCapStyle(Qt.PenCapStyle.RoundCap)
    caneta.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pintor.setPen(caneta)
    pintor.setBrush(Qt.BrushStyle.NoBrush)
    DESENHOS[nome](pintor)
    pintor.end()
    quadro.setDevicePixelRatio(escala)
    return quadro


@lru_cache(maxsize=64)
def icone(nome: str, cor: str, cor_ativa: str | None = None, lado: int = 18) -> QIcon:
    """Ícone com uma cor normal e, se pedida, outra para o estado marcado."""
    resultado = QIcon()
    resultado.addPixmap(pixmap(nome, cor, lado), QIcon.Mode.Normal, QIcon.State.Off)
    alvo = cor_ativa or cor
    resultado.addPixmap(pixmap(nome, alvo, lado), QIcon.Mode.Normal, QIcon.State.On)
    resultado.addPixmap(pixmap(nome, alvo, lado), QIcon.Mode.Active, QIcon.State.Off)
    resultado.addPixmap(pixmap(nome, alvo, lado), QIcon.Mode.Active, QIcon.State.On)
    return resultado
