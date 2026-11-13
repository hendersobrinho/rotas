"""Telas da atualização automática (a lógica está em app/atualizacao.py).

Ao abrir o sistema, uma consulta rápida ao GitHub roda em segundo plano — sem
travar nada e sem barulho se não houver internet. Havendo versão nova, o botão
"Atualização disponível" aparece na barra lateral; o clique abre a janela com
as notas da release e, com o "Atualizar agora", o instalador é baixado (com
barra de progresso), conferido e executado. O programa fecha para ele trocar
os arquivos e abrir de novo.
"""

from __future__ import annotations

import threading

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app import __version__
from app import atualizacao as nucleo
from app.atualizacao import Atualizacao, ErroDeAtualizacao
from app.ui.estilo import CORES, marcar
from app.ui.widgets import rotulo


def _em_segundo_plano(funcao) -> dict:
    """Roda `funcao` numa thread; o dicionário ganha "pronto", "resultado"
    ou "erro" (lido por quem consulta de tempos em tempos)."""
    estado: dict = {"pronto": False, "resultado": None, "erro": None}

    def rodar() -> None:
        try:
            estado["resultado"] = funcao()
        except Exception as erro:  # noqa: BLE001 - vira mensagem, não derruba
            estado["erro"] = erro
        estado["pronto"] = True

    threading.Thread(target=rodar, daemon=True).start()
    return estado


class DialogoAtualizacao(QDialog):
    """Mostra a versão nova e, com o "sim", baixa e executa o instalador."""

    def __init__(
        self, nova: Atualizacao, parent: QWidget | None = None,
        versao_instalada: str = __version__,
    ) -> None:
        super().__init__(parent)
        self.nova = nova
        self._baixando: dict | None = None
        self._cancelar = False
        self.setWindowTitle("Nova versão disponível")
        self.setMinimumWidth(520)
        self.setStyleSheet(f"QDialog {{ background: {CORES['papel']}; }}")

        selo = QLabel(f"VERSÃO {nova.versao}")
        selo.setStyleSheet(
            f"background: {CORES['laranja_claro']}; color: {CORES['carimbo']};"
            "border-radius: 6px; padding: 3px 8px; font-size: 11px; font-weight: 700;"
        )

        self.notas = QTextBrowser()
        self.notas.setOpenExternalLinks(True)
        self.notas.setMarkdown(nova.notas)
        self.notas.setMinimumHeight(150)
        self.notas.setStyleSheet(
            f"QTextBrowser {{ background: {CORES['papel_suave']};"
            f" border: 1px solid {CORES['pauta']}; border-radius: 10px; padding: 8px; }}"
        )
        self.notas.setVisible(bool(nova.notas))

        aviso = rotulo(
            "Ao atualizar, o programa fecha e abre sozinho em seguida. "
            "Seus dados ficam no banco e não são alterados.",
            "fraco",
        )
        aviso.setWordWrap(True)

        self.andamento = rotulo("", "fraco")
        self.andamento.hide()
        self.barra = QProgressBar()
        self.barra.setFixedHeight(8)
        self.barra.hide()

        self.btn_depois = QPushButton("Depois")
        self.btn_depois.clicked.connect(self._depois)
        self.btn_atualizar = QPushButton("Atualizar agora")
        marcar(self.btn_atualizar, variante="primario")
        self.btn_atualizar.setDefault(True)
        self.btn_atualizar.clicked.connect(self._atualizar)

        botoes = QHBoxLayout()
        botoes.addStretch()
        botoes.addWidget(self.btn_depois)
        botoes.addWidget(self.btn_atualizar)

        topo = QHBoxLayout()
        topo.addWidget(rotulo("Há uma versão nova do Rotas", "titulo"))
        topo.addStretch(1)
        topo.addWidget(selo)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 20)
        layout.setSpacing(12)
        layout.addLayout(topo)
        layout.addWidget(rotulo(f"Você está na versão {versao_instalada}.", "fraco"))
        layout.addWidget(self.notas)
        layout.addWidget(aviso)
        layout.addWidget(self.andamento)
        layout.addWidget(self.barra)
        layout.addLayout(botoes)

        self._timer = QTimer(self)
        self._timer.setInterval(100)
        self._timer.timeout.connect(self._acompanhar)

    def _depois(self) -> None:
        if self._baixando is not None:
            self._cancelar = True  # a thread para no próximo pedaço
            self.btn_depois.setEnabled(False)
            self.andamento.setText("Cancelando…")
            return
        self.reject()

    def _atualizar(self) -> None:
        self.btn_atualizar.setEnabled(False)
        self.btn_depois.setText("Cancelar")
        self.andamento.setText("Baixando a atualização…")
        self.andamento.show()
        self.barra.setRange(0, 0)  # indefinida até saber o tamanho
        self.barra.show()
        self._cancelar = False
        progresso = {"baixado": 0, "total": self.nova.tamanho}

        def ao_baixar(baixado: int, total: int) -> None:
            progresso["baixado"], progresso["total"] = baixado, total

        self._baixando = _em_segundo_plano(
            lambda: nucleo.baixar(
                self.nova, progresso=ao_baixar, cancelado=lambda: self._cancelar
            )
        )
        self._baixando["progresso"] = progresso
        self._timer.start()

    def _acompanhar(self) -> None:
        tarefa = self._baixando
        if tarefa is None:
            return
        baixado, total = tarefa["progresso"]["baixado"], tarefa["progresso"]["total"]
        if total:
            self.barra.setRange(0, 1000)
            self.barra.setValue(int(1000 * min(baixado, total) / total))
            self.andamento.setText(
                f"Baixando a atualização…  {baixado / 1_048_576:.0f} de "
                f"{total / 1_048_576:.0f} MB"
            )
        if not tarefa["pronto"]:
            return
        self._timer.stop()
        self._baixando = None
        if tarefa["erro"] is not None:
            self._falhou(tarefa["erro"])
            return
        self.andamento.setText("Abrindo o instalador…")
        try:
            nucleo.executar_instalador(tarefa["resultado"])
        except ErroDeAtualizacao as erro:
            self._falhou(erro)
            return
        # O instalador assume daqui: fecha o programa inteiro para trocar os arquivos.
        self.accept()
        QApplication.quit()

    def _falhou(self, erro: Exception) -> None:
        cancelou = self._cancelar
        self._cancelar = False
        self.barra.hide()
        self.andamento.hide()
        self.btn_atualizar.setEnabled(True)
        self.btn_depois.setEnabled(True)
        self.btn_depois.setText("Depois")
        if cancelou:
            return
        QMessageBox.warning(
            self, "Não foi possível atualizar",
            f"{erro}\n\nO programa continua como estava. Tente de novo mais "
            f"tarde, ou baixe o instalador em {nucleo.URL_RELEASES}.",
        )

    def reject(self) -> None:
        if self._baixando is not None:
            self._depois()
            return
        super().reject()


class VerificadorDeAtualizacao(QObject):
    """Consulta o GitHub sem travar a tela.

    `encontrou` avisa a barra lateral para mostrar o botão. Com
    `verificar(manual=True)` — o clique da pessoa — a resposta vem também
    quando não há nada novo ou quando não deu para consultar.
    """

    encontrou = Signal(object)  # Atualizacao

    def __init__(self, janela: QWidget) -> None:
        super().__init__(janela)
        self._janela = janela
        self._consulta: dict | None = None
        self._manual = False
        self.disponivel: Atualizacao | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._acompanhar)

    def verificar(self, manual: bool = False) -> None:
        if self._consulta is not None:
            self._manual = self._manual or manual
            return
        self._manual = manual
        self._consulta = _em_segundo_plano(nucleo.procurar)
        self._timer.start()

    def abrir(self) -> None:
        """O clique no botão da barra lateral."""
        if self.disponivel is not None:
            DialogoAtualizacao(self.disponivel, self._janela).exec()
        else:
            self.verificar(manual=True)

    def _acompanhar(self) -> None:
        consulta = self._consulta
        if consulta is None or not consulta["pronto"]:
            return
        self._timer.stop()
        self._consulta = None
        if consulta["erro"] is not None:
            if self._manual:
                QMessageBox.information(
                    self._janela, "Atualização",
                    f"Não consegui verificar agora: {consulta['erro']}\n"
                    "Confira a internet e tente de novo.",
                )
            return
        nova = consulta["resultado"]
        if nova is not None:
            self.disponivel = nova
            self.encontrou.emit(nova)
            if self._manual:
                DialogoAtualizacao(nova, self._janela).exec()
        elif self._manual:
            QMessageBox.information(
                self._janela, "Atualização",
                f"Você já está na versão mais nova ({__version__}).",
            )
