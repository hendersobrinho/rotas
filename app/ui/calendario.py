"""Calendário mensal: cada dia mostra quem tem serviço marcado, não só quantos."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models import Evento, StatusEvento, TipoServico
from app.ui.datas import DIAS_SEMANA, primeiro_dia_da_grade, titulo_mes
from app.ui.estilo import (
    COR_STATUS,
    CORES,
    FONTE_DADOS,
    cores_da_etiqueta,
    cores_no_calendario,
    glifo_da_etiqueta,
    marcar,
)
from app.ui.widgets import rotulo

LINHAS = 6
MAX_ETIQUETAS = 3


class TextoElidido(QLabel):
    """QLabel que corta o próprio texto com reticências quando falta largura."""

    def __init__(self, texto: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._texto = texto
        self.setMinimumWidth(16)
        self._reescrever()

    def definir_texto(self, texto: str) -> None:
        self._texto = texto
        self._reescrever()

    def resizeEvent(self, evento) -> None:  # noqa: N802 (API do Qt)
        super().resizeEvent(evento)
        self._reescrever()

    def _reescrever(self) -> None:
        metricas = QFontMetrics(self.font())
        disponivel = max(16, self.width() - 12)
        super().setText(
            metricas.elidedText(self._texto, Qt.TextElideMode.ElideRight, disponivel)
        )


class CelulaDia(QFrame):
    """Um quadradinho do mês: número do dia e as etiquetas dos serviços."""

    aberto = Signal(date)

    def __init__(self, ultima_coluna: bool, ultima_linha: bool, parent=None) -> None:
        super().__init__(parent)
        self._ultima_coluna = ultima_coluna
        self._ultima_linha = ultima_linha
        self._dia: date | None = None
        self._do_mes = True
        self._hoje = False
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(102)

        self._numero = QLabel()
        self._numero.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._numero.setFixedSize(24, 22)

        # Selo no canto: dia que passou com algo sem baixa (âmbar, com a
        # contagem) ou dia com tudo baixado (✓ verde).
        self._selo = QLabel()
        self._selo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._selo.setFixedHeight(18)
        self._selo.hide()

        topo = QHBoxLayout()
        topo.setContentsMargins(0, 0, 0, 0)
        topo.addWidget(self._numero)
        topo.addStretch(1)
        topo.addWidget(self._selo)

        self._etiquetas = [TextoElidido() for _ in range(MAX_ETIQUETAS)]
        self._extra = QLabel()
        self._extra.setStyleSheet(
            f"color: {CORES['tinta_fraca']}; font-size: 11px; padding-left: 2px;"
        )

        coluna = QVBoxLayout(self)
        coluna.setContentsMargins(8, 7, 8, 7)
        coluna.setSpacing(3)
        coluna.addLayout(topo)
        for etiqueta in self._etiquetas:
            coluna.addWidget(etiqueta)
        coluna.addWidget(self._extra)
        coluna.addStretch(1)

    def definir(self, dia: date, do_mes: bool, hoje: bool, eventos: list[Evento]) -> None:
        self._dia = dia
        self._do_mes = do_mes
        self._hoje = hoje
        self._numero.setText(str(dia.day))
        self._pintar_numero()
        self._pintar_fundo(False)

        # O que está em aberto vem primeiro: é o que precisa de atenção, e
        # não pode ficar escondido no "+N" atrás do que já teve baixa.
        eventos = sorted(
            eventos, key=lambda e: (e.status is not StatusEvento.PENDENTE,)
        )
        abertos = sum(1 for e in eventos if e.status is StatusEvento.PENDENTE)
        self._pintar_selo(dia, abertos, len(eventos))

        visiveis = eventos[:MAX_ETIQUETAS]
        for etiqueta, evento in zip(self._etiquetas, visiveis):
            # Em aberto: cor do tipo de serviço. Baixado: verde com ✓.
            # Não realizado: vermelho com ✕. Cancelado: cinza riscado.
            cor, fundo, glifo = cores_no_calendario(evento)
            cancelado = evento.status is StatusEvento.CANCELADO
            aberto = evento.status is StatusEvento.PENDENTE
            etiqueta.setStyleSheet(
                f"background: {fundo}; color: {cor}; border-radius: 5px;"
                "padding: 2px 6px; font-size: 11px;"
                f"font-weight: {600 if aberto else 500};"
            )
            fonte = etiqueta.font()
            fonte.setStrikeOut(cancelado)
            etiqueta.setFont(fonte)
            etiqueta.definir_texto(f"{glifo}  {evento.cliente.nome_exibicao}")
            etiqueta.setToolTip(
                f"{evento.tipo_servico.nome} · {evento.cliente.nome_exibicao}"
                f" · {evento.status.value}"
            )
            etiqueta.setVisible(True)
        for etiqueta in self._etiquetas[len(visiveis):]:
            etiqueta.setVisible(False)

        restantes = len(eventos) - len(visiveis)
        self._extra.setText(f"+{restantes}" if restantes > 0 else "")
        self._extra.setVisible(restantes > 0)

    def _pintar_selo(self, dia: date, abertos: int, total: int) -> None:
        base = (
            "border-radius: 9px; padding: 0 6px; font-size: 10px; font-weight: 700;"
            f'font-family: "{FONTE_DADOS}";'
        )
        if abertos and dia < date.today():
            self._selo.setText(f"● {abertos}")
            self._selo.setToolTip(f"{abertos} serviço(s) deste dia ainda sem baixa")
            self._selo.setStyleSheet(
                f"background: {CORES['laranja_claro']}; color: {CORES['carimbo']};"
                + base
            )
            self._selo.show()
        elif total and not abertos:
            self._selo.setText("✓")
            self._selo.setToolTip("Tudo deste dia já teve baixa")
            self._selo.setStyleSheet(
                f"background: {CORES['verde_claro']}; color: {CORES['verde']};" + base
            )
            self._selo.show()
        else:
            self._selo.hide()

    def _pintar_numero(self) -> None:
        if self._hoje:
            estilo = (
                f"background: {CORES['marca']}; color: {CORES['sobre_marca']}; border-radius: 11px;"
            )
        elif self._do_mes:
            estilo = f"background: transparent; color: {CORES['tinta']};"
        else:
            estilo = f"background: transparent; color: {CORES['tinta_fraca']};"
        self._numero.setStyleSheet(
            f'{estilo} font-family: "{FONTE_DADOS}"; font-size: 12px; font-weight: 600;'
        )

    def _pintar_fundo(self, sobre: bool) -> None:
        if sobre:
            fundo = CORES["azul_claro"]
        elif self._do_mes:
            fundo = CORES["papel"]
        else:
            fundo = CORES["papel_suave"]
        direita = "none" if self._ultima_coluna else f"1px solid {CORES['pauta']}"
        baixo = "none" if self._ultima_linha else f"1px solid {CORES['pauta']}"
        self.setStyleSheet(
            f"CelulaDia {{ background: {fundo}; border: none;"
            f" border-right: {direita}; border-bottom: {baixo}; }}"
        )

    def enterEvent(self, evento) -> None:  # noqa: N802
        super().enterEvent(evento)
        self._pintar_fundo(True)

    def leaveEvent(self, evento) -> None:  # noqa: N802
        super().leaveEvent(evento)
        self._pintar_fundo(False)

    def mouseReleaseEvent(self, evento) -> None:  # noqa: N802
        super().mouseReleaseEvent(evento)
        if self._dia is not None and evento.button() == Qt.MouseButton.LeftButton:
            self.aberto.emit(self._dia)


class CalendarioMensal(QWidget):
    """Grade do mês inteiro; clicar num dia entra nele."""

    dia_aberto = Signal(date)
    mes_mudou = Signal(date, date)  # primeiro e último dia visíveis na grade

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        hoje = date.today()
        self._mes = hoje.replace(day=1)

        self._titulo = QLabel()
        marcar(self._titulo, papel="titulo")
        self._resumo = rotulo("", "fraco")

        anterior = QPushButton("‹")
        proximo = QPushButton("›")
        for botao in (anterior, proximo):
            botao.setFixedWidth(34)
            marcar(botao, variante="fantasma")
            botao.setStyleSheet("font-size: 18px;")
        anterior.clicked.connect(lambda: self._andar(-1))
        proximo.clicked.connect(lambda: self._andar(1))

        botao_hoje = QPushButton("Hoje")
        botao_hoje.clicked.connect(self.ir_para_hoje)

        # Primeira linha: o mês, a navegação e as ações; segunda: a legenda
        # e o resumo, que numa linha só ficavam espremidos.
        topo = QHBoxLayout()
        topo.setSpacing(6)
        topo.addWidget(self._titulo)
        topo.addSpacing(8)
        topo.addWidget(anterior)
        topo.addWidget(proximo)
        topo.addWidget(botao_hoje)
        topo.addStretch(1)
        self._acoes = QHBoxLayout()
        self._acoes.setSpacing(8)
        topo.addLayout(self._acoes)

        linha_legenda = QHBoxLayout()
        linha_legenda.setSpacing(6)
        linha_legenda.addWidget(self._legenda())
        linha_legenda.addStretch(1)
        linha_legenda.addWidget(self._resumo)

        cabecalho = QVBoxLayout()
        cabecalho.setSpacing(10)
        cabecalho.addLayout(topo)
        cabecalho.addLayout(linha_legenda)

        folha = QFrame()  # a "folha" branca do mês
        marcar(folha, cartao=True)
        folha_layout = QVBoxLayout(folha)
        folha_layout.setContentsMargins(1, 0, 1, 1)
        folha_layout.setSpacing(0)

        faixa = QHBoxLayout()
        faixa.setContentsMargins(0, 8, 0, 8)
        faixa.setSpacing(0)
        for nome in DIAS_SEMANA:
            dia = QLabel(nome.upper())
            dia.setAlignment(
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            )
            dia.setContentsMargins(10, 0, 0, 0)
            marcar(dia, papel="etiqueta")
            faixa.addWidget(dia, 1)
        folha_layout.addLayout(faixa)

        separador = QFrame()
        separador.setFixedHeight(1)
        separador.setStyleSheet(f"background: {CORES['pauta']};")
        folha_layout.addWidget(separador)

        grade = QGridLayout()
        grade.setContentsMargins(0, 0, 0, 0)
        grade.setSpacing(0)
        self._grade = grade
        self._linhas: list[list[CelulaDia]] = []
        for linha in range(LINHAS):
            celulas_da_linha = []
            for coluna in range(7):
                celula = CelulaDia(coluna == 6, linha == LINHAS - 1)
                celula.aberto.connect(self.dia_aberto)
                grade.addWidget(celula, linha, coluna)
                grade.setColumnStretch(coluna, 1)
                celulas_da_linha.append(celula)
            grade.setRowStretch(linha, 1)
            self._linhas.append(celulas_da_linha)
        self._celulas = [c for linha in self._linhas for c in linha]
        folha_layout.addLayout(grade)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addLayout(cabecalho)
        layout.addWidget(folha)

        self._eventos: dict[date, list[Evento]] = {}
        self._desenhar()

    def _legenda(self) -> QWidget:
        caixa = QWidget()
        self._legenda_layout = QHBoxLayout(caixa)
        self._legenda_layout.setContentsMargins(0, 0, 0, 0)
        self._legenda_layout.setSpacing(14)
        return caixa

    def definir_legenda(self, tipos: list[TipoServico]) -> None:
        """A legenda é montada a partir dos tipos de serviço cadastrados."""
        while self._legenda_layout.count():
            item = self._legenda_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        for tipo in tipos:
            cor, _ = cores_da_etiqueta(tipo.estilo)
            etiqueta = QLabel(
                f'<span style="color:{cor}">{glifo_da_etiqueta(tipo.estilo)}</span>'
                f"&nbsp;{tipo.nome}"
            )
            marcar(etiqueta, papel="fraco")
            self._legenda_layout.addWidget(etiqueta)
        # As cores do tipo só valem para o que está em aberto; o resto
        # aparece com a cor da situação.
        divisor = QFrame()
        divisor.setFixedSize(1, 14)
        divisor.setStyleSheet(f"background: {CORES['pauta_forte']};")
        self._legenda_layout.addWidget(divisor)
        for status, texto in (
            (StatusEvento.CONCLUIDO, "Baixado"),
            (StatusEvento.NAO_REALIZADO, "Não realizado"),
        ):
            cor, fundo = COR_STATUS[status]
            glifo = "✓" if status is StatusEvento.CONCLUIDO else "✕"
            etiqueta = QLabel(
                f'<span style="color:{cor}; background:{fundo};">&nbsp;{glifo}&nbsp;</span>'
                f"&nbsp;{texto}"
            )
            marcar(etiqueta, papel="fraco")
            self._legenda_layout.addWidget(etiqueta)

    def adicionar_acao(self, botao: QWidget) -> None:
        """Botões extras ao lado da navegação do mês."""
        self._acoes.addWidget(botao)

    # ---------------------------------------------------------------- estado
    @property
    def mes(self) -> date:
        return self._mes

    def intervalo_visivel(self) -> tuple[date, date]:
        inicio = primeiro_dia_da_grade(self._mes)
        return inicio, inicio + timedelta(days=LINHAS * 7 - 1)

    def definir_eventos(self, eventos: list[Evento]) -> None:
        agrupados: dict[date, list[Evento]] = {}
        for evento in eventos:
            agrupados.setdefault(evento.data, []).append(evento)
        for lista in agrupados.values():
            lista.sort(key=lambda e: (e.periodo.name, e.id))
        self._eventos = agrupados
        self._desenhar_celulas()
        self._atualizar_resumo()

    def ir_para_hoje(self) -> None:
        self.ir_para(date.today())

    def ir_para(self, dia: date) -> None:
        novo = dia.replace(day=1)
        if novo != self._mes:
            self._mes = novo
            self._desenhar()
        else:
            self._avisar_periodo()

    def _andar(self, meses: int) -> None:
        mes = self._mes.month + meses
        ano = self._mes.year + (mes - 1) // 12
        self._mes = date(ano, (mes - 1) % 12 + 1, 1)
        self._desenhar()

    # -------------------------------------------------------------- desenho
    def _desenhar(self) -> None:
        self._titulo.setText(titulo_mes(self._mes))
        self._desenhar_celulas()
        self._atualizar_resumo()
        self._avisar_periodo()

    def _avisar_periodo(self) -> None:
        inicio, fim = self.intervalo_visivel()
        self.mes_mudou.emit(inicio, fim)

    def _desenhar_celulas(self) -> None:
        inicio = primeiro_dia_da_grade(self._mes)
        hoje = date.today()
        for numero, linha in enumerate(self._linhas):
            dias = [inicio + timedelta(days=numero * 7 + i) for i in range(7)]
            # Semana inteira fora do mês não ocupa espaço na folha.
            vazia = all(dia.month != self._mes.month for dia in dias)
            self._grade.setRowStretch(numero, 0 if vazia else 1)
            for celula, dia in zip(linha, dias):
                celula.setVisible(not vazia)
                if vazia:
                    continue
                celula.definir(
                    dia,
                    do_mes=dia.month == self._mes.month,
                    hoje=dia == hoje,
                    eventos=self._eventos.get(dia, []),
                )

    def _atualizar_resumo(self) -> None:
        _, ultimo = monthrange(self._mes.year, self._mes.month)
        primeiro_dia = self._mes
        ultimo_dia = self._mes.replace(day=ultimo)
        do_mes = [
            evento
            for dia, lista in self._eventos.items()
            if primeiro_dia <= dia <= ultimo_dia
            for evento in lista
        ]
        if not do_mes:
            self._resumo.setText("Nenhum serviço neste mês")
            return
        pendentes = sum(1 for e in do_mes if e.status is StatusEvento.PENDENTE)
        baixados = sum(1 for e in do_mes if e.status is StatusEvento.CONCLUIDO)
        texto = f"{len(do_mes)} serviço(s) no mês"
        if pendentes:
            texto += f" · {pendentes} em aberto"
        if baixados:
            texto += f" · {baixados} baixado(s)"
        self._resumo.setText(texto)
