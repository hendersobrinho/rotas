"""Painel: os números dos serviços no período escolhido."""

from __future__ import annotations

from datetime import date

from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.db import session_scope
from app.models import StatusEvento
from app.repository import eventos as repo_eventos
from app.ui.datas import (
    Agrupamento,
    andar_periodo,
    fatias_do_periodo,
    intervalo_do_periodo,
    rotulo_intervalo,
)
from app.ui.estilo import (
    COR_STATUS,
    CORES,
    FONTE_DADOS,
    marcar,
    preenchimento_da_etiqueta,
)
from app.ui.graficos import BarrasHorizontais, BarrasVerticais, Fatia
from app.ui.mensagens import mostrar_erro
from app.ui.widgets import Segmentado, cartao, rotulo

COR_UNICA = preenchimento_da_etiqueta("azul")


class Indicador(QFrame):
    """Número grande com um ponto colorido dizendo do que ele fala."""

    def __init__(self, titulo: str, cor: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        marcar(self, cartao="plano")

        ponto = QLabel("●")
        ponto.setStyleSheet(f"color: {cor}; font-size: 11px;")
        legenda = rotulo(titulo, "campo")

        topo = QHBoxLayout()
        topo.setSpacing(6)
        topo.addWidget(ponto)
        topo.addWidget(legenda)
        topo.addStretch(1)

        self.valor = QLabel("0")
        self.valor.setStyleSheet(
            f'font-family: "{FONTE_DADOS}"; font-size: 26px; font-weight: 600;'
            f"color: {CORES['tinta']};"
        )

        coluna = QVBoxLayout(self)
        coluna.setContentsMargins(16, 12, 16, 14)
        coluna.setSpacing(2)
        coluna.addLayout(topo)
        coluna.addWidget(self.valor)

    def definir(self, valor: int) -> None:
        self.valor.setText(str(valor))


class PainelTab(QWidget):
    """Indicadores e gráficos do período selecionado."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._referencia = date.today()
        self._modo = Agrupamento.MES

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 10, 18, 18)
        layout.setSpacing(14)
        layout.addLayout(self._montar_cabecalho())
        layout.addLayout(self._montar_indicadores())
        layout.addLayout(self._montar_graficos(), 1)

        self.recarregar()

    # ---------------------------------------------------------------- layout
    def _montar_cabecalho(self) -> QHBoxLayout:
        self.titulo = QLabel()
        marcar(self.titulo, papel="titulo")

        self.seletor = Segmentado(Agrupamento)
        self.seletor.definir_valor(Agrupamento.MES)
        self.seletor.mudou.connect(self._trocar_modo)

        anterior = QPushButton("‹")
        proximo = QPushButton("›")
        for botao in (anterior, proximo):
            botao.setFixedWidth(34)
            marcar(botao, variante="fantasma")
            botao.setStyleSheet("font-size: 18px;")
        anterior.clicked.connect(lambda: self._andar(-1))
        proximo.clicked.connect(lambda: self._andar(1))

        hoje = QPushButton("Hoje")
        hoje.clicked.connect(self._ir_para_hoje)

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(6)
        cabecalho.addWidget(self.titulo)
        cabecalho.addSpacing(8)
        cabecalho.addWidget(anterior)
        cabecalho.addWidget(proximo)
        cabecalho.addWidget(hoje)
        cabecalho.addStretch(1)
        cabecalho.addWidget(rotulo("Período", "campo"))
        cabecalho.addWidget(self.seletor)
        return cabecalho

    def _montar_indicadores(self) -> QHBoxLayout:
        self.indicadores: dict[str, Indicador] = {
            "total": Indicador("Serviços no período", CORES["azul"]),
            "pendente": Indicador("Pendentes", COR_STATUS[StatusEvento.PENDENTE][0]),
            "concluido": Indicador("Concluídos", COR_STATUS[StatusEvento.CONCLUIDO][0]),
            "nao_realizado": Indicador(
                "Não realizados", COR_STATUS[StatusEvento.NAO_REALIZADO][0]
            ),
            "cancelado": Indicador("Cancelados", COR_STATUS[StatusEvento.CANCELADO][0]),
        }
        linha = QHBoxLayout()
        linha.setSpacing(14)
        for indicador in self.indicadores.values():
            linha.addWidget(indicador, 1)
        return linha

    def _montar_graficos(self) -> QGridLayout:
        self.grafico_tempo = BarrasVerticais()
        self.grafico_tipo = BarrasHorizontais()
        self.grafico_cliente = BarrasHorizontais()
        self.grafico_solicitante = BarrasHorizontais()

        grade = QGridLayout()
        grade.setSpacing(14)
        grade.addWidget(
            self._cartao_grafico(
                "Serviços ao longo do período", self.grafico_tempo,
                "Quantidade por dia; no ano, por mês."), 0, 0)
        grade.addWidget(
            self._cartao_grafico(
                "Por tipo de serviço", self.grafico_tipo,
                "Cada tipo na cor escolhida no cadastro."), 0, 1)
        grade.addWidget(
            self._cartao_grafico(
                "Clientes mais atendidos", self.grafico_cliente,
                "Os oito primeiros do período."), 1, 0)
        grade.addWidget(
            self._cartao_grafico(
                "Quem mais pediu", self.grafico_solicitante,
                "Serviços por solicitante."), 1, 1)
        grade.setColumnStretch(0, 3)
        grade.setColumnStretch(1, 2)
        return grade

    def _cartao_grafico(self, titulo: str, grafico: QWidget, dica: str) -> QWidget:
        painel = cartao()
        coluna = QVBoxLayout(painel)
        coluna.setContentsMargins(16, 14, 16, 14)
        coluna.setSpacing(4)
        coluna.addWidget(rotulo(titulo, "secao"))
        coluna.addWidget(rotulo(dica, "fraco"))
        coluna.addSpacing(6)
        coluna.addWidget(grafico, 1)
        return painel

    # ----------------------------------------------------------------- dados
    def _trocar_modo(self, modo: Agrupamento) -> None:
        self._modo = modo
        self.recarregar()

    def _andar(self, passos: int) -> None:
        self._referencia = andar_periodo(self._referencia, self._modo, passos)
        self.recarregar()

    def _ir_para_hoje(self) -> None:
        self._referencia = date.today()
        self.recarregar()

    def recarregar(self) -> None:
        inicio, fim = intervalo_do_periodo(self._referencia, self._modo)
        self.titulo.setText(rotulo_intervalo(inicio, fim, self._modo).capitalize())

        try:
            with session_scope() as sessao:
                por_status = repo_eventos.resumo_por_status(sessao, inicio, fim)
                por_tipo = repo_eventos.resumo_por_tipo(sessao, inicio, fim)
                por_dia = repo_eventos.contagem_por_dia(sessao, inicio, fim)
                por_cliente = repo_eventos.resumo_por_cliente(sessao, inicio, fim)
                por_solicitante = repo_eventos.resumo_por_solicitante(
                    sessao, inicio, fim
                )
        except Exception as erro:
            mostrar_erro(self, erro, "Erro ao carregar o painel")
            return

        self.indicadores["total"].definir(sum(por_status.values()))
        self.indicadores["pendente"].definir(por_status.get(StatusEvento.PENDENTE, 0))
        self.indicadores["concluido"].definir(por_status.get(StatusEvento.CONCLUIDO, 0))
        self.indicadores["nao_realizado"].definir(
            por_status.get(StatusEvento.NAO_REALIZADO, 0)
        )
        self.indicadores["cancelado"].definir(por_status.get(StatusEvento.CANCELADO, 0))

        self.grafico_tipo.definir([
            Fatia(nome, total, preenchimento_da_etiqueta(estilo))
            for nome, estilo, total in por_tipo
        ])
        self.grafico_cliente.definir(
            [Fatia(nome, total, COR_UNICA) for nome, total in por_cliente]
        )
        self.grafico_solicitante.definir(
            [Fatia(nome, total, COR_UNICA) for nome, total in por_solicitante]
        )

        fatias = []
        for texto, comeco, termino in fatias_do_periodo(inicio, fim, self._modo):
            total = sum(
                quantidade
                for dia, quantidade in por_dia.items()
                if comeco <= dia <= termino
            )
            detalhe = (
                comeco.strftime("%d/%m/%Y")
                if comeco == termino
                else f"{comeco.strftime('%d/%m')} a {termino.strftime('%d/%m')}"
            )
            fatias.append(Fatia(texto.replace("\n", " "), total, COR_UNICA, detalhe))
        self.grafico_tempo.definir(fatias)
