"""Aba Registro: o que cada usuário fez no sistema."""

from __future__ import annotations

from PySide6.QtCore import QDate, Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from app.db import session_scope
from app.models import AcaoLog, EntidadeLog
from app.repository import logs as repo_logs
from app.repository import usuarios as repo_usuarios
from app.ui.estilo import CORES, marcar
from app.ui.mensagens import mostrar_erro
from app.ui.widgets import (
    cartao,
    combo_enum,
    configurar_tabela,
    preencher_linha,
    rotulo,
    selecionar_dado,
)

COLUNAS = ("Quando", "Usuário", "Ação", "Sobre", "O que aconteceu")
LIMITE = 500

COR_ACAO = {
    AcaoLog.LOGIN: CORES["verde"],
    AcaoLog.LOGOUT: CORES["tinta_fraca"],
    AcaoLog.CRIACAO: CORES["azul"],
    AcaoLog.ALTERACAO: CORES["carimbo"],
    AcaoLog.EXCLUSAO: CORES["vermelho"],
}


class RegistroTab(QWidget):
    """Lista do mais recente para o mais antigo, com filtros em cima."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 10, 18, 18)
        layout.setSpacing(14)
        layout.addWidget(self._montar_filtros())
        layout.addWidget(self._montar_tabela(), 1)

        self.recarregar_usuarios()
        self.recarregar()

    # ---------------------------------------------------------------- layout
    def _montar_filtros(self) -> QWidget:
        painel = cartao()
        grade = QGridLayout(painel)
        grade.setContentsMargins(16, 14, 16, 14)
        grade.setHorizontalSpacing(12)
        grade.setVerticalSpacing(10)

        self.filtro_usuario = QComboBox()
        self.filtro_usuario.setMinimumWidth(180)
        self.filtro_acao = combo_enum(AcaoLog, incluir_vazio=True, texto_vazio="Todas")
        self.filtro_entidade = combo_enum(
            EntidadeLog, incluir_vazio=True, texto_vazio="Tudo"
        )
        self.filtro_termo = QLineEdit()
        self.filtro_termo.setPlaceholderText("Procurar no texto")
        self.filtro_termo.setClearButtonEnabled(True)
        self.filtro_termo.returnPressed.connect(self.recarregar)

        self.usar_datas = QCheckBox("Filtrar por período")
        self.data_inicio = QDateEdit(QDate.currentDate().addDays(-30))
        self.data_fim = QDateEdit(QDate.currentDate())
        for campo in (self.data_inicio, self.data_fim):
            campo.setCalendarPopup(True)
            campo.setDisplayFormat("dd/MM/yyyy")
            campo.setEnabled(False)
            campo.setMaximumWidth(140)
        self.usar_datas.toggled.connect(self.data_inicio.setEnabled)
        self.usar_datas.toggled.connect(self.data_fim.setEnabled)

        aplicar = QPushButton("Aplicar")
        marcar(aplicar, variante="primario")
        aplicar.clicked.connect(self.recarregar)
        limpar = QPushButton("Limpar")
        limpar.clicked.connect(self._limpar)

        grade.addWidget(rotulo("Usuário", "campo"), 0, 0)
        grade.addWidget(self.filtro_usuario, 0, 1)
        grade.addWidget(rotulo("Ação", "campo"), 0, 2)
        grade.addWidget(self.filtro_acao, 0, 3)
        grade.addWidget(rotulo("Sobre", "campo"), 0, 4)
        grade.addWidget(self.filtro_entidade, 0, 5)
        grade.addWidget(rotulo("Texto", "campo"), 1, 0)
        grade.addWidget(self.filtro_termo, 1, 1)
        grade.addWidget(self.usar_datas, 1, 2)
        grade.addWidget(self.data_inicio, 1, 3)
        grade.addWidget(QLabel("até"), 1, 4, Qt.AlignmentFlag.AlignRight)
        grade.addWidget(self.data_fim, 1, 5)
        grade.addWidget(aplicar, 0, 6)
        grade.addWidget(limpar, 1, 6)
        grade.setColumnStretch(7, 3)
        return painel

    def _montar_tabela(self) -> QWidget:
        painel = cartao()
        coluna = QVBoxLayout(painel)
        coluna.setContentsMargins(16, 14, 16, 16)
        coluna.setSpacing(10)

        topo = QHBoxLayout()
        topo.addWidget(rotulo("Registro de atividades", "secao"))
        topo.addStretch(1)
        self.contador = rotulo("", "fraco")
        topo.addWidget(self.contador)
        coluna.addLayout(topo)

        self.tabela = QTableWidget()
        configurar_tabela(self.tabela, COLUNAS, coluna_elastica=4)
        coluna.addWidget(self.tabela)
        return painel

    # ----------------------------------------------------------------- dados
    def recarregar_usuarios(self) -> None:
        anterior = self.filtro_usuario.currentData()
        try:
            with session_scope() as sessao:
                pessoas = repo_usuarios.listar(sessao)
        except Exception as erro:
            mostrar_erro(self, erro, "Erro ao listar usuários")
            return
        self.filtro_usuario.clear()
        self.filtro_usuario.addItem("Todos", None)
        for pessoa in pessoas:
            self.filtro_usuario.addItem(pessoa.nome, pessoa.id)
        selecionar_dado(self.filtro_usuario, anterior)

    def recarregar(self) -> None:
        inicio = fim = None
        if self.usar_datas.isChecked():
            inicio = self.data_inicio.date().toPython()
            fim = self.data_fim.date().toPython()
        try:
            with session_scope() as sessao:
                registros = repo_logs.listar(
                    sessao,
                    data_inicio=inicio,
                    data_fim=fim,
                    usuario_id=self.filtro_usuario.currentData(),
                    acao=self.filtro_acao.currentData(),
                    entidade=self.filtro_entidade.currentData(),
                    termo=self.filtro_termo.text(),
                    limite=LIMITE,
                )
                total = repo_logs.contar(sessao)
        except Exception as erro:
            mostrar_erro(self, erro, "Erro ao carregar o registro")
            return

        self.tabela.setRowCount(len(registros))
        for linha, registro in enumerate(registros):
            preencher_linha(
                self.tabela,
                linha,
                (
                    registro.quando.astimezone().strftime("%d/%m/%Y  %H:%M"),
                    registro.usuario_nome,
                    registro.acao.value,
                    registro.entidade.value,
                    registro.descricao,
                ),
                dado=registro.id,
            )
            item = self.tabela.item(linha, 2)
            if item is not None:
                item.setForeground(QColor(COR_ACAO[registro.acao]))

        if len(registros) >= LIMITE:
            self.contador.setText(
                f"mostrando os {LIMITE} mais recentes de {total}"
            )
        else:
            self.contador.setText(f"{len(registros)} de {total} no total")

    def _limpar(self) -> None:
        selecionar_dado(self.filtro_usuario, None)
        selecionar_dado(self.filtro_acao, None)
        selecionar_dado(self.filtro_entidade, None)
        self.filtro_termo.clear()
        self.usar_datas.setChecked(False)
        self.recarregar()
