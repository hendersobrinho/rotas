"""Aba de serviços: calendário do mês e, ao clicar num dia, a agenda do dia."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.db import session_scope
from app.models import Cliente, Evento, Periodo, StatusEvento
from app.repository import clientes as repo_clientes
from app.repository import eventos as repo_eventos
from app.repository import tipos_servico as repo_tipos
from app.schemas import FiltroEventos
from app.ui.calendario import CalendarioMensal
from app.ui.datas import data_por_extenso
from app.ui.estilo import (
    COR_STATUS,
    CORES,
    ROTULO_PERIODO,
    cores_da_etiqueta,
    marcar,
)
from app.ui.evento_dialog import EventoDialog
from app.ui.mensagens import mostrar_erro
from app.ui.relatorio_pdf import RelatorioDialog
from app.ui.widgets import Etiqueta, cartao, rotulo


def _limpar(layout: QLayout) -> None:
    """Esvazia o layout de verdade: sem setParent(None) o widget antigo
    continua desenhado até o Qt processar o deleteLater()."""
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()


class LinhaEvento(QFrame):
    """Um serviço na folha do dia, pautado como numa agenda de papel."""

    escolhido = Signal(int)
    baixa_pedida = Signal(int, object)  # id do serviço, situação nova

    def __init__(self, evento: Evento, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._evento_id = evento.id
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._pintar(CORES["papel"])

        cor_servico, _ = cores_da_etiqueta(evento.tipo_servico.estilo)
        cancelado = evento.status is StatusEvento.CANCELADO
        if cancelado:
            cor_servico = CORES["tinta_fraca"]

        faixa = QFrame()
        faixa.setFixedWidth(3)
        faixa.setStyleSheet(f"background: {cor_servico}; border-radius: 2px;")

        servico = QLabel(evento.tipo_servico.nome)
        servico.setStyleSheet(
            f"color: {cor_servico}; font-weight: 600; font-size: 13px;"
        )
        cliente = QLabel(evento.cliente.nome_exibicao)
        cliente.setStyleSheet(
            f"color: {CORES['tinta_fraca'] if cancelado else CORES['tinta']};"
            "font-weight: 600; font-size: 13px;"
        )

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(6)
        cabecalho.addWidget(servico)
        cabecalho.addWidget(rotulo("·", "fraco"))
        cabecalho.addWidget(cliente)
        cabecalho.addStretch(1)

        cor, fundo = COR_STATUS[evento.status]
        etiqueta = Etiqueta()
        etiqueta.definir(evento.status.value, cor, fundo, riscado=cancelado)
        cabecalho.addWidget(etiqueta)

        detalhes = [
            f"{evento.endereco.tipo.value}: {evento.endereco.resumo()}"
            if evento.endereco is not None
            else "Endereço não informado"
        ]
        if evento.solicitante is not None:
            detalhes.append(f"Pedido por {evento.solicitante.nome_exibicao}")
        texto = QLabel(" · ".join(detalhes))
        texto.setWordWrap(True)
        marcar(texto, papel="fraco")

        coluna = QVBoxLayout()
        coluna.setSpacing(3)
        coluna.addLayout(cabecalho)
        coluna.addWidget(texto)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 14, 12)
        layout.setSpacing(12)
        layout.addWidget(faixa)
        layout.addLayout(coluna)
        layout.addWidget(
            self._botao_baixa(evento), 0, Qt.AlignmentFlag.AlignVCenter
        )

    def _botao_baixa(self, evento: Evento) -> QPushButton:
        """Baixa num clique: encaixado na borda de fora da linha."""
        pendente = evento.status is StatusEvento.PENDENTE
        botao = QPushButton("✓" if pendente else "↺")
        botao.setFixedSize(34, 34)
        botao.setCursor(Qt.CursorShape.PointingHandCursor)
        if pendente:
            botao.setToolTip("Dar baixa — marcar como concluído")
            novo = StatusEvento.CONCLUIDO
            estilo = (
                f"background: {CORES['verde_claro']}; color: {CORES['verde']};"
                f"border: 1px solid #C6E4D4;"
            )
            passagem = f"background: {CORES['verde']}; color: #FFFFFF;"
        else:
            botao.setToolTip("Voltar para pendente")
            novo = StatusEvento.PENDENTE
            estilo = (
                f"background: {CORES['papel_suave']}; color: {CORES['tinta_fraca']};"
                f"border: 1px solid {CORES['pauta']};"
            )
            passagem = f"background: {CORES['cinza_claro']}; color: {CORES['tinta']};"
        botao.setStyleSheet(
            f"QPushButton {{ {estilo} border-radius: 17px; font-size: 15px;"
            " font-weight: 600; padding: 0; }"
            f"QPushButton:hover {{ {passagem} border-radius: 17px; }}"
        )
        botao.clicked.connect(lambda: self.baixa_pedida.emit(self._evento_id, novo))
        return botao

    def _pintar(self, fundo: str) -> None:
        self.setStyleSheet(
            f"LinhaEvento {{ background: {fundo}; border: none;"
            f" border-bottom: 1px solid {CORES['pauta']}; }}"
        )

    def enterEvent(self, evento) -> None:  # noqa: N802
        super().enterEvent(evento)
        self._pintar(CORES["azul_claro"])

    def leaveEvent(self, evento) -> None:  # noqa: N802
        super().leaveEvent(evento)
        self._pintar(CORES["papel"])

    def mouseReleaseEvent(self, evento) -> None:  # noqa: N802
        super().mouseReleaseEvent(evento)
        if evento.button() == Qt.MouseButton.LeftButton:
            self.escolhido.emit(self._evento_id)


class EventosTab(QWidget):
    """Mês inteiro numa página; o dia escolhido na outra."""

    dados_alterados = Signal()

    PAGINA_MES = 0
    PAGINA_DIA = 1

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._clientes: list[Cliente] = []
        self._dia: date | None = None
        self._periodo: tuple[date, date] | None = None

        self.pilha = QStackedWidget()
        self.pilha.addWidget(self._montar_mes())
        self.pilha.addWidget(self._montar_dia())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 10, 18, 18)
        layout.addWidget(self.pilha)

        self.recarregar_clientes()
        self.recarregar()

    # ------------------------------------------------------------------ mês
    def _montar_mes(self) -> QWidget:
        self.calendario = CalendarioMensal()
        self.calendario.dia_aberto.connect(self.abrir_dia)
        self.calendario.mes_mudou.connect(self._carregar_periodo)

        pdf = QPushButton("Emitir PDF")
        pdf.clicked.connect(lambda: self._emitir_pdf(None))
        self.calendario.adicionar_acao(pdf)

        pagina = QWidget()
        layout = QVBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.calendario)
        return pagina

    # ------------------------------------------------------------------ dia
    def _montar_dia(self) -> QWidget:
        voltar = QPushButton("‹  Voltar ao mês")
        marcar(voltar, variante="fantasma")
        voltar.clicked.connect(self.voltar_ao_mes)

        self.titulo_dia = QLabel()
        marcar(self.titulo_dia, papel="titulo")
        self.resumo_dia = rotulo("", "fraco")

        pdf = QPushButton("Emitir PDF")
        pdf.clicked.connect(lambda: self._emitir_pdf(self._dia))

        novo = QPushButton("Incluir serviço")
        marcar(novo, variante="primario")
        novo.clicked.connect(self._novo)

        textos = QVBoxLayout()
        textos.setSpacing(2)
        textos.addWidget(self.titulo_dia)
        textos.addWidget(self.resumo_dia)

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(12)
        cabecalho.addLayout(textos)
        cabecalho.addStretch(1)
        cabecalho.addWidget(pdf, 0, Qt.AlignmentFlag.AlignVCenter)
        cabecalho.addWidget(novo, 0, Qt.AlignmentFlag.AlignVCenter)

        self.faixas: dict[Periodo, QVBoxLayout] = {}
        folha = cartao()
        folha_layout = QVBoxLayout(folha)
        folha_layout.setContentsMargins(0, 0, 0, 10)
        folha_layout.setSpacing(0)
        for periodo in Periodo:
            titulo = QLabel(ROTULO_PERIODO[periodo])
            marcar(titulo, papel="etiqueta")
            titulo.setContentsMargins(16, 14, 16, 6)
            folha_layout.addWidget(titulo)
            lista = QVBoxLayout()
            lista.setSpacing(0)
            folha_layout.addLayout(lista)
            self.faixas[periodo] = lista

        corpo = QWidget()
        corpo_layout = QVBoxLayout(corpo)
        corpo_layout.setContentsMargins(0, 0, 8, 0)
        corpo_layout.setSpacing(0)
        corpo_layout.addWidget(folha)
        corpo_layout.addStretch(1)

        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setWidget(corpo)

        coluna_central = QWidget()
        coluna_central.setMaximumWidth(880)
        interno = QVBoxLayout(coluna_central)
        interno.setContentsMargins(0, 0, 0, 0)
        interno.setSpacing(14)
        interno.addWidget(voltar, 0, Qt.AlignmentFlag.AlignLeft)
        interno.addLayout(cabecalho)
        interno.addWidget(rolagem)

        pagina = QWidget()
        layout = QHBoxLayout(pagina)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch(1)
        layout.addWidget(coluna_central, 6)
        layout.addStretch(1)
        return pagina

    # ---------------------------------------------------------------- dados
    def recarregar_clientes(self) -> None:
        """Relê clientes e tipos de serviço — a legenda do mês sai dos tipos."""
        try:
            with session_scope() as sessao:
                self._clientes = repo_clientes.listar_clientes(sessao)
                tipos = repo_tipos.listar(sessao, apenas_ativos=True)
        except Exception as erro:
            mostrar_erro(self, erro, "Erro ao carregar clientes e tipos")
            return
        self.calendario.definir_legenda(tipos)

    def recarregar(self) -> None:
        """Relê o mês visível e, se estiver dentro de um dia, relê o dia."""
        if self._periodo is None:
            inicio, fim = self.calendario.intervalo_visivel()
            self._periodo = (inicio, fim)
        self._carregar_periodo(*self._periodo)
        if self._dia is not None and self.pilha.currentIndex() == self.PAGINA_DIA:
            self._desenhar_dia()

    def _carregar_periodo(self, inicio: date, fim: date) -> None:
        self._periodo = (inicio, fim)
        try:
            with session_scope() as sessao:
                eventos = repo_eventos.listar_eventos(
                    sessao, FiltroEventos(data_inicio=inicio, data_fim=fim)
                )
        except Exception as erro:
            mostrar_erro(self, erro, "Erro ao carregar o mês")
            return
        self.calendario.definir_eventos(eventos)

    def _eventos_do_dia(self) -> list[Evento]:
        if self._dia is None:
            return []
        with session_scope() as sessao:
            return repo_eventos.listar_eventos(
                sessao, FiltroEventos(data_inicio=self._dia, data_fim=self._dia)
            )

    # ---------------------------------------------------------------- ações
    def abrir_dia(self, dia: date) -> None:
        self._dia = dia
        self.calendario.ir_para(dia)
        self._desenhar_dia()
        self.pilha.setCurrentIndex(self.PAGINA_DIA)

    def voltar_ao_mes(self) -> None:
        self.pilha.setCurrentIndex(self.PAGINA_MES)

    def _desenhar_dia(self) -> None:
        if self._dia is None:
            return
        try:
            eventos = self._eventos_do_dia()
        except Exception as erro:
            mostrar_erro(self, erro, "Erro ao carregar o dia")
            return

        self.titulo_dia.setText(data_por_extenso(self._dia).capitalize())
        pendentes = sum(1 for e in eventos if e.status is StatusEvento.PENDENTE)
        if eventos:
            resumo = f"{len(eventos)} serviço(s)"
            if pendentes:
                resumo += f" · {pendentes} pendente(s)"
        else:
            resumo = "Nada marcado ainda"
        self.resumo_dia.setText(resumo)

        for periodo, lista in self.faixas.items():
            _limpar(lista)
            do_periodo = [e for e in eventos if e.periodo is periodo]
            if not do_periodo:
                vazio = QLabel("Nada marcado")
                vazio.setStyleSheet(
                    f"color: {CORES['tinta_fraca']}; font-size: 12px;"
                    f"border-bottom: 1px solid {CORES['pauta']};"
                    "padding: 10px 16px 14px 16px;"
                )
                lista.addWidget(vazio)
                continue
            for evento in do_periodo:
                linha = LinhaEvento(evento)
                linha.escolhido.connect(self._editar)
                linha.baixa_pedida.connect(self._mudar_status)
                linha.setSizePolicy(
                    QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed
                )
                lista.addWidget(linha)

    def _novo(self) -> None:
        if not self._clientes:
            mostrar_erro(
                self,
                ValueError("Cadastre um cliente antes de marcar serviços."),
                "Nenhum cliente cadastrado",
            )
            return
        dialogo = EventoDialog(self, self._clientes, dia=self._dia or date.today())
        if dialogo.exec() == EventoDialog.DialogCode.Accepted:
            self._apos_mudanca()

    def _editar(self, evento_id: int) -> None:
        try:
            with session_scope() as sessao:
                evento = repo_eventos.obter_evento(sessao, evento_id)
        except Exception as erro:
            mostrar_erro(self, erro, "Erro ao abrir o serviço")
            return
        if evento is None:
            self.recarregar()
            return
        dialogo = EventoDialog(self, self._clientes, evento=evento)
        if dialogo.exec() == EventoDialog.DialogCode.Accepted:
            self._apos_mudanca()

    def _emitir_pdf(self, dia: date | None) -> None:
        RelatorioDialog(self, dia or date.today()).exec()

    def _mudar_status(self, evento_id: int, novo: StatusEvento) -> None:
        """Baixa rápida, sem abrir o diálogo."""
        try:
            with session_scope() as sessao:
                repo_eventos.alterar_status(sessao, evento_id, novo)
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para mudar a situação")
            return
        self._apos_mudanca()

    def _apos_mudanca(self) -> None:
        self.recarregar()
        self.dados_alterados.emit()
