"""Diálogo de inclusão e edição de um serviço (coleta ou retirada)."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.db import session_scope
from app.models import Cliente, Evento, Periodo, StatusEvento, TipoServico
from app.repository import eventos as repo_eventos
from app.schemas import DadosEvento
from app.ui.estilo import CORES, marcar
from app.ui.mensagens import confirmar, mostrar_erro
from app.ui.widgets import Segmentado, rotulo, selecionar_dado


class EventoDialog(QDialog):
    """Cria ou edita um serviço; salva sozinho e devolve o id em `evento_id`."""

    def __init__(
        self,
        parent: QWidget | None,
        clientes: list[Cliente],
        evento: Evento | None = None,
        dia: date | None = None,
        cliente_id: int | None = None,
    ) -> None:
        super().__init__(parent)
        self._clientes = clientes
        self._evento_id = evento.id if evento else None
        self.evento_id: int | None = self._evento_id
        self.excluido = False

        self.setWindowTitle("Serviço")
        self.setMinimumWidth(540)
        self.setStyleSheet(f"QDialog {{ background: {CORES['papel']}; }}")

        self.campo_cliente = QComboBox()
        for cliente in clientes:
            self.campo_cliente.addItem(cliente.nome_exibicao, cliente.id)
        self.campo_cliente.currentIndexChanged.connect(self._atualizar_enderecos)

        self.campo_endereco = QComboBox()
        self.campo_servico = Segmentado(TipoServico)
        self.campo_periodo = Segmentado(Periodo)
        self.campo_status = Segmentado(StatusEvento)

        self.campo_data = QDateEdit()
        self.campo_data.setCalendarPopup(True)
        self.campo_data.setDisplayFormat("dd/MM/yyyy")
        self.campo_data.setMaximumWidth(140)

        self.campo_solicitante = QLineEdit()
        self.campo_solicitante.setPlaceholderText("Quem pediu, aqui no escritório")

        conteudo = QVBoxLayout()
        conteudo.setSpacing(6)
        titulo = rotulo("Novo serviço" if evento is None else "Editar serviço", "titulo")
        conteudo.addWidget(titulo)
        conteudo.addWidget(
            rotulo("Coleta busca os documentos; retirada leva de volta.", "fraco")
        )
        conteudo.addSpacing(10)

        conteudo.addWidget(rotulo("Cliente", "campo"))
        conteudo.addWidget(self.campo_cliente)
        conteudo.addSpacing(8)
        conteudo.addWidget(rotulo("Endereço", "campo"))
        conteudo.addWidget(self.campo_endereco)
        conteudo.addSpacing(8)

        conteudo.addWidget(rotulo("Serviço", "campo"))
        linha_servico = QHBoxLayout()
        linha_servico.addWidget(self.campo_servico)
        linha_servico.addStretch(1)
        conteudo.addLayout(linha_servico)
        conteudo.addSpacing(8)

        linha_data = QHBoxLayout()
        linha_data.setSpacing(24)
        bloco_data = QVBoxLayout()
        bloco_data.setSpacing(6)
        bloco_data.addWidget(rotulo("Data", "campo"))
        bloco_data.addWidget(self.campo_data)
        bloco_periodo = QVBoxLayout()
        bloco_periodo.setSpacing(6)
        bloco_periodo.addWidget(rotulo("Período", "campo"))
        bloco_periodo.addWidget(self.campo_periodo)
        linha_data.addLayout(bloco_data)
        linha_data.addLayout(bloco_periodo)
        linha_data.addStretch(1)
        conteudo.addLayout(linha_data)
        conteudo.addSpacing(8)

        conteudo.addWidget(rotulo("Solicitante", "campo"))
        conteudo.addWidget(self.campo_solicitante)
        conteudo.addSpacing(8)

        conteudo.addWidget(rotulo("Situação", "campo"))
        linha_status = QHBoxLayout()
        linha_status.addWidget(self.campo_status)
        linha_status.addStretch(1)
        conteudo.addLayout(linha_status)

        self.btn_excluir = QPushButton("Excluir")
        marcar(self.btn_excluir, variante="perigo")
        self.btn_excluir.clicked.connect(self._excluir)
        self.btn_excluir.setVisible(evento is not None)

        btn_descartar = QPushButton("Descartar")
        btn_descartar.clicked.connect(self.reject)
        btn_salvar = QPushButton("Salvar")
        marcar(btn_salvar, variante="primario")
        btn_salvar.setDefault(True)
        btn_salvar.clicked.connect(self._salvar)

        rodape = QHBoxLayout()
        rodape.addWidget(self.btn_excluir)
        rodape.addStretch(1)
        rodape.addWidget(btn_descartar)
        rodape.addWidget(btn_salvar)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(18)
        layout.addLayout(conteudo)
        layout.addLayout(rodape)

        self._preencher(evento, dia, cliente_id)

    # ------------------------------------------------------------------ dados
    def _preencher(
        self, evento: Evento | None, dia: date | None, cliente_id: int | None
    ) -> None:
        if evento is not None:
            selecionar_dado(self.campo_cliente, evento.cliente_id)
            self._atualizar_enderecos()
            selecionar_dado(self.campo_endereco, evento.endereco_id)
            self.campo_servico.definir_valor(evento.tipo_servico)
            self.campo_periodo.definir_valor(evento.periodo)
            self.campo_status.definir_valor(evento.status)
            self.campo_solicitante.setText(evento.solicitante or "")
            escolhido = evento.data
        else:
            if cliente_id is not None:
                selecionar_dado(self.campo_cliente, cliente_id)
            self._atualizar_enderecos()
            self.campo_servico.definir_valor(TipoServico.COLETA)
            self.campo_periodo.definir_valor(Periodo.MANHA)
            self.campo_status.definir_valor(StatusEvento.PENDENTE)
            escolhido = dia or date.today()
        self.campo_data.setDate(QDate(escolhido.year, escolhido.month, escolhido.day))

    def _cliente_atual(self) -> Cliente | None:
        cliente_id = self.campo_cliente.currentData()
        for cliente in self._clientes:
            if cliente.id == cliente_id:
                return cliente
        return None

    def _atualizar_enderecos(self) -> None:
        anterior = self.campo_endereco.currentData()
        cliente = self._cliente_atual()
        self.campo_endereco.clear()
        self.campo_endereco.addItem("Não informar endereço", None)
        if cliente is not None:
            for endereco in cliente.enderecos:
                self.campo_endereco.addItem(
                    f"{endereco.tipo.value} — {endereco.resumo()}", endereco.id
                )
        selecionar_dado(self.campo_endereco, anterior)

    def _dados(self) -> DadosEvento:
        cliente_id = self.campo_cliente.currentData()
        if cliente_id is None:
            raise ValueError("Escolha o cliente do serviço.")
        return DadosEvento(
            cliente_id=int(cliente_id),
            endereco_id=self.campo_endereco.currentData(),
            tipo_servico=self.campo_servico.valor(),
            data=self.campo_data.date().toPython(),
            periodo=self.campo_periodo.valor(),
            solicitante=self.campo_solicitante.text(),
            status=self.campo_status.valor(),
        )

    # ------------------------------------------------------------------ ações
    def _salvar(self) -> None:
        try:
            dados = self._dados()
            with session_scope() as sessao:
                if self._evento_id is None:
                    evento = repo_eventos.criar_evento(sessao, dados)
                else:
                    evento = repo_eventos.atualizar_evento(
                        sessao, self._evento_id, dados
                    )
                self.evento_id = evento.id
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para salvar")
            return
        self.accept()

    def _excluir(self) -> None:
        if self._evento_id is None:
            return
        if not confirmar(
            self,
            "Excluir serviço",
            "Excluir este serviço de vez?\n\n"
            "Para manter o registro no histórico, mude a situação para Cancelado.",
        ):
            return
        try:
            with session_scope() as sessao:
                repo_eventos.excluir_evento(sessao, self._evento_id)
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para excluir")
            return
        self.excluido = True
        self.evento_id = None
        self.accept()

    def keyPressEvent(self, evento) -> None:  # noqa: N802
        # Enter salva; Esc fecha (comportamento padrão do QDialog).
        if evento.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._salvar()
            return
        super().keyPressEvent(evento)
