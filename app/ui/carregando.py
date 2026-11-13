"""Tela de espera: o R da marca se desenhando sobre a janela desfocada.

Uso, de qualquer tela:

    dados = esperar(self, buscar_no_banco, "Carregando clientes…")

`buscar_no_banco` roda numa thread (só banco e rede, nada de tela). Se terminar
rápido, nada aparece; passando de um instante, a janela fica desfocada por
baixo e o R se desenha no meio até o trabalho acabar.
"""

from __future__ import annotations

import threading
import time
from typing import Callable, TypeVar

from PySide6.QtCore import QElapsedTimer, QEvent, QObject, QPointF, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from app.ui import marca as marca_visual
from app.ui.estilo import CORES, FONTE_TITULO, escuro

T = TypeVar("T")

# Quanto esperar antes de mostrar (rápido assim, nem pisca) e, depois de
# mostrar, quanto tempo no mínimo (para não piscar ao terminar).
ATRASO_S = 0.15
MINIMO_S = 0.5
CICLO_MS = 2200


def _caminho_do_r() -> QPainterPath:
    """O traço do R, no espaço 512 × 512 do ícone (app/recursos/icone.svg)."""
    caminho = QPainterPath(QPointF(150, 396))
    caminho.lineTo(150, 112)
    caminho.lineTo(246, 112)
    caminho.arcTo(QRectF(172, 112, 148, 148), 90, -180)
    caminho.lineTo(206, 260)
    caminho.lineTo(362, 396)
    return caminho


def _desfocar(imagem: QPixmap, fator: int = 14) -> QPixmap:
    """Desfoque barato: reduz e amplia de novo, suavizando."""
    if imagem.isNull():
        return imagem
    largura, altura = imagem.width(), imagem.height()
    pequena = imagem.scaled(
        max(1, largura // fator), max(1, altura // fator),
        Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation,
    )
    media = pequena.scaled(
        max(1, largura // 4), max(1, altura // 4),
        Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation,
    )
    resultado = media.scaled(
        largura, altura,
        Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation,
    )
    resultado.setDevicePixelRatio(imagem.devicePixelRatio())
    return resultado


class TelaCarregando(QWidget):
    """Cobre a janela inteira: fundo desfocado, cartão com o R animado."""

    def __init__(self, janela: QWidget, texto: str) -> None:
        super().__init__(janela)
        self._texto = texto
        self._fundo = _desfocar(janela.grab())
        self._r = _caminho_do_r()
        self._pontos = [self._r.pointAtPercent(i / 240) for i in range(241)]
        self._relogio = QElapsedTimer()
        self._relogio.start()
        self._entrada = 0.0  # 0 → 1 no primeiro quarto de segundo
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self.update)
        self._timer.start()
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setGeometry(janela.rect())
        janela.installEventFilter(self)
        self.show()
        self.raise_()
        self.setFocus()

    # A janela mudou de tamanho: acompanha.
    def eventFilter(self, objeto: QObject, evento: QEvent) -> bool:  # noqa: N802
        if objeto is self.parent() and evento.type() == QEvent.Type.Resize:
            self.setGeometry(self.parent().rect())
        return False

    # Enquanto carrega, cliques e teclas param aqui.
    def mousePressEvent(self, evento) -> None:  # noqa: N802
        evento.accept()

    def keyPressEvent(self, evento) -> None:  # noqa: N802
        evento.accept()

    def encerrar(self) -> None:
        self._timer.stop()
        if self.parent() is not None:
            self.parent().removeEventFilter(self)
        self.hide()
        self.deleteLater()

    # ------------------------------------------------------------ desenho
    def paintEvent(self, _evento) -> None:  # noqa: N802
        decorrido = self._relogio.elapsed()
        entrada = min(1.0, decorrido / 250)
        pintor = QPainter(self)
        pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
        pintor.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        # Fundo: a janela desfocada, apagada por um véu da cor do tema.
        pintor.setOpacity(entrada)
        pintor.drawPixmap(self.rect(), self._fundo)
        veu = QColor(CORES["canvas"])
        veu.setAlpha(150 if escuro() else 120)
        pintor.fillRect(self.rect(), veu)

        # O cartão no meio.
        largura, altura = 300, 250
        cartao = QRectF(
            (self.width() - largura) / 2, (self.height() - altura) / 2 + (1 - entrada) * 12,
            largura, altura,
        )
        # Sombra difusa: camadas cada vez maiores e mais fracas.
        for passo in range(10, 0, -1):
            sombra = QPainterPath()
            sombra.addRoundedRect(
                cartao.adjusted(-passo * 2, -passo + 6, passo * 2, passo * 2 + 6),
                22 + passo * 2, 22 + passo * 2,
            )
            pintor.fillPath(sombra, QColor(10, 20, 45, 7))
        forma = QPainterPath()
        forma.addRoundedRect(cartao, 22, 22)
        pintor.fillPath(forma, QColor(CORES["papel"]))
        pintor.setPen(QPen(QColor(CORES["pauta"]), 1))
        pintor.drawPath(forma)

        lado = 104.0
        icone = QRectF(cartao.center().x() - lado / 2, cartao.top() + 34, lado, lado)
        self._desenhar_r(pintor, icone, decorrido)

        pintor.setPen(QColor(CORES["tinta"]))
        fonte = QFont(FONTE_TITULO)
        fonte.setPixelSize(15)
        fonte.setWeight(QFont.Weight.DemiBold)
        pintor.setFont(fonte)
        texto = QRectF(cartao.left(), icone.bottom() + 20, cartao.width(), 24)
        pintor.drawText(texto, Qt.AlignmentFlag.AlignCenter, self._texto)

        self._desenhar_faixa(
            pintor, QRectF(cartao.left() + 60, texto.bottom() + 16, cartao.width() - 120, 4),
            decorrido,
        )
        pintor.end()

    def _desenhar_r(self, pintor: QPainter, alvo: QRectF, decorrido: int) -> None:
        """O R se traça, o pino cai no fim da rota, segura e recomeça."""
        fase = (decorrido % CICLO_MS) / CICLO_MS
        pintor.save()
        pintor.translate(alvo.topLeft())
        escala = alvo.width() / 512
        pintor.scale(escala, escala)

        fundo = QPainterPath()
        fundo.addRoundedRect(QRectF(0, 0, 512, 512), 116, 116)
        pintor.fillPath(fundo, QColor(marca_visual.AZUL_MARCA))

        pintor.translate(19.32, 6.42)
        pintor.scale(0.8688, 0.8688)

        # Os primeiros 55% do ciclo desenham o traço; depois ele fica inteiro
        # até o fim, quando some junto com o pino.
        sumindo = max(0.0, (fase - 0.88) / 0.12)
        progresso = min(1.0, fase / 0.55)
        progresso = 1 - (1 - progresso) ** 2  # desacelera chegando ao fim
        trilho = QPen(QColor(255, 255, 255, 22), 62)
        trilho.setCapStyle(Qt.PenCapStyle.RoundCap)
        trilho.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        pintor.setPen(trilho)
        pintor.drawPath(self._r)

        quantos = max(1, int(progresso * (len(self._pontos) - 1)))
        if progresso > 0:
            traco = QPainterPath(self._pontos[0])
            for ponto in self._pontos[1:quantos + 1]:
                traco.lineTo(ponto)
            caneta = QPen(QColor(marca_visual.CIANO), 62)
            caneta.setCapStyle(Qt.PenCapStyle.RoundCap)
            caneta.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            pintor.setOpacity(pintor.opacity() * (1 - sumindo))
            pintor.setPen(caneta)
            pintor.drawPath(traco)

        # O ponto de partida, branco, aparece desde o começo.
        pintor.setPen(Qt.PenStyle.NoPen)
        pintor.setBrush(QColor("#FFFFFF"))
        pintor.drawEllipse(QPointF(150, 396), 13.64, 13.64)

        # O pino cai de cima quando o traço chega, com um quique.
        if fase >= 0.5:
            queda = min(1.0, (fase - 0.5) / 0.16)
            # quique: passa um pouco do chão e volta
            if queda < 1:
                y = -260 * (1 - queda) ** 2
            else:
                volta = min(1.0, (fase - 0.66) / 0.08)
                y = -18 * (1 - abs(1 - 2 * volta)) if volta < 1 else 0
            pintor.save()
            pintor.translate(0, y)
            pino = QPainterPath(QPointF(362.0, 493.5))
            pino.lineTo(319.08, 421.64)
            pino.arcTo(QRectF(312, 346, 100, 100), 210.85, -241.71)
            pino.closeSubpath()
            contorno = QPen(QColor(marca_visual.AZUL_MARCA), 26)
            contorno.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            pintor.setPen(contorno)
            pintor.setBrush(QColor(marca_visual.LARANJA))
            pintor.drawPath(pino)
            pintor.setPen(Qt.PenStyle.NoPen)
            pintor.setBrush(QColor(marca_visual.AZUL_MARCA))
            pintor.drawEllipse(QPointF(362, 396), 21, 21)
            pintor.restore()
        pintor.restore()

    @staticmethod
    def _desenhar_faixa(pintor: QPainter, trilho: QRectF, decorrido: int) -> None:
        """A faixa tricolor correndo, a mesma da tela de abertura."""
        caminho = QPainterPath()
        caminho.addRoundedRect(trilho, 2, 2)
        pintor.fillPath(caminho, QColor(CORES["pauta"]))
        pintor.save()
        pintor.setClipPath(caminho)
        fase = (decorrido % 1400) / 1400
        tamanho = trilho.width() * 0.45
        x = trilho.left() - tamanho + fase * (trilho.width() + tamanho)
        total = sum(marca_visual.PROPORCOES_FAIXA)
        for cor, peso in zip(marca_visual.CORES_FAIXA, marca_visual.PROPORCOES_FAIXA):
            pedaco = tamanho * peso / total
            pintor.fillRect(QRectF(x, trilho.top(), pedaco, trilho.height()), QColor(cor))
            x += pedaco
        pintor.restore()


_ativa = threading.local()


def esperar(origem: QWidget, funcao: Callable[[], T], texto: str = "Carregando…") -> T:
    """Roda `funcao` numa thread; demorando, mostra a tela de espera.

    Só para trabalho sem tela (banco, rede). Erro lá dentro volta aqui, como
    se a função tivesse sido chamada direto.
    """
    janela = origem.window() if origem is not None else None
    if janela is None or not janela.isVisible() or getattr(_ativa, "valor", False):
        return funcao()

    resultado: dict = {}

    def rodar() -> None:
        try:
            resultado["valor"] = funcao()
        except BaseException as erro:  # noqa: BLE001 - devolve para quem chamou
            resultado["erro"] = erro

    _ativa.valor = True
    tela: TelaCarregando | None = None
    mostrada_em = 0.0
    try:
        linha = threading.Thread(target=rodar, daemon=True)
        linha.start()
        linha.join(ATRASO_S)
        while linha.is_alive():
            if tela is None:
                tela = TelaCarregando(janela, texto)
                mostrada_em = time.monotonic()
            QApplication.processEvents()
            linha.join(0.016)
        if tela is not None:
            while time.monotonic() - mostrada_em < MINIMO_S:
                QApplication.processEvents()
                time.sleep(0.016)
    finally:
        if tela is not None:
            tela.encerrar()
        _ativa.valor = False
    if "erro" in resultado:
        raise resultado["erro"]
    return resultado.get("valor")
