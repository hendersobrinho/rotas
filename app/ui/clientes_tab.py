"""Aba de clientes: busca, ficha com os dois endereços e histórico de serviços."""

from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QTableWidgetItem,
    QHBoxLayout,
    QHeaderView,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from app.db import session_scope
from app.models import Cliente, Evento, TipoCliente, TipoEndereco
from app.repository import clientes as repo_clientes
from app.repository import eventos as repo_eventos
from app.schemas import DadosCliente
from app.ui.datas import Agrupamento, agrupar
from app.ui.estilo import COR_STATUS, CORES, FONTE_DADOS, marcar
from app.ui.mensagens import confirmar, mostrar_erro
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


def _rotulo_endereco(evento: Evento) -> str:
    return "—" if evento.endereco is None else evento.endereco.tipo.value


class ClientesTab(QWidget):
    """Lista à esquerda, ficha e histórico à direita."""

    dados_alterados = Signal()
    abrir_dia = Signal(date)  # duplo clique no histórico abre o dia no calendário

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cliente_id: int | None = None
        self._carregando = False
        self._historico: list[Evento] = []

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

        cabecalho = QHBoxLayout()
        self.titulo_ficha = rotulo("Ficha do cliente", "secao")
        cabecalho.addWidget(self.titulo_ficha)
        cabecalho.addStretch(1)
        self.btn_excluir = QPushButton("Excluir cliente")
        marcar(self.btn_excluir, variante="perigo")
        self.btn_excluir.clicked.connect(self._excluir)
        cabecalho.addWidget(self.btn_excluir)
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

        self.form_residencial = EnderecoForm(TipoEndereco.RESIDENCIAL)
        self.form_comercial = EnderecoForm(TipoEndereco.COMERCIAL)

        self.btn_salvar = QPushButton("Salvar")
        marcar(self.btn_salvar, variante="primario")
        self.btn_salvar.clicked.connect(self._salvar)
        self.btn_descartar = QPushButton("Descartar alterações")
        self.btn_descartar.clicked.connect(self._descartar)

        acoes = QHBoxLayout()
        acoes.addStretch(1)
        acoes.addWidget(self.btn_descartar)
        acoes.addWidget(self.btn_salvar)

        conteudo = QWidget()
        coluna = QVBoxLayout(conteudo)
        coluna.setContentsMargins(0, 0, 10, 0)
        coluna.setSpacing(14)
        coluna.addWidget(self.cartao_dados)
        coluna.addWidget(self.form_residencial)
        coluna.addWidget(self.form_comercial)
        coluna.addLayout(acoes)
        coluna.addStretch(1)

        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setWidget(conteudo)
        rolagem.setMinimumWidth(480)
        return rolagem

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
        self._habilitar_ficha(True)

    def _preencher_ficha(self, cliente: Cliente) -> None:
        self.campo_tipo.definir_valor(cliente.tipo)
        self.nome.setText(cliente.nome)
        self.apelido.setText(cliente.apelido or "")
        self.telefone.setText(cliente.telefone or "")
        self.observacao.setPlainText(cliente.observacao or "")
        self.form_residencial.preencher(
            cliente.endereco_por_tipo(TipoEndereco.RESIDENCIAL)
        )
        self.form_comercial.preencher(cliente.endereco_por_tipo(TipoEndereco.COMERCIAL))
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
                        evento.tipo_servico.value,
                        evento.status.value,
                    ),
                    dado=evento.data,
                )
                detalhe = "\n".join(
                    [
                        f"Período: {evento.periodo.value}",
                        f"Endereço: {_rotulo_endereco(evento)}",
                        f"Solicitante: {evento.solicitante or '—'}",
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
    def _novo(self) -> None:
        self.tabela.clearSelection()
        self._cliente_id = None
        self.campo_tipo.definir_valor(TipoCliente.PF)
        self.nome.clear()
        self.apelido.clear()
        self.telefone.clear()
        self.observacao.clear()
        self.form_residencial.limpar()
        self.form_comercial.limpar()
        self._preencher_historico([])
        self.titulo_historico.setText("Histórico de serviços")
        self.titulo_ficha.setText("Novo cliente")
        self._habilitar_ficha(True)
        self.nome.setFocus()

    def _descartar(self) -> None:
        if self._cliente_id is None:
            self._modo_vazio()
        else:
            self._abrir(self._cliente_id)

    def _salvar(self) -> None:
        dados = DadosCliente(
            tipo=self.campo_tipo.valor(),
            nome=self.nome.text(),
            apelido=self.apelido.text(),
            telefone=self.telefone.text(),
            observacao=self.observacao.toPlainText(),
            enderecos=[self.form_residencial.dados(), self.form_comercial.dados()],
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
        self.nome.clear()
        self.apelido.clear()
        self.telefone.clear()
        self.observacao.clear()
        self.form_residencial.limpar()
        self.form_comercial.limpar()
        self._preencher_historico([])
        self.titulo_historico.setText("Histórico de serviços")
        self.titulo_ficha.setText("Escolha um cliente na lista")
        self._habilitar_ficha(False)

    def _habilitar_ficha(self, ativo: bool) -> None:
        for widget in (
            self.cartao_dados,
            self.form_residencial,
            self.form_comercial,
            self.btn_salvar,
            self.btn_descartar,
        ):
            widget.setEnabled(ativo)
        self.btn_excluir.setVisible(ativo and self._cliente_id is not None)

    @staticmethod
    def _rotulo(cliente: Cliente) -> str:
        """Texto completo do cliente, usado na dica da lista."""
        if cliente.apelido and cliente.apelido != cliente.nome:
            return f"{cliente.apelido} · {cliente.nome}"
        return cliente.nome
