"""Serviço que não deu para fazer: registrar o motivo e remarcar."""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from app.db import session_scope
from app.models import Evento, Periodo
from app.repository import eventos as repo_eventos
from app.ui.estilo import CORES, marcar
from app.ui.mensagens import mostrar_erro
from app.ui.seletor_data import SeletorDeData
from app.ui.widgets import (
    Segmentado,
    selecionar_dado,
    configurar_tabela,
    dado_da_linha,
    preencher_linha,
    rotulo,
)

MOTIVOS = (
    "Estabelecimento fechado",
    "Não tinha ninguém para atender",
    "Documentos não estavam prontos",
    "Endereço não encontrado",
    "Cliente pediu para voltar outro dia",
    "Não deu tempo na rota",
)
COLUNAS_PENDENCIAS = ("Data", "Cliente", "Serviço", "Motivo")


class ReagendarDialog(QDialog):
    """Marca o serviço como não realizado e, se for o caso, abre outro."""

    def __init__(self, parent: QWidget | None, evento: Evento) -> None:
        super().__init__(parent)
        self._evento_id = evento.id
        self.remarcado_para: date | None = None

        self.setWindowTitle("Não deu para fazer")
        self.setMinimumWidth(430)
        self.setStyleSheet(f"QDialog {{ background: {CORES['papel']}; }}")

        self.campo_motivo = QComboBox()
        self.campo_motivo.setEditable(True)
        self.campo_motivo.addItem("")
        for motivo in MOTIVOS:
            self.campo_motivo.addItem(motivo)
        self.campo_motivo.setCurrentText(evento.motivo or "")
        self.campo_motivo.lineEdit().setPlaceholderText(
            "Escolha um motivo ou escreva o seu"
        )

        # O serviço novo precisa de endereço. Vem com o do original, e dá para
        # trocar — inclusive quando o original ficou sem, porque o endereço
        # saiu do cadastro.
        self.campo_endereco = QComboBox()
        enderecos = list(evento.cliente.enderecos)
        if evento.endereco_id is None and enderecos:
            self.campo_endereco.addItem("Escolha o endereço", None)
        for endereco in enderecos:
            self.campo_endereco.addItem(
                f"{endereco.tipo.value} — {endereco.resumo()}", endereco.id
            )
        if not enderecos:
            self.campo_endereco.addItem("Sem endereço cadastrado", None)
            self.campo_endereco.setEnabled(False)
        elif evento.endereco_id is not None:
            selecionar_dado(self.campo_endereco, evento.endereco_id)

        self.remarcar = QCheckBox("Remarcar para outro dia")
        self.remarcar.setChecked(True)
        self.remarcar.toggled.connect(self._alternar_remarcacao)

        self.calendario = SeletorDeData(self)
        self.calendario.definir_data(max(evento.data + timedelta(days=1), date.today()))
        self.campo_periodo = Segmentado(Periodo)
        self.campo_periodo.definir_valor(evento.periodo)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(10)
        layout.addWidget(rotulo("Não deu para fazer", "titulo"))
        layout.addWidget(
            rotulo(
                f"{evento.tipo_servico.nome} · {evento.cliente.nome_exibicao}"
                f" · {evento.data.strftime('%d/%m/%Y')}",
                "fraco",
            )
        )
        layout.addSpacing(8)
        layout.addWidget(rotulo("Motivo", "campo"))
        layout.addWidget(self.campo_motivo)
        layout.addSpacing(8)
        layout.addWidget(self.remarcar)
        explicacao = rotulo(
            "O serviço do dia fica no histórico como não realizado; a"
            " remarcação nasce ligada a ele.",
            "fraco",
        )
        explicacao.setWordWrap(True)
        layout.addWidget(explicacao)
        layout.addSpacing(4)
        layout.addWidget(rotulo("Endereço da remarcação", "campo"))
        layout.addWidget(self.campo_endereco)
        layout.addSpacing(4)
        layout.addWidget(self.calendario)
        linha_periodo = QHBoxLayout()
        linha_periodo.addWidget(rotulo("Período", "campo"))
        linha_periodo.addSpacing(8)
        linha_periodo.addWidget(self.campo_periodo)
        linha_periodo.addStretch(1)
        layout.addLayout(linha_periodo)
        layout.addSpacing(10)

        salvar = QPushButton("Salvar")
        marcar(salvar, variante="primario")
        salvar.setDefault(True)
        salvar.clicked.connect(self._salvar)
        descartar = QPushButton("Descartar")
        descartar.clicked.connect(self.reject)
        rodape = QHBoxLayout()
        rodape.addStretch(1)
        rodape.addWidget(descartar)
        rodape.addWidget(salvar)
        layout.addLayout(rodape)

        self.campo_motivo.setFocus()

    def _alternar_remarcacao(self, ligado: bool) -> None:
        self.calendario.setEnabled(ligado)
        self.campo_periodo.setEnabled(ligado)
        self.campo_endereco.setEnabled(
            ligado and self.campo_endereco.count() > 0
            and self.campo_endereco.itemData(self.campo_endereco.count() - 1)
            is not None
        )

    def _salvar(self) -> None:
        motivo = self.campo_motivo.currentText()
        try:
            with session_scope() as sessao:
                if self.remarcar.isChecked():
                    novo = repo_eventos.reagendar(
                        sessao,
                        self._evento_id,
                        self.calendario.data(),
                        self.campo_periodo.valor(),
                        motivo,
                        endereco_id=self.campo_endereco.currentData(),
                    )
                    self.remarcado_para = novo.data
                else:
                    repo_eventos.nao_realizado(sessao, self._evento_id, motivo)
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para salvar")
            return
        self.accept()


class PendenciasDialog(QDialog):
    """Serviços não realizados que ninguém remarcou ainda."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.houve_mudanca = False

        self.setWindowTitle("Pendências")
        self.setMinimumSize(640, 420)
        self.setStyleSheet(f"QDialog {{ background: {CORES['papel']}; }}")

        self.tabela = QTableWidget()
        configurar_tabela(self.tabela, COLUNAS_PENDENCIAS, coluna_elastica=3)
        self.tabela.doubleClicked.connect(lambda _i: self._reagendar())
        self.contador = rotulo("", "fraco")

        self.btn_reagendar = QPushButton("Resolver")
        marcar(self.btn_reagendar, variante="primario")
        self.btn_reagendar.clicked.connect(self._reagendar)
        fechar = QPushButton("Fechar")
        fechar.clicked.connect(self.accept)

        rodape = QHBoxLayout()
        rodape.addWidget(self.contador)
        rodape.addStretch(1)
        rodape.addWidget(fechar)
        rodape.addWidget(self.btn_reagendar)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(10)
        layout.addWidget(rotulo("Pendências", "titulo"))
        layout.addWidget(
            rotulo(
                "Serviços que não deram para fazer e continuam sem remarcação.",
                "fraco",
            )
        )
        layout.addSpacing(6)
        layout.addWidget(self.tabela, 1)
        layout.addLayout(rodape)

        self.recarregar()

    def recarregar(self) -> None:
        try:
            with session_scope() as sessao:
                pendentes = repo_eventos.listar_pendencias(sessao)
        except Exception as erro:
            mostrar_erro(self, erro, "Erro ao carregar as pendências")
            return

        self.tabela.setRowCount(len(pendentes))
        for linha, evento in enumerate(pendentes):
            preencher_linha(
                self.tabela,
                linha,
                (
                    evento.data.strftime("%d/%m/%Y"),
                    evento.cliente.nome_exibicao,
                    evento.tipo_servico.nome,
                    evento.motivo or "—",
                ),
                dado=evento.id,
            )
        self.contador.setText(f"{len(pendentes)} sem remarcação")
        self.btn_reagendar.setEnabled(bool(pendentes))
        if pendentes:
            self.tabela.selectRow(0)

    def _reagendar(self) -> None:
        linhas = self.tabela.selectionModel().selectedRows()
        if not linhas:
            return
        evento_id = dado_da_linha(self.tabela, linhas[0].row())
        if evento_id is None:
            return
        with session_scope() as sessao:
            evento = repo_eventos.obter_evento(sessao, int(evento_id))
        if evento is None:
            self.recarregar()
            return
        if ReagendarDialog(self, evento).exec() == QDialog.DialogCode.Accepted:
            self.houve_mudanca = True
            self.recarregar()
