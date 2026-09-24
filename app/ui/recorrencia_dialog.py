"""Cadastro de um serviço fixo: a regra e uma prévia das próximas datas."""

from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QPushButton,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.db import session_scope
from app.models import (
    Cliente,
    FrequenciaRecorrencia,
    Periodo,
    Recorrencia,
)
from app.repository import recorrencias as repo_recorrencias
from app.repository import solicitantes as repo_solicitantes
from app.repository import tipos_servico as repo_tipos
from app.schemas import DadosRecorrencia
from app.ui.estilo import CORES, cores_da_etiqueta, glifo_da_etiqueta, marcar
from app.ui.mensagens import mostrar_erro
from app.ui.widgets import Segmentado, rotulo, selecionar_dado

ORDINAIS = ((1, "primeira"), (2, "segunda"), (3, "terceira"), (4, "quarta"),
            (5, "quinta"), (-1, "última"))


class RecorrenciaDialog(QDialog):
    """Descreve quando o serviço se repete, mostrando as próximas datas."""

    def __init__(
        self,
        parent: QWidget | None,
        cliente: Cliente,
        regra: Recorrencia | None = None,
    ) -> None:
        super().__init__(parent)
        self._cliente = cliente
        self._regra_id = regra.id if regra else None
        self.recorrencia_id: int | None = self._regra_id

        self.setWindowTitle("Serviço fixo")
        self.setMinimumWidth(480)
        self.setStyleSheet(f"QDialog {{ background: {CORES['papel']}; }}")

        self.campo_servico = QComboBox()
        self.campo_endereco = QComboBox()
        self.campo_solicitante = QComboBox()
        self.campo_periodo = Segmentado(Periodo)
        self.campo_frequencia = Segmentado(FrequenciaRecorrencia)
        self.campo_frequencia.mudou.connect(self._trocar_frequencia)

        self.campo_dia_semana = QComboBox()
        self.campo_dia_semana_mes = QComboBox()
        for indice, nome in enumerate(repo_recorrencias.DIAS_SEMANA_NOMES):
            self.campo_dia_semana.addItem(nome.capitalize(), indice)
            self.campo_dia_semana_mes.addItem(nome.capitalize(), indice)
        self.campo_ordinal = QComboBox()
        for valor, nome in ORDINAIS:
            self.campo_ordinal.addItem(nome.capitalize(), valor)
        self.campo_dia_mes = QSpinBox()
        self.campo_dia_mes.setRange(1, 31)
        self.campo_dia_mes.setMaximumWidth(90)
        self.campo_util = QCheckBox("Caindo em fim de semana, passa para segunda")
        self.campo_util.setChecked(True)
        self.campo_ativo = QCheckBox("Abrir os serviços automaticamente")
        self.campo_ativo.setChecked(True)

        for campo in (
            self.campo_dia_semana,
            self.campo_dia_semana_mes,
            self.campo_ordinal,
            self.campo_dia_mes,
        ):
            campo.currentIndexChanged.connect(self._atualizar_previa) if isinstance(
                campo, QComboBox
            ) else campo.valueChanged.connect(self._atualizar_previa)
        self.campo_util.toggled.connect(lambda _v: self._atualizar_previa())

        self.paginas = QStackedWidget()
        self.paginas.addWidget(self._pagina_semanal())
        self.paginas.addWidget(self._pagina_ordinal())
        self.paginas.addWidget(self._pagina_dia_mes())

        self.previa = rotulo("", "apoio")
        self.previa.setWordWrap(True)
        self.previa.setStyleSheet(
            f"background: {CORES['azul_claro']}; color: {CORES['azul_escuro']};"
            "border-radius: 8px; padding: 8px 10px; font-size: 12px;"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(8)
        layout.addWidget(
            rotulo("Novo serviço fixo" if regra is None else "Editar serviço fixo",
                   "titulo")
        )
        layout.addWidget(rotulo(cliente.nome_exibicao, "fraco"))
        layout.addSpacing(8)
        layout.addWidget(rotulo("Tipo de serviço", "campo"))
        layout.addWidget(self.campo_servico)
        layout.addWidget(rotulo("Endereço *", "campo"))
        layout.addWidget(self.campo_endereco)
        layout.addWidget(rotulo("Solicitante", "campo"))
        layout.addWidget(self.campo_solicitante)
        layout.addSpacing(4)

        linha_periodo = QHBoxLayout()
        linha_periodo.addWidget(rotulo("Período", "campo"))
        linha_periodo.addSpacing(8)
        linha_periodo.addWidget(self.campo_periodo)
        linha_periodo.addStretch(1)
        layout.addLayout(linha_periodo)
        layout.addSpacing(8)

        layout.addWidget(rotulo("Quando se repete", "campo"))
        layout.addWidget(self.campo_frequencia)
        layout.addWidget(self.paginas)
        layout.addSpacing(4)
        layout.addWidget(self.campo_ativo)
        layout.addSpacing(6)
        layout.addWidget(self.previa)
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

        self._carregar_listas(regra)
        self._preencher(regra)

    # ---------------------------------------------------------------- telas
    def _pagina_semanal(self) -> QWidget:
        pagina = QWidget()
        linha = QHBoxLayout(pagina)
        linha.setContentsMargins(0, 6, 0, 0)
        linha.addWidget(rotulo("Toda", "campo"))
        linha.addWidget(self.campo_dia_semana, 1)
        return pagina

    def _pagina_ordinal(self) -> QWidget:
        pagina = QWidget()
        linha = QHBoxLayout(pagina)
        linha.setContentsMargins(0, 6, 0, 0)
        linha.addWidget(rotulo("Na", "campo"))
        linha.addWidget(self.campo_ordinal, 1)
        linha.addWidget(self.campo_dia_semana_mes, 2)
        linha.addWidget(rotulo("do mês", "campo"))
        return pagina

    def _pagina_dia_mes(self) -> QWidget:
        pagina = QWidget()
        coluna = QVBoxLayout(pagina)
        coluna.setContentsMargins(0, 6, 0, 0)
        linha = QHBoxLayout()
        linha.addWidget(rotulo("Todo dia", "campo"))
        linha.addWidget(self.campo_dia_mes)
        linha.addWidget(rotulo("do mês", "campo"))
        linha.addStretch(1)
        coluna.addLayout(linha)
        coluna.addWidget(self.campo_util)
        return pagina

    # ---------------------------------------------------------------- dados
    def _carregar_listas(self, regra: Recorrencia | None) -> None:
        try:
            with session_scope() as sessao:
                tipos = repo_tipos.listar(sessao, apenas_ativos=True)
                if regra is not None and all(t.id != regra.tipo_servico_id for t in tipos):
                    antigo = repo_tipos.obter(sessao, regra.tipo_servico_id)
                    if antigo is not None:
                        tipos.append(antigo)
                pessoas = repo_solicitantes.listar(sessao, apenas_ativos=True)
        except Exception as erro:
            mostrar_erro(self, erro, "Erro ao carregar as listas")
            return

        self.campo_servico.clear()
        for tipo in tipos:
            cor, _ = cores_da_etiqueta(tipo.estilo)
            self.campo_servico.addItem(
                f"{glifo_da_etiqueta(tipo.estilo)}   {tipo.nome}", tipo.id
            )
            self.campo_servico.setItemData(
                self.campo_servico.count() - 1, QColor(cor),
                Qt.ItemDataRole.ForegroundRole,
            )

        # Endereço é obrigatório, aqui também: o serviço gerado precisa dele.
        self.campo_endereco.clear()
        if not self._cliente.enderecos:
            self.campo_endereco.addItem("Sem endereço cadastrado", None)
            self.campo_endereco.setEnabled(False)
            self.campo_ativo.setChecked(False)
            self.campo_ativo.setEnabled(False)
            self.campo_ativo.setText(
                "Sem endereço, a regra fica parada"
            )
        else:
            for endereco in self._cliente.enderecos:
                self.campo_endereco.addItem(
                    f"{endereco.tipo.value} — {endereco.resumo()}", endereco.id
                )

        self.campo_solicitante.clear()
        self.campo_solicitante.addItem("Não informar", None)
        for pessoa in pessoas:
            self.campo_solicitante.addItem(pessoa.nome_exibicao, pessoa.id)

    def _preencher(self, regra: Recorrencia | None) -> None:
        if regra is None:
            self.campo_frequencia.definir_valor(FrequenciaRecorrencia.MENSAL_ORDINAL)
            self._trocar_frequencia(FrequenciaRecorrencia.MENSAL_ORDINAL)
            return
        selecionar_dado(self.campo_servico, regra.tipo_servico_id)
        selecionar_dado(self.campo_endereco, regra.endereco_id)
        selecionar_dado(self.campo_solicitante, regra.solicitante_id)
        self.campo_periodo.definir_valor(regra.periodo)
        self.campo_frequencia.definir_valor(regra.frequencia)
        if regra.dia_semana is not None:
            selecionar_dado(self.campo_dia_semana, regra.dia_semana)
            selecionar_dado(self.campo_dia_semana_mes, regra.dia_semana)
        if regra.ordinal is not None:
            selecionar_dado(self.campo_ordinal, regra.ordinal)
        if regra.dia_mes is not None:
            self.campo_dia_mes.setValue(regra.dia_mes)
        self.campo_util.setChecked(regra.apenas_util)
        self.campo_ativo.setChecked(regra.ativo)
        self._trocar_frequencia(regra.frequencia)

    def _trocar_frequencia(self, frequencia: FrequenciaRecorrencia) -> None:
        ordem = list(FrequenciaRecorrencia)
        self.paginas.setCurrentIndex(ordem.index(frequencia))
        self._atualizar_previa()

    def _dados(self) -> DadosRecorrencia:
        frequencia = self.campo_frequencia.valor()
        return DadosRecorrencia(
            cliente_id=self._cliente.id,
            tipo_servico_id=self.campo_servico.currentData(),
            frequencia=frequencia,
            periodo=self.campo_periodo.valor(),
            endereco_id=self.campo_endereco.currentData(),
            solicitante_id=self.campo_solicitante.currentData(),
            dia_semana=(
                self.campo_dia_semana.currentData()
                if frequencia is FrequenciaRecorrencia.SEMANAL
                else self.campo_dia_semana_mes.currentData()
            ),
            ordinal=self.campo_ordinal.currentData(),
            dia_mes=self.campo_dia_mes.value(),
            apenas_util=self.campo_util.isChecked(),
            ativo=self.campo_ativo.isChecked(),
        )

    def _atualizar_previa(self) -> None:
        """Mostra as próximas datas — é a prova de que a regra faz o esperado."""
        dados = self._dados()
        provisoria = Recorrencia(
            frequencia=dados.frequencia,
            dia_semana=dados.dia_semana,
            ordinal=dados.ordinal,
            dia_mes=dados.dia_mes,
            apenas_util=dados.apenas_util,
        )
        hoje = date.today()
        datas = repo_recorrencias.ocorrencias(
            provisoria, hoje, hoje + timedelta(days=250)
        )[:4]
        if not datas:
            self.previa.setText("Essa regra não cai em nenhuma data nos próximos meses.")
            return
        self.previa.setText(
            f"{repo_recorrencias.descrever(provisoria)} · próximas: "
            + ", ".join(d.strftime("%d/%m/%Y") for d in datas)
        )

    def _salvar(self) -> None:
        try:
            dados = self._dados()
            if dados.tipo_servico_id is None:
                raise ValueError("Cadastre ao menos um tipo de serviço.")
            # Regra desligada pode ficar sem endereço: é o que permite
            # desligar uma que perdeu o endereço do cadastro.
            if dados.endereco_id is None and dados.ativo:
                raise ValueError(
                    f"“{self._cliente.nome_exibicao}” não tem endereço"
                    " cadastrado.\n\nCadastre o endereço, ou desmarque"
                    " “abrir automaticamente”."
                )
            with session_scope() as sessao:
                if self._regra_id is None:
                    regra = repo_recorrencias.criar(sessao, dados)
                else:
                    regra = repo_recorrencias.atualizar(sessao, self._regra_id, dados)
                self.recorrencia_id = regra.id
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para salvar")
            return
        self.accept()
