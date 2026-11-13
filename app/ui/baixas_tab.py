"""Rota e baixas: emitir a rota e acompanhar o que ainda espera confirmação.

Quatro colunas, como num quadro de cartões:

  * Atrasados — dias que já passaram e o serviço continua pendente: ninguém
    confirmou se o motoboy foi. É a coluna que cobra ação.
  * Hoje — o que está na rua agora, para dar baixa ao longo do dia.
  * Não realizados — não deu para fazer e ainda não foi remarcado.
  * Baixados — concluídos nos últimos sete dias, para conferir e desfazer
    algum engano.

O cartão vai de uma coluna para outra arrastando, ou pelos botões dele. No
topo, os filtros (cliente, tipo, período) e o botão de emitir a rota — que
pergunta se os atrasados sem baixa vão junto.
"""

from __future__ import annotations

from datetime import date, timedelta

import enum

from PySide6.QtCore import QMimeData, QPoint, Qt, Signal
from PySide6.QtGui import QDrag, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.db import session_scope
from app.models import Cliente, Evento, Periodo, StatusEvento
from app.repository import clientes as repo_clientes
from app.repository import eventos as repo_eventos
from app.repository import tipos_servico as repo_tipos
from app.ui.calendario import TextoElidido
from app.ui.datas import DIAS_SEMANA, data_por_extenso
from app.ui.estilo import (
    CORES,
    FONTE_DADOS,
    FONTE_TITULO,
    ROTULO_PERIODO,
    cores_da_etiqueta,
    glifo_da_etiqueta,
    marcar,
)
from app.ui.mensagens import confirmar, mostrar_erro
from app.ui.widgets import Segmentado, rotulo

TIPO_MIME = "application/x-rotas-evento"
DIAS_BAIXADOS = 7

ATRASADOS = "atrasados"
HOJE = "hoje"
NAO_REALIZADOS = "nao_realizados"
BAIXADOS = "baixados"

CHAVES = (ATRASADOS, HOJE, NAO_REALIZADOS, BAIXADOS)


def coluna_info(chave: str) -> tuple[str, str, str, str, str]:
    """(título, explicação, cor da faixa, cor do texto, fundo da contagem).

    Lida na hora, e não guardada: as cores mudam com o tema.
    """
    return {
        ATRASADOS: (
            "Atrasados", "Dias que passaram sem baixa",
            CORES["laranja"], CORES["carimbo"], CORES["laranja_claro"],
        ),
        HOJE: (
            "Hoje", "Na rua agora",
            CORES["ciano"], CORES["azul"], CORES["ciano_claro"],
        ),
        NAO_REALIZADOS: (
            "Não realizados", "Sem remarcação",
            CORES["vermelho"], CORES["vermelho"], CORES["vermelho_claro"],
        ),
        BAIXADOS: (
            "Baixados", f"Concluídos nos últimos {DIAS_BAIXADOS} dias",
            CORES["verde"], CORES["verde"], CORES["verde_claro"],
        ),
    }[chave]


class FiltroPeriodo(enum.Enum):
    TODOS = "Dia todo"
    MANHA = "Manhã"
    TARDE = "Tarde"

VAZIO = {
    ATRASADOS: ("Tudo em dia", "Nenhum serviço de dias anteriores esperando baixa."),
    HOJE: ("Nada pendente hoje", "O que for marcado para hoje aparece aqui."),
    NAO_REALIZADOS: ("Nenhuma pendência", "Tudo que não deu certo já foi remarcado."),
    BAIXADOS: ("Nada baixado ainda", "Arraste um cartão para cá para dar baixa."),
}


def _limpar(layout: QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()


def _dia_curto(dia: date) -> str:
    return f"{DIAS_SEMANA[(dia.weekday() + 1) % 7]}, {dia.strftime('%d/%m')}"


def _ha_quanto(dia: date, hoje: date) -> str:
    dias = (hoje - dia).days
    if dias <= 0:
        return ""
    if dias == 1:
        return "ontem"
    return f"há {dias} dias"


class CartaoServico(QFrame):
    """Um serviço no quadro. Arrastável; os botões fazem o mesmo que arrastar."""

    abrir = Signal(int)
    mover = Signal(int, str)  # id do serviço, coluna de destino

    def __init__(self, evento: Evento, coluna: str, hoje: date,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.evento_id = evento.id
        self.coluna = coluna
        self._inicio_arraste: QPoint | None = None
        self.setObjectName("cartaoServico")
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self._pintar(False)

        cor_tipo, fundo_tipo = cores_da_etiqueta(evento.tipo_servico.estilo)
        tipo = QLabel(
            f"{glifo_da_etiqueta(evento.tipo_servico.estilo)}  {evento.tipo_servico.nome}"
        )
        tipo.setStyleSheet(
            f"background: {fundo_tipo}; color: {cor_tipo}; border-radius: 5px;"
            "padding: 2px 7px; font-size: 11px; font-weight: 700;"
        )
        quando = QLabel(
            f"{evento.data.strftime('%d/%m')} · {ROTULO_PERIODO[evento.periodo].lower()}"
        )
        quando.setToolTip(data_por_extenso(evento.data))
        quando.setStyleSheet(
            f'font-family: "{FONTE_DADOS}"; font-size: 11px;'
            f"color: {CORES['tinta_media']};"
        )
        topo = QHBoxLayout()
        topo.setSpacing(6)
        topo.addWidget(tipo)
        topo.addStretch(1)
        topo.addWidget(quando)

        cliente = QLabel(evento.cliente.nome_exibicao)
        cliente.setWordWrap(True)
        cliente.setStyleSheet(
            f"font-size: 13px; font-weight: 700; color: {CORES['tinta']};"
        )

        endereco = TextoElidido(
            f"{evento.endereco.etiqueta_na_tela}: {evento.endereco.resumo()}"
            if evento.endereco is not None
            else "Endereço não informado"
        )
        endereco.setStyleSheet(f"color: {CORES['tinta_media']}; font-size: 11px;")

        coluna_layout = QVBoxLayout(self)
        coluna_layout.setContentsMargins(12, 10, 12, 10)
        coluna_layout.setSpacing(5)
        coluna_layout.addLayout(topo)
        coluna_layout.addWidget(cliente)
        if evento.contato is not None:
            cuidados = TextoElidido(f"A/C {evento.contato.descricao}")
            cuidados.setStyleSheet(
                f"color: {CORES['tinta']}; font-size: 11px; font-weight: 600;"
            )
            coluna_layout.addWidget(cuidados)
        coluna_layout.addWidget(endereco)

        extras: list[str] = []
        if coluna == ATRASADOS:
            atraso = _ha_quanto(evento.data, hoje)
            if atraso:
                extras.append(
                    f'<span style="color:{CORES["carimbo"]}; font-weight:700;">'
                    f"● {atraso}</span>"
                )
        if evento.motivo and coluna == NAO_REALIZADOS:
            extras.append(f"Motivo: {evento.motivo}")
        if evento.solicitante is not None:
            extras.append(f"Pedido por {evento.solicitante.nome_exibicao}")
        if extras:
            detalhe = QLabel(" · ".join(extras))
            detalhe.setWordWrap(True)
            detalhe.setStyleSheet(f"color: {CORES['tinta_media']}; font-size: 11px;")
            coluna_layout.addWidget(detalhe)

        acoes = self._acoes()
        if acoes is not None:
            coluna_layout.addSpacing(2)
            coluna_layout.addLayout(acoes)

    def _botao(self, texto: str, variante: str, destino: str, dica: str) -> QPushButton:
        botao = QPushButton(texto)
        marcar(botao, variante=variante)
        botao.setCursor(Qt.CursorShape.PointingHandCursor)
        botao.setToolTip(dica)
        botao.setStyleSheet("padding: 4px 10px; font-size: 12px;")
        botao.clicked.connect(lambda: self.mover.emit(self.evento_id, destino))
        return botao

    def _acoes(self) -> QHBoxLayout | None:
        linha = QHBoxLayout()
        linha.setSpacing(6)
        if self.coluna in (ATRASADOS, HOJE):
            linha.addWidget(self._botao(
                "✓  Dar baixa", "sucesso", BAIXADOS, "Confirmar que foi feito"
            ))
            linha.addWidget(self._botao(
                "Não deu", "fantasma", NAO_REALIZADOS,
                "Registrar o motivo e, se for o caso, remarcar",
            ))
        elif self.coluna == NAO_REALIZADOS:
            linha.addWidget(self._botao(
                "Remarcar", "alerta", NAO_REALIZADOS, "Escolher um novo dia"
            ))
            linha.addWidget(self._botao(
                "Foi feito", "fantasma", BAIXADOS, "Afinal deu certo: dar baixa"
            ))
        elif self.coluna == BAIXADOS:
            linha.addWidget(self._botao(
                "↺  Desfazer", "fantasma", HOJE, "Voltar para pendente"
            ))
        else:
            return None
        linha.addStretch(1)
        return linha

    def _pintar(self, destaque: bool) -> None:
        borda = CORES["ciano"] if destaque else CORES["pauta"]
        self.setStyleSheet(
            f"QFrame#cartaoServico {{ background: {CORES['papel']};"
            f" border: 1px solid {borda}; border-radius: 10px; }}"
        )

    # ------------------------------------------------------------ arrastar
    def enterEvent(self, evento) -> None:  # noqa: N802
        super().enterEvent(evento)
        self._pintar(True)

    def leaveEvent(self, evento) -> None:  # noqa: N802
        super().leaveEvent(evento)
        self._pintar(False)

    def mousePressEvent(self, evento) -> None:  # noqa: N802
        if evento.button() == Qt.MouseButton.LeftButton:
            self._inicio_arraste = evento.position().toPoint()
        super().mousePressEvent(evento)

    def mouseMoveEvent(self, evento) -> None:  # noqa: N802
        if (
            self._inicio_arraste is None
            or not (evento.buttons() & Qt.MouseButton.LeftButton)
        ):
            return
        distancia = (evento.position().toPoint() - self._inicio_arraste).manhattanLength()
        if distancia < QApplication.startDragDistance():
            return
        self._inicio_arraste = None
        dados = QMimeData()
        dados.setData(TIPO_MIME, f"{self.evento_id}:{self.coluna}".encode())
        arraste = QDrag(self)
        arraste.setMimeData(dados)
        imagem: QPixmap = self.grab()
        arraste.setPixmap(imagem)
        arraste.setHotSpot(evento.position().toPoint())
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        arraste.exec(Qt.DropAction.MoveAction)
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def mouseDoubleClickEvent(self, evento) -> None:  # noqa: N802
        super().mouseDoubleClickEvent(evento)
        self.abrir.emit(self.evento_id)


class ColunaQuadro(QFrame):
    """Uma coluna do quadro: cabeçalho colorido e a pilha de cartões."""

    soltou = Signal(int, str, str)  # id, coluna de origem, coluna de destino

    def __init__(self, chave: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.chave = chave
        titulo, explicacao, cor_faixa, cor_texto, fundo = coluna_info(chave)
        self._cor_faixa = cor_faixa
        self.setObjectName("colunaQuadro")
        self.setAcceptDrops(True)
        self._pintar(False)

        faixa = QFrame()
        faixa.setFixedHeight(4)
        faixa.setStyleSheet(
            f"background: {cor_faixa}; border: none;"
            "border-top-left-radius: 12px; border-top-right-radius: 12px;"
        )

        nome = QLabel(titulo)
        nome.setStyleSheet(
            f'font-family: "{FONTE_TITULO}"; font-size: 14px; font-weight: 700;'
            f"color: {CORES['tinta']};"
        )
        self.contagem = QLabel("0")
        self.contagem.setStyleSheet(
            f"background: {fundo}; color: {cor_texto}; border-radius: 9px;"
            f'padding: 1px 8px; font-family: "{FONTE_DADOS}"; font-size: 11px;'
            "font-weight: 700;"
        )
        self.acao = QPushButton()
        marcar(self.acao, variante="fantasma")
        self.acao.setStyleSheet("padding: 3px 8px; font-size: 11px;")
        self.acao.setVisible(False)

        cabecalho = QHBoxLayout()
        cabecalho.setContentsMargins(14, 12, 10, 0)
        cabecalho.setSpacing(8)
        cabecalho.addWidget(nome)
        cabecalho.addWidget(self.contagem)
        cabecalho.addStretch(1)
        cabecalho.addWidget(self.acao)

        apoio = rotulo(explicacao, "fraco")
        apoio.setContentsMargins(14, 0, 14, 6)

        self.lista = QVBoxLayout()
        self.lista.setContentsMargins(10, 4, 10, 10)
        self.lista.setSpacing(8)
        corpo = QWidget()
        corpo.setObjectName("corpoColuna")
        corpo.setStyleSheet("QWidget#corpoColuna { background: transparent; }")
        corpo_layout = QVBoxLayout(corpo)
        corpo_layout.setContentsMargins(0, 0, 0, 0)
        corpo_layout.addLayout(self.lista)
        corpo_layout.addStretch(1)

        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setWidget(corpo)
        rolagem.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        rolagem.setFrameShape(QFrame.Shape.NoFrame)
        rolagem.viewport().setAutoFillBackground(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(faixa)
        layout.addLayout(cabecalho)
        layout.addWidget(apoio)
        layout.addWidget(rolagem, 1)

    def _pintar(self, alvo: bool) -> None:
        fundo = CORES["ciano_claro"] if alvo else CORES["cinza_claro"]
        borda = CORES["ciano"] if alvo else CORES["pauta"]
        estilo = "dashed" if alvo else "solid"
        self.setStyleSheet(
            f"QFrame#colunaQuadro {{ background: {fundo};"
            f" border: 1px {estilo} {borda}; border-radius: 12px; }}"
        )

    def definir_cartoes(self, widgets: list[QWidget], total: int) -> None:
        _limpar(self.lista)
        for widget in widgets:
            self.lista.addWidget(widget)
        self.contagem.setText(str(total))
        if not widgets:
            titulo, texto = VAZIO[self.chave]
            vazio = QLabel(
                f'<div style="font-size:13px; font-weight:700;'
                f' color:{CORES["tinta_media"]};">{titulo}</div>'
                f'<div style="font-size:11px; color:{CORES["tinta_fraca"]};">{texto}</div>'
            )
            vazio.setAlignment(Qt.AlignmentFlag.AlignCenter)
            vazio.setWordWrap(True)
            vazio.setStyleSheet(
                f"border: 1px dashed {CORES['pauta_forte']}; border-radius: 10px;"
                "padding: 22px 12px; background: transparent;"
            )
            self.lista.addWidget(vazio)

    # ---------------------------------------------------------------- soltar
    def _ler(self, evento) -> tuple[int, str] | None:
        dados = evento.mimeData()
        if not dados.hasFormat(TIPO_MIME):
            return None
        try:
            evento_id, origem = bytes(dados.data(TIPO_MIME)).decode().split(":", 1)
            return int(evento_id), origem
        except ValueError:
            return None

    def dragEnterEvent(self, evento) -> None:  # noqa: N802
        lido = self._ler(evento)
        if lido is None or lido[1] == self.chave:
            evento.ignore()
            return
        evento.acceptProposedAction()
        self._pintar(True)

    def dragLeaveEvent(self, evento) -> None:  # noqa: N802
        self._pintar(False)
        super().dragLeaveEvent(evento)

    def dropEvent(self, evento) -> None:  # noqa: N802
        self._pintar(False)
        lido = self._ler(evento)
        if lido is None:
            return
        evento.acceptProposedAction()
        self.soltou.emit(lido[0], lido[1], self.chave)


class Indicador(QFrame):
    """Número da coluna no topo da tela."""

    clicado = Signal(str)

    def __init__(self, chave: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.chave = chave
        titulo, _explicacao, cor_faixa, _cor_texto, _fundo = coluna_info(chave)
        marcar(self, cartao="plano")
        ponto = QLabel()
        ponto.setFixedSize(10, 10)
        ponto.setStyleSheet(f"background: {cor_faixa}; border-radius: 5px;")
        legenda = rotulo(titulo, "campo")
        self.valor = QLabel("0")
        marcar(self.valor, papel="grande")

        topo = QHBoxLayout()
        topo.setSpacing(8)
        topo.addWidget(ponto)
        topo.addWidget(legenda)
        topo.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(0)
        layout.addLayout(topo)
        layout.addWidget(self.valor)


class BaixasTab(QWidget):
    """A tela inteira: título, emitir rota, filtros, números e o quadro."""

    dados_alterados = Signal()
    contagem_mudou = Signal(int)  # o que pede ação: atrasados + não realizados

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._clientes: list[Cliente] = []
        self._atrasados_ids: list[int] = []
        self._grupos: dict[str, list[Evento]] = {chave: [] for chave in CHAVES}

        titulo = rotulo("Rota e baixas", "titulo")
        self.subtitulo = rotulo(
            "Emita a rota do dia e acompanhe o que ainda espera confirmação."
            " Arraste o cartão para a coluna certa ou use os botões dele;"
            " dois cliques abrem o serviço.",
            "fraco",
        )
        self.subtitulo.setWordWrap(True)
        atualizar = QPushButton("Atualizar")
        marcar(atualizar, variante="fantasma")
        atualizar.clicked.connect(self.recarregar)
        self.btn_emitir = QPushButton("Emitir rota")
        marcar(self.btn_emitir, variante="primario")
        self.btn_emitir.setToolTip(
            "PDF da rota para o motoboy — com a opção de levar os atrasados junto"
        )
        self.btn_emitir.clicked.connect(self.emitir_rota)

        textos = QVBoxLayout()
        textos.setSpacing(2)
        textos.addWidget(titulo)
        textos.addWidget(self.subtitulo)
        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(8)
        cabecalho.addLayout(textos, 1)
        cabecalho.addWidget(atualizar, 0, Qt.AlignmentFlag.AlignTop)
        cabecalho.addWidget(self.btn_emitir, 0, Qt.AlignmentFlag.AlignTop)

        self.indicadores = {chave: Indicador(chave) for chave in CHAVES}
        linha_numeros = QHBoxLayout()
        linha_numeros.setSpacing(12)
        for indicador in self.indicadores.values():
            linha_numeros.addWidget(indicador, 1)

        self.colunas = {chave: ColunaQuadro(chave) for chave in CHAVES}
        quadro = QHBoxLayout()
        quadro.setSpacing(12)
        for coluna in self.colunas.values():
            coluna.soltou.connect(self._soltou)
            quadro.addWidget(coluna, 1)

        atrasados = self.colunas[ATRASADOS]
        atrasados.acao.setText("✓ Baixar todos")
        atrasados.acao.setToolTip("Dar baixa em todos os atrasados mostrados")
        atrasados.acao.clicked.connect(self._baixar_todos)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(14)
        layout.addLayout(cabecalho)
        layout.addWidget(self._barra_filtros())
        layout.addLayout(linha_numeros)
        layout.addLayout(quadro, 1)

        self.recarregar()

    # -------------------------------------------------------------- filtros
    def _barra_filtros(self) -> QWidget:
        barra = QFrame()
        marcar(barra, cartao="plano")
        self.busca = QLineEdit()
        self.busca.setPlaceholderText("Filtrar por cliente ou endereço")
        self.busca.setClearButtonEnabled(True)
        self.busca.setMinimumWidth(260)
        self.busca.textChanged.connect(lambda _t: self._desenhar())

        self.filtro_tipo = QComboBox()
        self.filtro_tipo.setMinimumWidth(180)
        self.filtro_tipo.currentIndexChanged.connect(lambda _i: self._desenhar())

        self.filtro_periodo = Segmentado(FiltroPeriodo)
        self.filtro_periodo.mudou.connect(lambda _v: self._desenhar())

        self.limpar_filtros = QPushButton("Limpar filtros")
        marcar(self.limpar_filtros, variante="fantasma")
        self.limpar_filtros.clicked.connect(self._limpar_filtros)
        self.limpar_filtros.setVisible(False)

        self.resumo_filtro = rotulo("", "fraco")

        linha = QHBoxLayout(barra)
        linha.setContentsMargins(12, 10, 12, 10)
        linha.setSpacing(10)
        linha.addWidget(self.busca, 2)
        linha.addWidget(rotulo("Tipo", "campo"))
        linha.addWidget(self.filtro_tipo, 1)
        linha.addSpacing(6)
        linha.addWidget(self.filtro_periodo)
        linha.addWidget(self.limpar_filtros)
        linha.addStretch(1)
        linha.addWidget(self.resumo_filtro)
        return barra

    def _recarregar_tipos(self) -> None:
        atual = self.filtro_tipo.currentData()
        try:
            with session_scope() as sessao:
                tipos = repo_tipos.listar(sessao, apenas_ativos=False)
        except Exception:
            return
        self.filtro_tipo.blockSignals(True)
        self.filtro_tipo.clear()
        self.filtro_tipo.addItem("Todos os tipos", None)
        for tipo in tipos:
            self.filtro_tipo.addItem(tipo.nome, tipo.id)
        indice = self.filtro_tipo.findData(atual)
        self.filtro_tipo.setCurrentIndex(max(0, indice))
        self.filtro_tipo.blockSignals(False)

    def _limpar_filtros(self) -> None:
        for campo in (self.busca, self.filtro_tipo):
            campo.blockSignals(True)
        self.busca.clear()
        self.filtro_tipo.setCurrentIndex(0)
        self.filtro_periodo.definir_valor(FiltroPeriodo.TODOS)
        for campo in (self.busca, self.filtro_tipo):
            campo.blockSignals(False)
        self._desenhar()

    def _filtrando(self) -> bool:
        return bool(
            self.busca.text().strip()
            or self.filtro_tipo.currentData() is not None
            or self.filtro_periodo.valor() is not FiltroPeriodo.TODOS
        )

    def _passa(self, evento: Evento) -> bool:
        tipo = self.filtro_tipo.currentData()
        if tipo is not None and evento.tipo_servico_id != tipo:
            return False
        periodo = self.filtro_periodo.valor()
        if periodo is FiltroPeriodo.MANHA and evento.periodo is not Periodo.MANHA:
            return False
        if periodo is FiltroPeriodo.TARDE and evento.periodo is not Periodo.TARDE:
            return False
        termo = self.busca.text().strip().casefold()
        if termo:
            cliente = evento.cliente
            textos = [cliente.nome, cliente.apelido or ""]
            if evento.endereco is not None:
                textos += [evento.endereco.etiqueta, evento.endereco.resumo()]
            if not any(termo in texto.casefold() for texto in textos):
                return False
        return True

    # ---------------------------------------------------------------- dados
    def recarregar(self) -> None:
        hoje = date.today()
        try:
            with session_scope() as sessao:
                sem_baixa = repo_eventos.listar_sem_baixa(sessao, hoje)
                nao_realizados = repo_eventos.listar_pendencias(sessao)
                baixados = repo_eventos.listar_baixados(
                    sessao, hoje - timedelta(days=DIAS_BAIXADOS - 1), hoje
                )
                self._clientes = repo_clientes.listar_clientes(sessao)
        except Exception as erro:
            mostrar_erro(self, erro, "Erro ao carregar as baixas")
            return

        self._recarregar_tipos()
        self._grupos = {
            ATRASADOS: [e for e in sem_baixa if e.data < hoje],
            HOJE: [e for e in sem_baixa if e.data == hoje],
            NAO_REALIZADOS: sorted(nao_realizados, key=lambda e: (e.data, e.id)),
            BAIXADOS: baixados,
        }
        # O contador da barra lateral não depende do filtro.
        self.contagem_mudou.emit(
            len(self._grupos[ATRASADOS]) + len(self._grupos[NAO_REALIZADOS])
        )
        self._desenhar()

    def _desenhar(self) -> None:
        hoje = date.today()
        filtrando = self._filtrando()
        self.limpar_filtros.setVisible(filtrando)
        grupos = {
            chave: [e for e in eventos if self._passa(e)]
            for chave, eventos in self._grupos.items()
        }
        mostrados = sum(len(lista) for lista in grupos.values())
        total = sum(len(lista) for lista in self._grupos.values())
        self.resumo_filtro.setText(
            f"{mostrados} de {total} cartões" if filtrando else f"{total} cartões"
        )
        self._atrasados_ids = [e.id for e in grupos[ATRASADOS]]
        for chave, eventos in grupos.items():
            agrupar_por_dia = chave in (ATRASADOS, BAIXADOS)
            widgets: list[QWidget] = []
            dia_atual: date | None = None
            for evento in eventos:
                if agrupar_por_dia and evento.data != dia_atual:
                    dia_atual = evento.data
                    quantos = sum(1 for e in eventos if e.data == dia_atual)
                    widgets.append(self._separador_dia(dia_atual, quantos, hoje))
                cartao = CartaoServico(evento, chave, hoje)
                cartao.mover.connect(
                    lambda evento_id, destino, origem=chave:
                    self._soltou(evento_id, origem, destino)
                )
                cartao.abrir.connect(self._abrir)
                widgets.append(cartao)
            self.colunas[chave].definir_cartoes(widgets, len(eventos))
            self.indicadores[chave].valor.setText(str(len(eventos)))

        self.colunas[ATRASADOS].acao.setVisible(len(grupos[ATRASADOS]) > 1)

    def emitir_rota(self) -> None:
        """O PDF da rota, com a opção de incluir os atrasados sem baixa."""
        from app.ui.relatorio_pdf import RelatorioDialog

        RelatorioDialog(self, date.today(), atalho_baixas=False).exec()

    def _separador_dia(self, dia: date, quantos: int, hoje: date) -> QLabel:
        texto = _dia_curto(dia) if (hoje - dia).days > 1 else (
            "ontem" if dia < hoje else "hoje"
        )
        rotulo_dia = QLabel(f"{texto.upper()}  ·  {quantos}")
        rotulo_dia.setStyleSheet(
            f'font-family: "{FONTE_DADOS}"; font-size: 10px; font-weight: 600;'
            f"color: {CORES['tinta_fraca']}; padding: 6px 2px 0 2px;"
            "background: transparent;"
        )
        return rotulo_dia

    # ---------------------------------------------------------------- ações
    def _soltou(self, evento_id: int, origem: str, destino: str) -> None:
        if destino == NAO_REALIZADOS:
            self._nao_deu(evento_id)
            return
        if origem == destino:
            return
        novo = StatusEvento.CONCLUIDO if destino == BAIXADOS else StatusEvento.PENDENTE
        try:
            with session_scope() as sessao:
                repo_eventos.alterar_status(sessao, evento_id, novo)
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para mudar a situação")
            return
        self._apos_mudanca()

    def _nao_deu(self, evento_id: int) -> None:
        from app.ui.reagendar import ReagendarDialog

        evento = self._obter(evento_id)
        if evento is None:
            return
        if ReagendarDialog(self, evento).exec() == ReagendarDialog.DialogCode.Accepted:
            self._apos_mudanca()

    def _abrir(self, evento_id: int) -> None:
        from app.ui.evento_dialog import EventoDialog

        evento = self._obter(evento_id)
        if evento is None:
            return
        dialogo = EventoDialog(self, self._clientes, evento=evento)
        if dialogo.exec() == EventoDialog.DialogCode.Accepted:
            self._apos_mudanca()

    def _obter(self, evento_id: int) -> Evento | None:
        try:
            with session_scope() as sessao:
                evento = repo_eventos.obter_evento(sessao, evento_id)
        except Exception as erro:
            mostrar_erro(self, erro, "Erro ao abrir o serviço")
            return None
        if evento is None:
            self.recarregar()
        return evento

    def _baixar_todos(self) -> None:
        total = len(self._atrasados_ids)
        if not total or not confirmar(
            self, "Dar baixa em todos",
            f"Confirmar que os {total} serviços atrasados mostrados foram feitos?\n\n"
            "Cada um fica registrado como concluído no registro de atividades.",
        ):
            return
        try:
            with session_scope() as sessao:
                repo_eventos.dar_baixa_em_lote(sessao, self._atrasados_ids)
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para dar baixa")
            return
        self._apos_mudanca()

    def _apos_mudanca(self) -> None:
        self.recarregar()
        self.dados_alterados.emit()
