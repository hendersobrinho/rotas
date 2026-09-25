"""Aba de clientes: busca, ficha com os dois endereços e histórico de serviços."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.db import session_scope
from app.models import Cliente, Evento, TipoCliente
from app.repository import clientes as repo_clientes
from app.repository import eventos as repo_eventos
from app.repository import recorrencias as repo_recorrencias
from app.schemas import DadosCliente
from app.ui.datas import Agrupamento, agrupar
from app.ui.estilo import COR_STATUS, CORES, FONTE_DADOS, marcar
from app.ui.mensagens import confirmar, mostrar_erro
from app.ui.recorrencia_dialog import RecorrenciaDialog
from app.ui.widgets import (
    EnderecoForm,
    Segmentado,
    cartao,
    configurar_tabela,
    dado_da_linha,
    preencher_linha,
    rotulo,
)

COLUNAS_CLIENTES = ("Cliente", "Tipo")
COLUNAS_HISTORICO = ("Data", "Serviço", "Situação")
COLUNAS_FIXOS = ("Quando", "Serviço", "Período", "Situação")


def _situacao_do_fixo(regra) -> str:
    """Regra ligada mas sem endereço não abre nada — a lista precisa dizer."""
    if not regra.ativo:
        return "Parado"
    return "Ativo" if regra.endereco_id is not None else "Sem endereço"


def _rotulo_endereco(evento: Evento) -> str:
    return "—" if evento.endereco is None else evento.endereco.etiqueta


class ClientesTab(QWidget):
    """Lista à esquerda, ficha e histórico à direita."""

    dados_alterados = Signal()
    abrir_dia = Signal(date)  # duplo clique no histórico abre o dia no calendário

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cliente_id: int | None = None
        self._carregando = False
        self._historico: list[Evento] = []
        self._editando = False

        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.setHandleWidth(16)
        splitter.addWidget(self._montar_lista())
        splitter.addWidget(self._montar_ficha())
        splitter.addWidget(self._montar_historico())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)
        splitter.setSizes([290, 620, 350])

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 10, 18, 18)
        layout.addWidget(splitter)

        self.recarregar()
        self._modo_vazio()

    # ----------------------------------------------------------------- lista
    def _montar_lista(self) -> QWidget:
        caixa = cartao()
        caixa.setMinimumWidth(280)
        layout = QVBoxLayout(caixa)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        topo = QHBoxLayout()
        topo.addWidget(rotulo("Clientes", "secao"))
        topo.addStretch(1)
        self.contador = rotulo("", "fraco")
        topo.addWidget(self.contador)
        layout.addLayout(topo)

        self.busca = QLineEdit()
        self.busca.setPlaceholderText("Buscar por nome ou apelido")
        self.busca.setClearButtonEnabled(True)
        self.busca.textChanged.connect(lambda _texto: self.recarregar())
        layout.addWidget(self.busca)

        self.tabela = QTableWidget()
        configurar_tabela(self.tabela, COLUNAS_CLIENTES, coluna_elastica=0)
        self.tabela.itemSelectionChanged.connect(self._ao_trocar_selecao)
        layout.addWidget(self.tabela)

        self.btn_novo = QPushButton("Novo cliente")
        marcar(self.btn_novo, variante="primario")
        self.btn_novo.clicked.connect(self._novo)
        layout.addWidget(self.btn_novo)
        return caixa

    # ----------------------------------------------------------------- ficha
    def _montar_ficha(self) -> QWidget:
        self.campo_tipo = Segmentado(TipoCliente)
        self.nome = QLineEdit()
        self.nome.setPlaceholderText("Razão social (PJ) ou nome completo (PF)")
        self.apelido = QLineEdit()
        self.apelido.setPlaceholderText("Como a pessoa gosta de ser chamada")
        self.telefone = QLineEdit()
        self.observacao = QPlainTextEdit()
        self.observacao.setMaximumHeight(70)
        self.observacao.setPlaceholderText("Combinados, recados, horários...")

        self.cartao_dados = cartao(plano=True)
        dados = QVBoxLayout(self.cartao_dados)
        dados.setContentsMargins(16, 14, 16, 16)
        dados.setSpacing(10)

        self.titulo_ficha = rotulo("Ficha do cliente", "secao")
        self.btn_excluir = QPushButton("Excluir cliente")
        marcar(self.btn_excluir, variante="perigo")
        self.btn_excluir.clicked.connect(self._excluir)
        self.btn_editar = QPushButton("Editar cliente")
        marcar(self.btn_editar, variante="primario")
        self.btn_editar.clicked.connect(self._editar)
        self.btn_descartar = QPushButton("Descartar")
        self.btn_descartar.clicked.connect(self._descartar)
        self.btn_salvar = QPushButton("Salvar")
        marcar(self.btn_salvar, variante="primario")
        self.btn_salvar.clicked.connect(self._salvar)

        # No topo da ficha: as ações ficam sempre à vista, sem rolar a página.
        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(8)
        cabecalho.addWidget(self.titulo_ficha)
        cabecalho.addStretch(1)
        for botao in (
            self.btn_excluir,
            self.btn_editar,
            self.btn_descartar,
            self.btn_salvar,
        ):
            cabecalho.addWidget(botao)
        dados.addLayout(cabecalho)

        linha_tipo = QHBoxLayout()
        linha_tipo.addWidget(self.campo_tipo)
        linha_tipo.addStretch(1)
        dados.addLayout(linha_tipo)

        for etiqueta, campo in (
            ("Nome / razão social", self.nome),
            ("Apelido / nome social", self.apelido),
            ("Telefone", self.telefone),
            ("Observação", self.observacao),
        ):
            dados.addWidget(rotulo(etiqueta, "campo"))
            dados.addWidget(campo)


        conteudo = QWidget()
        coluna = QVBoxLayout(conteudo)
        coluna.setContentsMargins(0, 0, 10, 0)
        coluna.setSpacing(14)
        coluna.addWidget(self.cartao_dados)
        coluna.addWidget(self._montar_enderecos())
        coluna.addWidget(self._montar_fixos())
        coluna.addStretch(1)

        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setWidget(conteudo)
        rolagem.setMinimumWidth(480)
        return rolagem

    def _montar_fixos(self) -> QWidget:
        """Serviços que a agenda abre sozinha para este cliente."""
        painel = cartao(plano=True)
        coluna = QVBoxLayout(painel)
        coluna.setContentsMargins(16, 14, 16, 16)
        coluna.setSpacing(10)

        topo = QHBoxLayout()
        topo.addWidget(rotulo("Serviços automáticos", "secao"))
        topo.addStretch(1)
        self.contador_fixos = rotulo("", "fraco")
        topo.addWidget(self.contador_fixos)
        coluna.addLayout(topo)
        coluna.addWidget(
            rotulo(
                "Cliente fixo: a agenda abre o serviço sozinha, pelos próximos"
                " dois meses.",
                "fraco",
            )
        )

        self.tabela_fixos = QTableWidget()
        configurar_tabela(self.tabela_fixos, COLUNAS_FIXOS, coluna_elastica=0)
        self.tabela_fixos.doubleClicked.connect(lambda _i: self._editar_fixo())
        self.tabela_fixos.setMinimumHeight(110)
        coluna.addWidget(self.tabela_fixos)

        self.btn_fixo_novo = QPushButton("Novo serviço fixo")
        marcar(self.btn_fixo_novo, variante="primario")
        self.btn_fixo_novo.clicked.connect(self._novo_fixo)
        self.btn_fixo_editar = QPushButton("Editar")
        self.btn_fixo_editar.clicked.connect(self._editar_fixo)
        self.btn_fixo_excluir = QPushButton("Excluir")
        marcar(self.btn_fixo_excluir, variante="perigo")
        self.btn_fixo_excluir.clicked.connect(self._excluir_fixo)
        self.btn_fixo_gerar = QPushButton("Gerar agora")
        self.btn_fixo_gerar.clicked.connect(self._gerar_fixos)

        acoes = QHBoxLayout()
        acoes.addWidget(self.btn_fixo_novo)
        acoes.addWidget(self.btn_fixo_gerar)
        acoes.addStretch(1)
        acoes.addWidget(self.btn_fixo_editar)
        acoes.addWidget(self.btn_fixo_excluir)
        coluna.addLayout(acoes)

        self.cartao_fixos = painel
        return painel

    # ------------------------------------------------------------ endereços
    def _montar_enderecos(self) -> QWidget:
        """Lista de endereços: quantos o cliente tiver, com botão de incluir."""
        painel = cartao(plano=True)
        coluna = QVBoxLayout(painel)
        coluna.setContentsMargins(16, 14, 16, 16)
        coluna.setSpacing(10)

        self.btn_endereco_novo = QPushButton("Adicionar endereço")
        self.btn_endereco_novo.clicked.connect(self._adicionar_endereco)

        # No cabeçalho do cartão, e visível mesmo fora da edição: clicar já
        # abre a ficha para editar. Escondido no fim da lista, ninguém acha.
        topo = QHBoxLayout()
        topo.addWidget(rotulo("Endereços", "secao"))
        self.contador_enderecos = rotulo("", "fraco")
        topo.addWidget(self.contador_enderecos)
        topo.addStretch(1)
        topo.addWidget(self.btn_endereco_novo)
        coluna.addLayout(topo)

        self.aviso_enderecos = rotulo(
            "Nenhum endereço cadastrado — sem endereço não dá para marcar"
            " serviço.",
            "fraco",
        )
        coluna.addWidget(self.aviso_enderecos)

        self.lista_enderecos = QVBoxLayout()
        self.lista_enderecos.setSpacing(10)
        coluna.addLayout(self.lista_enderecos)

        self.cartao_enderecos = painel
        return painel

    def _formularios_endereco(self) -> list[EnderecoForm]:
        return [
            self.lista_enderecos.itemAt(i).widget()
            for i in range(self.lista_enderecos.count())
            if isinstance(self.lista_enderecos.itemAt(i).widget(), EnderecoForm)
        ]

    def _limpar_enderecos(self) -> None:
        while self.lista_enderecos.count():
            item = self.lista_enderecos.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()

    def _preencher_enderecos(self, cliente: Cliente | None) -> None:
        self._limpar_enderecos()
        enderecos = list(cliente.enderecos) if cliente is not None else []
        for endereco in enderecos:
            self._acrescentar_formulario(endereco)
        self._atualizar_resumo_enderecos()

    def _acrescentar_formulario(self, endereco=None) -> EnderecoForm:
        formulario = EnderecoForm(endereco)
        formulario.remocao_pedida.connect(self._remover_endereco)
        formulario.somente_leitura(not self._editando)
        self.lista_enderecos.addWidget(formulario)
        return formulario

    def _adicionar_endereco(self) -> None:
        """Só faz sentido editando — e entrar em edição é o passo anterior."""
        if not self._editando:
            self._editar()
        formulario = self._acrescentar_formulario()
        formulario.somente_leitura(False)
        formulario.rotulo_endereco.setFocus()
        self._atualizar_resumo_enderecos()

    def _remover_endereco(self, formulario: EnderecoForm) -> None:
        self.lista_enderecos.removeWidget(formulario)
        formulario.setParent(None)
        formulario.deleteLater()
        self._atualizar_resumo_enderecos()

    def _atualizar_resumo_enderecos(self) -> None:
        quantos = len(self._formularios_endereco())
        self.contador_enderecos.setText(f"{quantos}" if quantos else "")
        self.aviso_enderecos.setVisible(quantos == 0)

    # ---------------------------------------------------------- automáticos
    def _preencher_fixos(self) -> None:
        if self._cliente_id is None:
            self.tabela_fixos.setRowCount(0)
            self.contador_fixos.setText("")
            self.cartao_fixos.setEnabled(False)
            return
        try:
            with session_scope() as sessao:
                regras = repo_recorrencias.listar(sessao, self._cliente_id)
                gerados = {
                    regra.id: repo_recorrencias.contar_gerados(sessao, regra.id)
                    for regra in regras
                }
        except Exception as erro:
            mostrar_erro(self, erro, "Erro ao carregar os serviços fixos")
            return

        self.cartao_fixos.setEnabled(True)
        self.tabela_fixos.setRowCount(len(regras))
        for linha, regra in enumerate(regras):
            preencher_linha(
                self.tabela_fixos,
                linha,
                (
                    repo_recorrencias.descrever(regra),
                    regra.tipo_servico.nome,
                    regra.periodo.value,
                    _situacao_do_fixo(regra),
                ),
                dado=regra.id,
            )
            item = self.tabela_fixos.item(linha, 0)
            if item is not None:
                item.setToolTip(f"{gerados.get(regra.id, 0)} serviço(s) já abertos")
            situacao = self.tabela_fixos.item(linha, 3)
            if situacao is not None and regra.ativo and regra.endereco_id is None:
                situacao.setForeground(QColor(CORES["vermelho"]))
                situacao.setToolTip(
                    "Sem endereço, a geração automática pula esta regra."
                )
            if not regra.ativo:
                for coluna in range(self.tabela_fixos.columnCount()):
                    celula = self.tabela_fixos.item(linha, coluna)
                    if celula is not None:
                        celula.setForeground(QColor(CORES["tinta_fraca"]))
        self.contador_fixos.setText(f"{len(regras)}")

    def _cliente_carregado(self) -> Cliente | None:
        if self._cliente_id is None:
            return None
        with session_scope() as sessao:
            return repo_clientes.obter_cliente(sessao, self._cliente_id)

    def _fixo_selecionado(self) -> int | None:
        linhas = self.tabela_fixos.selectionModel().selectedRows()
        if not linhas:
            return None
        valor = dado_da_linha(self.tabela_fixos, linhas[0].row())
        return None if valor is None else int(valor)

    def _novo_fixo(self) -> None:
        cliente = self._cliente_carregado()
        if cliente is None:
            return
        if RecorrenciaDialog(self, cliente).exec() == QDialog.DialogCode.Accepted:
            self._preencher_fixos()
            self.dados_alterados.emit()

    def _editar_fixo(self) -> None:
        cliente = self._cliente_carregado()
        regra_id = self._fixo_selecionado()
        if cliente is None or regra_id is None:
            return
        with session_scope() as sessao:
            regra = repo_recorrencias.obter(sessao, regra_id)
        if regra is None:
            self._preencher_fixos()
            return
        if RecorrenciaDialog(self, cliente, regra).exec() == QDialog.DialogCode.Accepted:
            self._preencher_fixos()
            self.dados_alterados.emit()

    def _excluir_fixo(self) -> None:
        regra_id = self._fixo_selecionado()
        if regra_id is None:
            return
        with session_scope() as sessao:
            regra = repo_recorrencias.obter(sessao, regra_id)
            descricao = repo_recorrencias.descrever(regra) if regra else ""
            gerados = repo_recorrencias.contar_gerados(sessao, regra_id)
        if not confirmar(
            self,
            "Excluir serviço fixo",
            f"Parar de abrir “{descricao}”?\n\n"
            f"Os {gerados} serviço(s) já abertos continuam na agenda.",
        ):
            return
        try:
            with session_scope() as sessao:
                repo_recorrencias.excluir(sessao, regra_id)
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para excluir")
            return
        self._preencher_fixos()
        self.dados_alterados.emit()

    def _gerar_fixos(self) -> None:
        """Abre agora o que as regras deste cliente já permitem abrir."""
        if self._cliente_id is None:
            return
        try:
            with session_scope() as sessao:
                criados = repo_recorrencias.gerar(sessao, cliente_id=self._cliente_id)
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para gerar")
            return
        self._preencher_fixos()
        self._abrir(self._cliente_id)
        self.dados_alterados.emit()
        sem_endereco = [
            regra
            for regra in self._regras_do_cliente()
            if regra.ativo and regra.endereco_id is None
        ]
        recado = (
            f"{len(criados)} serviço(s) aberto(s) na agenda."
            if criados
            else "Não havia nada novo para abrir."
        )
        if sem_endereco:
            recado += (
                f"\n\n{len(sem_endereco)} regra(s) estão sem endereço e não"
                " abrem nada. Edite e escolha o endereço, ou desligue."
            )
        QMessageBox.information(self, "Serviços automáticos", recado)

    def _regras_do_cliente(self) -> list:
        if self._cliente_id is None:
            return []
        try:
            with session_scope() as sessao:
                return repo_recorrencias.listar(sessao, self._cliente_id)
        except Exception:
            return []

    # ------------------------------------------------------------- histórico
    def _montar_historico(self) -> QWidget:
        painel = cartao()
        painel.setMinimumWidth(300)
        layout = QVBoxLayout(painel)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)

        self.titulo_historico = rotulo("Histórico de serviços", "secao")
        layout.addWidget(self.titulo_historico)
        layout.addWidget(
            rotulo("Clique duas vezes para abrir o dia na agenda.", "fraco")
        )

        self.campo_agrupamento = Segmentado(Agrupamento)
        self.campo_agrupamento.definir_valor(Agrupamento.MES)
        self.campo_agrupamento.mudou.connect(lambda _modo: self._desenhar_historico())
        seletor = QHBoxLayout()
        seletor.setSpacing(8)
        seletor.addWidget(rotulo("Agrupar por", "campo"))
        seletor.addWidget(self.campo_agrupamento)
        seletor.addStretch(1)
        layout.addLayout(seletor)

        self.tabela_historico = QTableWidget()
        configurar_tabela(self.tabela_historico, COLUNAS_HISTORICO, coluna_elastica=1)
        self.tabela_historico.doubleClicked.connect(self._ao_duplo_clique_historico)
        # Coluna da data com largura fixa: a linha de cabeçalho do grupo ocupa
        # as três colunas e não deve influenciar a largura de nenhuma delas.
        cabecalho = self.tabela_historico.horizontalHeader()
        cabecalho.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.tabela_historico.setColumnWidth(0, 108)
        layout.addWidget(self.tabela_historico)
        return painel

    # ----------------------------------------------------------------- dados
    def recarregar(self) -> None:
        """Relê a lista de clientes preservando a seleção atual."""
        selecionado = self._cliente_id
        self._carregando = True
        try:
            with session_scope() as sessao:
                encontrados = repo_clientes.listar_clientes(sessao, self.busca.text())

            self.tabela.setRowCount(len(encontrados))
            for linha, cliente in enumerate(encontrados):
                preencher_linha(
                    self.tabela,
                    linha,
                    (cliente.nome_exibicao, cliente.tipo.name),
                    dado=cliente.id,
                )
                item = self.tabela.item(linha, 0)
                if item is not None:
                    item.setToolTip(self._rotulo(cliente))
            self.contador.setText(f"{len(encontrados)}")
        except Exception as erro:
            mostrar_erro(self, erro, "Erro ao listar clientes")
            return
        finally:
            self._carregando = False

        if selecionado is not None and not self._selecionar_na_tabela(selecionado):
            self._modo_vazio()

    def selecionar_cliente(self, cliente_id: int) -> None:
        if not self._selecionar_na_tabela(cliente_id):
            self.busca.clear()
            self._selecionar_na_tabela(cliente_id)

    def _selecionar_na_tabela(self, cliente_id: int) -> bool:
        for linha in range(self.tabela.rowCount()):
            if dado_da_linha(self.tabela, linha) == cliente_id:
                self.tabela.selectRow(linha)
                return True
        return False

    def _ao_trocar_selecao(self) -> None:
        if self._carregando:
            return
        linhas = self.tabela.selectionModel().selectedRows()
        if not linhas:
            return
        cliente_id = dado_da_linha(self.tabela, linhas[0].row())
        if cliente_id is not None:
            self._abrir(int(cliente_id))

    def _ao_duplo_clique_historico(self, indice) -> None:
        dia = dado_da_linha(self.tabela_historico, indice.row())
        if isinstance(dia, date):
            self.abrir_dia.emit(dia)

    def _abrir(self, cliente_id: int) -> None:
        try:
            with session_scope() as sessao:
                cliente = repo_clientes.obter_cliente(sessao, cliente_id)
                if cliente is None:
                    self.recarregar()
                    return
                historico = repo_eventos.historico_cliente(sessao, cliente_id)
        except Exception as erro:
            mostrar_erro(self, erro, "Erro ao abrir cliente")
            return

        self._cliente_id = cliente_id
        self._preencher_ficha(cliente)
        self._preencher_historico(historico)
        self._preencher_fixos()
        self._modo_edicao(False)

    def _preencher_ficha(self, cliente: Cliente) -> None:
        self.campo_tipo.definir_valor(cliente.tipo)
        self.nome.setText(cliente.nome)
        self.apelido.setText(cliente.apelido or "")
        self.telefone.setText(cliente.telefone or "")
        self.observacao.setPlainText(cliente.observacao or "")
        self._preencher_enderecos(cliente)
        self.titulo_ficha.setText(cliente.nome_exibicao)

    def _preencher_historico(self, historico: list[Evento]) -> None:
        self._historico = historico
        self.titulo_historico.setText(f"Histórico de serviços ({len(historico)})")
        self._desenhar_historico()

    def _desenhar_historico(self) -> None:
        """Redesenha a tabela agrupada pelo período escolhido no seletor."""
        tabela = self.tabela_historico
        grupos = agrupar(self._historico, self.campo_agrupamento.valor())

        tabela.clearSpans()
        tabela.setRowCount(sum(1 + len(eventos) for _, eventos in grupos))

        linha = 0
        for titulo, eventos in grupos:
            self._linha_de_grupo(linha, f"{titulo}  ·  {len(eventos)}")
            linha += 1
            for evento in eventos:
                preencher_linha(
                    tabela,
                    linha,
                    (
                        evento.data.strftime("%d/%m/%Y"),
                        evento.tipo_servico.nome,
                        evento.status.value,
                    ),
                    dado=evento.data,
                )
                detalhe = "\n".join(
                    [
                        f"Período: {evento.periodo.value}",
                        f"Endereço: {_rotulo_endereco(evento)}",
                        "Solicitante: "
                        + (evento.solicitante.nome_exibicao
                           if evento.solicitante else "—"),
                    ]
                )
                for coluna in range(tabela.columnCount()):
                    item = tabela.item(linha, coluna)
                    if item is not None:
                        item.setToolTip(detalhe)
                cor, _ = COR_STATUS[evento.status]
                situacao = tabela.item(linha, 2)
                if situacao is not None:
                    situacao.setForeground(QColor(cor))
                linha += 1

    def _linha_de_grupo(self, linha: int, texto: str) -> None:
        """Faixa que abre cada período, ocupando a largura toda da tabela."""
        item = QTableWidgetItem(texto.upper())
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)  # visível, mas não selecionável
        item.setFont(QFont(FONTE_DADOS, 8, QFont.Weight.DemiBold))
        item.setForeground(QColor(CORES["tinta_fraca"]))
        item.setBackground(QColor(CORES["papel_suave"]))
        self.tabela_historico.setItem(linha, 0, item)
        self.tabela_historico.setSpan(linha, 0, 1, self.tabela_historico.columnCount())
        self.tabela_historico.setRowHeight(linha, 26)

    # ----------------------------------------------------------------- ações
    def _editar(self) -> None:
        """Só aqui a ficha fica editável — navegar pela lista não mexe em nada."""
        if self._cliente_id is None:
            return
        self._modo_edicao(True)
        self.nome.setFocus()

    def _novo(self) -> None:
        self.tabela.clearSelection()
        self._cliente_id = None
        self.campo_tipo.definir_valor(TipoCliente.PF)
        self.nome.clear()
        self.apelido.clear()
        self.telefone.clear()
        self.observacao.clear()
        self._preencher_enderecos(None)
        self._preencher_historico([])
        self.titulo_historico.setText("Histórico de serviços")
        self.titulo_ficha.setText("Novo cliente")
        self._modo_edicao(True)
        self.nome.setFocus()

    def _descartar(self) -> None:
        if self._cliente_id is None:
            self._modo_vazio()
        else:
            self._abrir(self._cliente_id)  # relê do banco e volta para leitura

    def _salvar(self) -> None:
        dados = DadosCliente(
            tipo=self.campo_tipo.valor(),
            nome=self.nome.text(),
            apelido=self.apelido.text(),
            telefone=self.telefone.text(),
            observacao=self.observacao.toPlainText(),
            enderecos=[f.dados() for f in self._formularios_endereco()],
        )
        try:
            with session_scope() as sessao:
                if self._cliente_id is None:
                    cliente = repo_clientes.criar_cliente(sessao, dados)
                else:
                    cliente = repo_clientes.atualizar_cliente(
                        sessao, self._cliente_id, dados
                    )
                novo_id = cliente.id
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para salvar")
            return

        self._cliente_id = novo_id
        self._modo_edicao(False)
        self.recarregar()
        self._selecionar_na_tabela(novo_id)
        self._abrir(novo_id)
        self.dados_alterados.emit()

    def _excluir(self) -> None:
        if self._cliente_id is None:
            return
        try:
            with session_scope() as sessao:
                cliente = repo_clientes.obter_cliente(sessao, self._cliente_id)
                if cliente is None:
                    self.recarregar()
                    return
                nome = cliente.nome_exibicao
                total = repo_eventos.contar_eventos_do_cliente(sessao, self._cliente_id)
        except Exception as erro:
            mostrar_erro(self, erro, "Erro ao consultar cliente")
            return

        aviso = f"Excluir o cliente “{nome}”?"
        if total:
            aviso += f"\n\nIsto também apaga {total} serviço(s) do histórico."
        if not confirmar(self, "Excluir cliente", aviso):
            return

        try:
            with session_scope() as sessao:
                repo_clientes.excluir_cliente(sessao, self._cliente_id)
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para excluir")
            return

        self._cliente_id = None
        self.recarregar()
        self._modo_vazio()
        self.dados_alterados.emit()

    # ---------------------------------------------------------------- estado
    def _modo_vazio(self) -> None:
        self._cliente_id = None
        self._editando = False
        self.nome.clear()
        self.apelido.clear()
        self.telefone.clear()
        self.observacao.clear()
        self._preencher_enderecos(None)
        self._preencher_historico([])
        self._preencher_fixos()
        self.titulo_historico.setText("Histórico de serviços")
        self.titulo_ficha.setText("Escolha um cliente na lista")
        self._modo_edicao(False)

    def _modo_edicao(self, editando: bool) -> None:
        """Alterna entre ler a ficha e mexer nela.

        Navegar pela lista mantém tudo só de leitura; a ficha só abre para
        edição pelo botão, ou ao criar um cliente novo.
        """
        self._editando = editando
        tem_ficha = editando or self._cliente_id is not None

        for campo in (self.nome, self.apelido, self.telefone):
            campo.setReadOnly(not editando)
            marcar(campo, leitura=not editando)
        self.observacao.setReadOnly(not editando)
        marcar(self.observacao, leitura=not editando)
        self.campo_tipo.somente_leitura(not editando)
        for formulario in self._formularios_endereco():
            formulario.somente_leitura(not editando)
        self.btn_endereco_novo.setVisible(tem_ficha)

        for widget in (self.cartao_dados, self.cartao_enderecos):
            widget.setEnabled(tem_ficha)

        self.btn_editar.setVisible(not editando and self._cliente_id is not None)
        self.btn_salvar.setVisible(editando)
        self.btn_descartar.setVisible(editando)
        self.btn_excluir.setVisible(not editando and self._cliente_id is not None)

        # Enquanto edita, a lista fica travada: ou salva, ou descarta.
        self.tabela.setEnabled(not editando)
        self.busca.setEnabled(not editando)
        self.btn_novo.setEnabled(not editando)

    @staticmethod
    def _rotulo(cliente: Cliente) -> str:
        """Texto completo do cliente, usado na dica da lista."""
        if cliente.apelido and cliente.apelido != cliente.nome:
            return f"{cliente.apelido} · {cliente.nome}"
        return cliente.nome
