"""Clientes em três passos: a lista, a ficha (só leitura) e o cadastro.

  * Lista — todos os clientes, com busca e filtro PF/PJ. Clicar abre a ficha.
  * Ficha — o cliente como ele é: contato, endereços, sócios ou empresas
    ligadas, serviços automáticos e histórico. Nada aqui se edita sem querer.
  * Cadastro — o formulário, aberto pelo "Novo cliente" ou pelo "Editar
    cadastro" da ficha. Salvar volta para a ficha; cancelar, também.

Sócios: uma empresa (PJ) pode ter pessoas ligadas a ela — sócio,
administrador, procurador. A ficha da empresa mostra essas pessoas com
telefone e endereço (para quando a entrega é na casa de um sócio), e a ficha
da pessoa mostra de quais empresas ela faz parte.
"""

from __future__ import annotations

import enum
from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLayout,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.db import session_scope
from app.models import Cliente, Evento, SituacaoLembrancinha, TipoCliente, VinculoSocio
from app.repository import clientes as repo_clientes
from app.repository import eventos as repo_eventos
from app.repository import lembrancinhas as repo_lembrancinhas
from app.repository import recorrencias as repo_recorrencias
from app.repository import socios as repo_socios
from app.schemas import DadosCliente
from app.ui.datas import Agrupamento, agrupar
from app.ui.estilo import COR_STATUS, CORES, FONTE_DADOS, FONTE_TITULO, marcar
from app.ui.importar_clientes import ImportarClientesDialog
from app.ui.mensagens import confirmar, mostrar_erro
from app.ui.recorrencia_dialog import RecorrenciaDialog
from app.ui.seletor_cliente import SeletorClienteDialog, sem_acento
from app.ui.widgets import (
    EnderecoForm,
    Segmentado,
    cartao,
    configurar_tabela,
    dado_da_linha,
    preencher_linha,
    rotulo,
)

COLUNAS_CLIENTES = ("Cliente", "Tipo", "Telefone", "Onde", "Vínculos")
COLUNAS_HISTORICO = ("Data", "Serviço", "Situação")
COLUNAS_FIXOS = ("Quando", "Serviço", "Período", "Situação")


class FiltroTipo(enum.Enum):
    TODOS = "Todos"
    PJ = "Empresas"
    PF = "Pessoas"


def _situacao_do_fixo(regra) -> str:
    """Regra ligada mas sem endereço não abre nada — a lista precisa dizer."""
    if not regra.ativo:
        return "Parado"
    return "Ativo" if regra.endereco_id is not None else "Sem endereço"


def _rotulo_endereco(evento: Evento) -> str:
    return "—" if evento.endereco is None else evento.endereco.etiqueta


def _iniciais(nome: str) -> str:
    partes = [p for p in nome.replace("-", " ").split() if p[:1].isalnum()]
    if not partes:
        return "?"
    if len(partes) == 1:
        return partes[0][:2].upper()
    return (partes[0][0] + partes[1][0]).upper()


def _onde(cliente: Cliente) -> str:
    """Cidade e bairro do primeiro endereço que tiver."""
    for endereco in cliente.enderecos:
        partes = [p for p in (endereco.bairro, endereco.cidade) if p]
        if partes:
            return " · ".join(partes)
    return "—"


def _limpar(layout: QLayout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget is not None:
            widget.setParent(None)
            widget.deleteLater()
        elif item.layout() is not None:
            _limpar(item.layout())


def _cores_do_tipo(tipo: TipoCliente) -> tuple[str, str]:
    """(texto, fundo): empresa em azul, pessoa em âmbar — nos dois temas."""
    if tipo is TipoCliente.PJ:
        return CORES["azul"], CORES["azul_claro"]
    return CORES["carimbo"], CORES["carimbo_claro"]


class Avatar(QLabel):
    """Círculo com as iniciais, na cor do tipo de cliente."""

    def __init__(self, nome: str, tipo: TipoCliente, lado: int = 40,
                 parent: QWidget | None = None) -> None:
        super().__init__(_iniciais(nome), parent)
        cor, fundo = _cores_do_tipo(tipo)
        self.setFixedSize(lado, lado)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            f"background: {fundo}; color: {cor}; border-radius: {lado // 2}px;"
            f' font-family: "{FONTE_TITULO}"; font-size: {max(11, lado // 3)}px;'
            " font-weight: 800;"
        )


def pilula(texto: str, cor: str, fundo: str) -> QLabel:
    etiqueta = QLabel(texto)
    etiqueta.setStyleSheet(
        f"background: {fundo}; color: {cor}; border-radius: 8px;"
        " padding: 2px 9px; font-size: 11px; font-weight: 700;"
    )
    return etiqueta


def pilula_lembrancinha(situacao: SituacaoLembrancinha, ano: int) -> QLabel:
    """O selo do cliente que recebe a lembrancinha de fim de ano."""
    cor, fundo = {
        SituacaoLembrancinha.A_ENTREGAR: (CORES["carimbo"], CORES["carimbo_claro"]),
        SituacaoLembrancinha.ENTREGUE: (CORES["verde"], CORES["verde_claro"]),
        SituacaoLembrancinha.NAO_ENVIAR: (CORES["tinta_media"], CORES["cinza_claro"]),
    }[situacao]
    etiqueta = pilula(f"🎁  LEMBRANCINHA {ano} · {situacao.value.upper()}", cor, fundo)
    etiqueta.setToolTip("Este cliente está na lista de lembrancinhas de fim de ano.")
    return etiqueta


def pilula_tipo(tipo: TipoCliente) -> QLabel:
    cor, fundo = _cores_do_tipo(tipo)
    return pilula("EMPRESA · PJ" if tipo is TipoCliente.PJ else "PESSOA · PF", cor, fundo)


def secao(titulo: str, apoio: str = "") -> tuple[QFrame, QVBoxLayout, QHBoxLayout]:
    """Cartão com título; devolve o cartão, o corpo e a linha do título."""
    painel = cartao(plano=True)
    coluna = QVBoxLayout(painel)
    coluna.setContentsMargins(18, 16, 18, 18)
    coluna.setSpacing(10)
    topo = QHBoxLayout()
    topo.setSpacing(8)
    topo.addWidget(rotulo(titulo, "secao"))
    coluna.addLayout(topo)
    if apoio:
        explicacao = rotulo(apoio, "fraco")
        explicacao.setWordWrap(True)
        coluna.addWidget(explicacao)
    return painel, coluna, topo


def botao(texto: str, variante: str | None = None, dica: str = "") -> QPushButton:
    criado = QPushButton(texto)
    criado.setCursor(Qt.CursorShape.PointingHandCursor)
    if variante:
        marcar(criado, variante=variante)
    if dica:
        criado.setToolTip(dica)
    return criado


# ======================================================================
# Vínculo: escolher a outra ponta e o papel
# ======================================================================
class VinculoDialog(QDialog):
    """Liga um cliente a outro: sócio de uma empresa, ou empresa de uma pessoa."""

    def __init__(self, parent: QWidget | None, cliente: Cliente,
                 clientes: list[Cliente], vinculo: VinculoSocio | None = None) -> None:
        super().__init__(parent)
        self._cliente = cliente
        self._vinculo = vinculo
        self.outro_id: int | None = None
        self.papel = repo_socios.PAPEL_PADRAO
        # Empresa escolhe a pessoa; pessoa escolhe a empresa (só PJ).
        self._e_empresa = cliente.tipo is TipoCliente.PJ
        if self._e_empresa:
            self._opcoes = [c for c in clientes if c.id != cliente.id]
        else:
            self._opcoes = [c for c in clientes if c.tipo is TipoCliente.PJ]

        self.setWindowTitle("Vínculo")
        self.setMinimumWidth(460)
        self.setStyleSheet(f"QDialog {{ background: {CORES['papel']}; }}")

        if vinculo is not None:
            titulo = "Mudar o papel"
            apoio = (
                f"{vinculo.pessoa.nome_exibicao} em {vinculo.empresa.nome_exibicao}."
            )
        elif self._e_empresa:
            titulo = "Vincular sócio"
            apoio = (
                f"Quem faz parte de {cliente.nome_exibicao}: sócio, administrador,"
                " procurador. A pessoa precisa estar cadastrada como cliente."
            )
        else:
            titulo = "Vincular a uma empresa"
            apoio = f"De qual empresa {cliente.nome_exibicao} faz parte."

        self.campo_outro = botao(
            "Escolher a pessoa…" if self._e_empresa else "Escolher a empresa…",
            "campo",
        )
        self.campo_outro.clicked.connect(self._escolher)
        self.campo_papel = QComboBox()
        self.campo_papel.setEditable(True)
        self.campo_papel.addItems(repo_socios.PAPEIS_SUGERIDOS)
        if vinculo is not None:
            self.campo_papel.setCurrentText(vinculo.papel)

        salvar = botao("Salvar vínculo", "primario")
        salvar.setDefault(True)
        salvar.clicked.connect(self._aceitar)
        cancelar = botao("Cancelar")
        cancelar.clicked.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(10)
        layout.addWidget(rotulo(titulo, "titulo"))
        texto = rotulo(apoio, "fraco")
        texto.setWordWrap(True)
        layout.addWidget(texto)
        layout.addSpacing(6)
        if vinculo is None:
            layout.addWidget(rotulo("Sócio ou pessoa" if self._e_empresa else "Empresa", "campo"))
            layout.addWidget(self.campo_outro)
        layout.addWidget(rotulo("Papel", "campo"))
        layout.addWidget(self.campo_papel)
        layout.addSpacing(10)
        rodape = QHBoxLayout()
        rodape.addStretch(1)
        rodape.addWidget(cancelar)
        rodape.addWidget(salvar)
        layout.addLayout(rodape)

    def _escolher(self) -> None:
        if not self._opcoes:
            mostrar_erro(
                self,
                ValueError(
                    "Nenhuma empresa (PJ) cadastrada ainda."
                    if not self._e_empresa else "Nenhum outro cliente cadastrado."
                ),
                "Nada para escolher",
            )
            return
        dialogo = SeletorClienteDialog(self, self._opcoes, self.outro_id)
        if dialogo.exec() == QDialog.DialogCode.Accepted and dialogo.cliente_id:
            self.outro_id = dialogo.cliente_id
            escolhido = next(c for c in self._opcoes if c.id == self.outro_id)
            self.campo_outro.setText(escolhido.nome_exibicao)

    def _aceitar(self) -> None:
        self.papel = self.campo_papel.currentText()
        if self._vinculo is None and self.outro_id is None:
            mostrar_erro(
                self, ValueError("Escolha com quem fazer o vínculo."), "Falta escolher"
            )
            return
        self.accept()


# ======================================================================
# Linha de um vínculo na ficha
# ======================================================================
class LinhaVinculo(QFrame):
    """Uma pessoa (ou empresa) ligada, com contato e onde encontrar."""

    abrir = Signal(int)
    mudar_papel = Signal(int)
    remover = Signal(int)

    def __init__(self, vinculo: VinculoSocio, outro: Cliente,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("linhaVinculo")
        self.setStyleSheet(
            f"QFrame#linhaVinculo {{ background: {CORES['papel_suave']};"
            f" border: 1px solid {CORES['pauta']}; border-radius: 12px; }}"
            "QFrame#linhaVinculo QLabel { background: transparent; }"
        )
        nome = QLabel(outro.nome_exibicao)
        nome.setStyleSheet(
            f"color: {CORES['tinta']}; font-weight: 800; font-size: 13px;"
        )
        nome.setWordWrap(True)
        papel = pilula(vinculo.papel.upper(), CORES["tinta_media"], CORES["cinza_claro"])

        topo = QHBoxLayout()
        topo.setSpacing(8)
        topo.addWidget(nome)
        topo.addWidget(papel)
        topo.addStretch(1)

        linhas = QVBoxLayout()
        linhas.setSpacing(3)
        linhas.addLayout(topo)
        detalhes = [outro.telefone] if outro.telefone else []
        if outro.apelido and outro.apelido != outro.nome:
            detalhes.insert(0, outro.nome)
        if detalhes:
            linhas.addWidget(rotulo(" · ".join(detalhes), "fraco"))
        for endereco in list(outro.enderecos)[:2]:
            texto = QLabel(f"📍 {endereco.etiqueta}: {endereco.resumo()}")
            texto.setWordWrap(True)
            texto.setStyleSheet(f"color: {CORES['tinta_media']}; font-size: 12px;")
            linhas.addWidget(texto)
        if not outro.enderecos:
            linhas.addWidget(rotulo("Sem endereço cadastrado", "fraco"))

        abrir = botao("Abrir ficha", "fantasma")
        abrir.clicked.connect(lambda: self.abrir.emit(outro.id))
        mudar = botao("Papel", "fantasma", "Mudar o papel (sócio, administrador…)")
        mudar.clicked.connect(lambda: self.mudar_papel.emit(vinculo.id))
        remover = botao("Desvincular", "fantasma", "Desfazer o vínculo")
        remover.clicked.connect(lambda: self.remover.emit(vinculo.id))
        acoes = QVBoxLayout()
        acoes.setSpacing(2)
        acoes.addWidget(abrir)
        acoes.addWidget(mudar)
        acoes.addWidget(remover)
        acoes.addStretch(1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 8, 10)
        layout.setSpacing(12)
        layout.addWidget(Avatar(outro.nome_exibicao, outro.tipo, 38), 0,
                         Qt.AlignmentFlag.AlignTop)
        layout.addLayout(linhas, 1)
        layout.addLayout(acoes)


# ======================================================================
# A tela
# ======================================================================
class ClientesTab(QWidget):
    """Lista, ficha e cadastro de clientes, um de cada vez."""

    dados_alterados = Signal()
    abrir_dia = Signal(date)  # duplo clique no histórico abre o dia no calendário

    PAGINA_LISTA = 0
    PAGINA_FICHA = 1
    PAGINA_CADASTRO = 2

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._cliente_id: int | None = None
        self._carregando = False
        self._historico: list[Evento] = []
        self._editando = False
        self._clientes: list[Cliente] = []
        self._contagem_vinculos: dict[int, tuple[int, int]] = {}
        self._lembrancinhas: dict[int, SituacaoLembrancinha] = {}

        self.pilha = QStackedWidget()
        self.pilha.addWidget(self._montar_lista())
        self.pilha.addWidget(self._montar_ficha())
        self.pilha.addWidget(self._montar_cadastro())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.addWidget(self.pilha)

        self.recarregar()
        self._modo_vazio()

    # ================================================================ lista
    def _montar_lista(self) -> QWidget:
        pagina = QWidget()
        coluna = QVBoxLayout(pagina)
        coluna.setContentsMargins(0, 0, 0, 0)
        coluna.setSpacing(14)

        titulos = QVBoxLayout()
        titulos.setSpacing(2)
        titulos.addWidget(rotulo("Clientes", "titulo"))
        self.resumo_lista = rotulo("", "fraco")
        titulos.addWidget(self.resumo_lista)

        self.btn_importar = botao(
            "Importar planilha", None,
            "Cadastra vários clientes de uma vez, a partir de uma planilha —"
            " e é de lá que sai o modelo em branco para preencher.",
        )
        self.btn_importar.clicked.connect(self._importar_planilha)
        self.btn_novo = botao("+  Novo cliente", "primario")
        self.btn_novo.clicked.connect(self._novo)

        cabecalho = QHBoxLayout()
        cabecalho.setSpacing(8)
        cabecalho.addLayout(titulos, 1)
        cabecalho.addWidget(self.btn_importar, 0, Qt.AlignmentFlag.AlignTop)
        cabecalho.addWidget(self.btn_novo, 0, Qt.AlignmentFlag.AlignTop)
        coluna.addLayout(cabecalho)

        filtros = cartao(plano=True)
        linha = QHBoxLayout(filtros)
        linha.setContentsMargins(12, 10, 12, 10)
        linha.setSpacing(10)
        self.busca = QLineEdit()
        self.busca.setPlaceholderText("Buscar por nome, apelido, telefone ou cidade")
        self.busca.setClearButtonEnabled(True)
        self.busca.textChanged.connect(lambda _texto: self._desenhar_lista())
        self.filtro_tipo = Segmentado(FiltroTipo)
        self.filtro_tipo.mudou.connect(lambda _v: self._desenhar_lista())
        self.contador = rotulo("", "fraco")
        linha.addWidget(self.busca, 1)
        linha.addWidget(self.filtro_tipo)
        linha.addWidget(self.contador)
        coluna.addWidget(filtros)

        caixa = cartao()
        dentro = QVBoxLayout(caixa)
        dentro.setContentsMargins(6, 6, 6, 6)
        self.tabela = QTableWidget()
        configurar_tabela(self.tabela, COLUNAS_CLIENTES, coluna_elastica=0)
        self.tabela.verticalHeader().setDefaultSectionSize(48)
        self.tabela.setCursor(Qt.CursorShape.PointingHandCursor)
        self.tabela.setToolTip("Clique para abrir a ficha")
        self.tabela.itemSelectionChanged.connect(self._ao_trocar_selecao)
        dentro.addWidget(self.tabela)

        self.lista_vazia = rotulo(
            "Nenhum cliente encontrado. Ajuste a busca ou cadastre um novo.", "fraco"
        )
        self.lista_vazia.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lista_vazia.setContentsMargins(0, 24, 0, 24)
        dentro.addWidget(self.lista_vazia)
        coluna.addWidget(caixa, 1)
        return pagina

    def _importar_planilha(self) -> None:
        """Cadastro em lote. Só recarrega se alguma coisa entrou de fato."""
        dialogo = ImportarClientesDialog(self)
        if dialogo.exec() == QDialog.DialogCode.Accepted and dialogo.importados:
            self.recarregar()
            self.dados_alterados.emit()

    def _passa_no_filtro(self, cliente: Cliente) -> bool:
        filtro = self.filtro_tipo.valor()
        if filtro is FiltroTipo.PJ and cliente.tipo is not TipoCliente.PJ:
            return False
        if filtro is FiltroTipo.PF and cliente.tipo is not TipoCliente.PF:
            return False
        termo = sem_acento(self.busca.text().strip())
        if not termo:
            return True
        textos = [cliente.nome, cliente.apelido or "", cliente.telefone or ""]
        for endereco in cliente.enderecos:
            textos += [endereco.cidade or "", endereco.bairro or "", endereco.etiqueta]
        return any(termo in sem_acento(texto) for texto in textos)

    def _texto_vinculos(self, cliente: Cliente) -> str:
        socios, empresas = self._contagem_vinculos.get(cliente.id, (0, 0))
        partes = []
        if socios:
            partes.append(f"{socios} sócio" + ("s" if socios > 1 else ""))
        if empresas:
            partes.append(f"{empresas} empresa" + ("s" if empresas > 1 else ""))
        return " · ".join(partes) or "—"

    def _desenhar_lista(self) -> None:
        visiveis = [c for c in self._clientes if self._passa_no_filtro(c)]
        self._carregando = True
        try:
            self.tabela.clearSelection()
            self.tabela.setRowCount(len(visiveis))
            negrito = QFont()
            negrito.setBold(True)
            for linha, cliente in enumerate(visiveis):
                preencher_linha(
                    self.tabela,
                    linha,
                    (
                        cliente.nome_exibicao,
                        cliente.tipo.name,
                        cliente.telefone or "—",
                        _onde(cliente),
                        self._texto_vinculos(cliente),
                    ),
                    dado=cliente.id,
                )
                nome = self.tabela.item(linha, 0)
                nome.setFont(negrito)
                nome.setToolTip(self._rotulo(cliente))
                situacao = self._lembrancinhas.get(cliente.id)
                if situacao is not None:
                    nome.setText(f"{cliente.nome_exibicao}  🎁")
                    nome.setToolTip(
                        f"{self._rotulo(cliente)}\nRecebe lembrancinha"
                        f" — {date.today().year}: {situacao.value.lower()}"
                    )
                tipo = self.tabela.item(linha, 1)
                tipo.setForeground(QColor(_cores_do_tipo(cliente.tipo)[0]))
                tipo.setFont(QFont(FONTE_DADOS, 9, QFont.Weight.Bold))
                for coluna in (2, 3, 4):
                    item = self.tabela.item(linha, coluna)
                    if item.text() == "—":
                        item.setForeground(QColor(CORES["tinta_fraca"]))
        finally:
            self._carregando = False
        total = len(self._clientes)
        self.contador.setText(
            f"{len(visiveis)} de {total}" if len(visiveis) != total else f"{total}"
        )
        self.lista_vazia.setVisible(not visiveis)
        self.tabela.setVisible(bool(visiveis))

    # ================================================================ ficha
    def _montar_ficha(self) -> QWidget:
        voltar = botao("‹  Clientes", "fantasma")
        voltar.clicked.connect(self.voltar_para_lista)

        # ---- cabeçalho: quem é
        self.cabecalho_ficha = cartao()
        topo = QHBoxLayout(self.cabecalho_ficha)
        topo.setContentsMargins(22, 18, 22, 18)
        topo.setSpacing(16)
        self.lugar_avatar = QHBoxLayout()
        topo.addLayout(self.lugar_avatar)

        self.titulo_ficha = QLabel()
        self.titulo_ficha.setWordWrap(True)
        self.titulo_ficha.setStyleSheet(
            f'font-family: "{FONTE_TITULO}"; font-size: 21px; font-weight: 700;'
            f" color: {CORES['tinta']};"
        )
        self.subtitulo_ficha = rotulo("", "fraco")
        self.pilulas_ficha = QHBoxLayout()
        self.pilulas_ficha.setSpacing(6)
        textos = QVBoxLayout()
        textos.setSpacing(4)
        textos.addWidget(self.titulo_ficha)
        textos.addWidget(self.subtitulo_ficha)
        textos.addLayout(self.pilulas_ficha)
        topo.addLayout(textos, 1)

        self.btn_excluir = botao("Excluir", "perigo")
        self.btn_excluir.clicked.connect(self._excluir)
        self.btn_editar = botao("Editar cadastro", "primario")
        self.btn_editar.clicked.connect(self._editar)
        topo.addWidget(self.btn_excluir, 0, Qt.AlignmentFlag.AlignTop)
        topo.addWidget(self.btn_editar, 0, Qt.AlignmentFlag.AlignTop)

        # ---- coluna da esquerda: contato, endereços e vínculos
        self.cartao_contato, contato, _ = secao("Contato e observações")
        self.grade_contato = QGridLayout()
        self.grade_contato.setHorizontalSpacing(18)
        self.grade_contato.setVerticalSpacing(8)
        contato.addLayout(self.grade_contato)

        self.cartao_enderecos, enderecos, topo_enderecos = secao("Endereços")
        self.contador_enderecos = rotulo("", "fraco")
        topo_enderecos.addWidget(self.contador_enderecos)
        topo_enderecos.addStretch(1)
        self.btn_endereco_novo = botao("+  Adicionar endereço", "fantasma")
        self.btn_endereco_novo.clicked.connect(self._adicionar_endereco)
        topo_enderecos.addWidget(self.btn_endereco_novo)
        self.lista_enderecos_ficha = QVBoxLayout()
        self.lista_enderecos_ficha.setSpacing(8)
        enderecos.addLayout(self.lista_enderecos_ficha)

        self.cartao_socios, socios, topo_socios = secao("Sócios e responsáveis")
        self.titulo_socios = topo_socios.itemAt(0).widget()
        self.apoio_socios = rotulo("", "fraco")
        self.apoio_socios.setWordWrap(True)
        socios.addWidget(self.apoio_socios)
        topo_socios.addStretch(1)
        self.btn_vincular = botao("+  Vincular sócio", "fantasma")
        self.btn_vincular.clicked.connect(self._vincular)
        topo_socios.addWidget(self.btn_vincular)
        self.lista_vinculos = QVBoxLayout()
        self.lista_vinculos.setSpacing(8)
        socios.addLayout(self.lista_vinculos)

        # Uma PJ também pode ser sócia de outra (holding): aparece só se for.
        self.cartao_faz_parte, faz_parte, _ = secao("Faz parte de")
        self.lista_faz_parte = QVBoxLayout()
        self.lista_faz_parte.setSpacing(8)
        faz_parte.addLayout(self.lista_faz_parte)

        esquerda = QVBoxLayout()
        esquerda.setSpacing(14)
        esquerda.addWidget(self.cartao_contato)
        esquerda.addWidget(self.cartao_enderecos)
        esquerda.addWidget(self.cartao_socios)
        esquerda.addWidget(self.cartao_faz_parte)
        esquerda.addStretch(1)

        direita = QVBoxLayout()
        direita.setSpacing(14)
        direita.addWidget(self._montar_fixos())
        direita.addWidget(self._montar_historico(), 1)

        corpo = QWidget()
        grade = QHBoxLayout(corpo)
        grade.setContentsMargins(0, 0, 8, 0)
        grade.setSpacing(16)
        grade.addLayout(esquerda, 3)
        grade.addLayout(direita, 2)

        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setWidget(corpo)
        rolagem.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        pagina = QWidget()
        coluna = QVBoxLayout(pagina)
        coluna.setContentsMargins(0, 0, 0, 0)
        coluna.setSpacing(12)
        coluna.addWidget(voltar, 0, Qt.AlignmentFlag.AlignLeft)
        coluna.addWidget(self.cabecalho_ficha)
        coluna.addWidget(rolagem, 1)
        return pagina

    def _montar_fixos(self) -> QWidget:
        """Serviços que a agenda abre sozinha para este cliente."""
        painel, coluna, topo = secao(
            "Serviços automáticos",
            "Cliente fixo: a agenda abre o serviço sozinha, pelos próximos dois meses.",
        )
        self.contador_fixos = rotulo("", "fraco")
        topo.addWidget(self.contador_fixos)
        topo.addStretch(1)

        self.tabela_fixos = QTableWidget()
        configurar_tabela(self.tabela_fixos, COLUNAS_FIXOS, coluna_elastica=0)
        self.tabela_fixos.doubleClicked.connect(lambda _i: self._editar_fixo())
        self.tabela_fixos.setMinimumHeight(120)
        self.tabela_fixos.setMaximumHeight(200)
        coluna.addWidget(self.tabela_fixos)
        self.sem_fixos = rotulo(
            "Nenhum serviço fixo. Se o cliente tem coleta toda semana ou todo"
            " mês, cadastre aqui e a agenda abre sozinha.",
            "fraco",
        )
        self.sem_fixos.setWordWrap(True)
        coluna.addWidget(self.sem_fixos)

        self.btn_fixo_novo = botao("Novo serviço fixo", "marinho")
        self.btn_fixo_novo.clicked.connect(self._novo_fixo)
        self.btn_fixo_editar = botao("Editar", "fantasma")
        self.btn_fixo_editar.clicked.connect(self._editar_fixo)
        self.btn_fixo_excluir = botao("Excluir", "perigo")
        self.btn_fixo_excluir.clicked.connect(self._excluir_fixo)
        self.btn_fixo_gerar = botao("Gerar agora", "fantasma")
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

    def _montar_historico(self) -> QWidget:
        painel, layout, _ = secao(
            "Histórico de serviços", "Dois cliques abrem o dia na agenda."
        )
        self.titulo_historico = layout.itemAt(0).layout().itemAt(0).widget()

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
        self.tabela_historico.setMinimumHeight(260)
        # Coluna da data com largura fixa: a linha de cabeçalho do grupo ocupa
        # as três colunas e não deve influenciar a largura de nenhuma delas.
        cabecalho = self.tabela_historico.horizontalHeader()
        cabecalho.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.tabela_historico.setColumnWidth(0, 108)
        layout.addWidget(self.tabela_historico, 1)
        return painel

    # ============================================================= cadastro
    def _montar_cadastro(self) -> QWidget:
        self.btn_descartar = botao("‹  Cancelar", "fantasma")
        self.btn_descartar.clicked.connect(self._descartar)

        self.titulo_cadastro = rotulo("Novo cliente", "titulo")
        self.apoio_cadastro = rotulo("", "fraco")

        self.campo_tipo = Segmentado(TipoCliente)
        self.nome = QLineEdit()
        self.nome.setPlaceholderText("Razão social (PJ) ou nome completo (PF)")
        self.apelido = QLineEdit()
        self.apelido.setPlaceholderText("Nome fantasia, ou como a pessoa gosta de ser chamada")
        self.telefone = QLineEdit()
        self.telefone.setPlaceholderText("(31) 90000-0000")
        self.observacao = QPlainTextEdit()
        self.observacao.setMaximumHeight(80)
        self.observacao.setPlaceholderText("Combinados, recados, horários...")

        self.cartao_dados, dados, _ = secao(
            "Dados do cliente", "Os nomes são gravados em maiúsculas, como na planilha."
        )
        grade = QGridLayout()
        grade.setHorizontalSpacing(14)
        grade.setVerticalSpacing(10)
        grade.addWidget(rotulo("Tipo", "campo"), 0, 0)
        linha_tipo = QHBoxLayout()
        linha_tipo.addWidget(self.campo_tipo)
        linha_tipo.addStretch(1)
        grade.addLayout(linha_tipo, 0, 1, 1, 3)
        grade.addWidget(rotulo("Nome / razão social", "campo"), 1, 0)
        grade.addWidget(self.nome, 1, 1, 1, 3)
        grade.addWidget(rotulo("Apelido / fantasia", "campo"), 2, 0)
        grade.addWidget(self.apelido, 2, 1)
        grade.addWidget(rotulo("Telefone", "campo"), 2, 2)
        grade.addWidget(self.telefone, 2, 3)
        grade.addWidget(rotulo("Observação", "campo"), 3, 0, Qt.AlignmentFlag.AlignTop)
        grade.addWidget(self.observacao, 3, 1, 1, 3)
        grade.setColumnStretch(1, 3)
        grade.setColumnStretch(3, 2)
        dados.addLayout(grade)

        self.cartao_enderecos_form, enderecos, topo = secao("Endereços")
        self.contador_enderecos_form = rotulo("", "fraco")
        topo.addWidget(self.contador_enderecos_form)
        topo.addStretch(1)
        self.btn_endereco_form = botao("+  Adicionar endereço", "fantasma")
        self.btn_endereco_form.clicked.connect(self._adicionar_endereco)
        topo.addWidget(self.btn_endereco_form)
        self.aviso_enderecos = rotulo(
            "Nenhum endereço cadastrado — sem endereço não dá para marcar serviço.",
            "fraco",
        )
        enderecos.addWidget(self.aviso_enderecos)
        self.lista_enderecos = QVBoxLayout()
        self.lista_enderecos.setSpacing(10)
        enderecos.addLayout(self.lista_enderecos)

        conteudo = QWidget()
        coluna = QVBoxLayout(conteudo)
        coluna.setContentsMargins(0, 0, 8, 0)
        coluna.setSpacing(14)
        coluna.addWidget(self.cartao_dados)
        coluna.addWidget(self.cartao_enderecos_form)
        coluna.addStretch(1)
        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setWidget(conteudo)
        rolagem.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.btn_salvar = botao("Salvar cliente", "primario")
        self.btn_salvar.clicked.connect(self._salvar)
        cancelar = botao("Cancelar")
        cancelar.clicked.connect(self._descartar)
        barra = cartao(plano=True)
        rodape = QHBoxLayout(barra)
        rodape.setContentsMargins(14, 10, 14, 10)
        rodape.addWidget(rotulo("As mudanças só valem depois de salvar.", "fraco"))
        rodape.addStretch(1)
        rodape.addWidget(cancelar)
        rodape.addWidget(self.btn_salvar)

        titulos = QVBoxLayout()
        titulos.setSpacing(2)
        titulos.addWidget(self.titulo_cadastro)
        titulos.addWidget(self.apoio_cadastro)

        miolo = QWidget()
        miolo.setMaximumWidth(980)
        interno = QVBoxLayout(miolo)
        interno.setContentsMargins(0, 0, 0, 0)
        interno.setSpacing(12)
        interno.addWidget(self.btn_descartar, 0, Qt.AlignmentFlag.AlignLeft)
        interno.addLayout(titulos)
        interno.addWidget(rolagem, 1)
        interno.addWidget(barra)

        pagina = QWidget()
        centro = QHBoxLayout(pagina)
        centro.setContentsMargins(0, 0, 0, 0)
        centro.addStretch(1)
        centro.addWidget(miolo, 8)
        centro.addStretch(1)
        return pagina

    # ------------------------------------------------- endereços (cadastro)
    def _formularios_endereco(self) -> list[EnderecoForm]:
        return [
            self.lista_enderecos.itemAt(i).widget()
            for i in range(self.lista_enderecos.count())
            if isinstance(self.lista_enderecos.itemAt(i).widget(), EnderecoForm)
        ]

    def _preencher_enderecos(self, cliente: Cliente | None) -> None:
        _limpar(self.lista_enderecos)
        for endereco in (list(cliente.enderecos) if cliente is not None else []):
            self._acrescentar_formulario(endereco)
        self._atualizar_resumo_enderecos()

    def _acrescentar_formulario(self, endereco=None) -> EnderecoForm:
        formulario = EnderecoForm(endereco)
        formulario.remocao_pedida.connect(self._remover_endereco)
        formulario.lembrancinha.toggled.connect(
            lambda marcado, f=formulario: self._um_so_da_lembrancinha(f, marcado)
        )
        self.lista_enderecos.addWidget(formulario)
        return formulario

    def _adicionar_endereco(self) -> None:
        """Da ficha ou do cadastro: abre o cadastro com um endereço em branco."""
        if not self._editando:
            self._editar()
        formulario = self._acrescentar_formulario()
        formulario.rotulo_endereco.setFocus()
        self._atualizar_resumo_enderecos()

    def _um_so_da_lembrancinha(self, escolhido: EnderecoForm, marcado: bool) -> None:
        """Só um endereço é o das lembrancinhas: marcar um desmarca os outros."""
        if not marcado:
            return
        for formulario in self._formularios_endereco():
            if formulario is not escolhido:
                formulario.lembrancinha.setChecked(False)

    def _remover_endereco(self, formulario: EnderecoForm) -> None:
        self.lista_enderecos.removeWidget(formulario)
        formulario.setParent(None)
        formulario.deleteLater()
        self._atualizar_resumo_enderecos()

    def _atualizar_resumo_enderecos(self) -> None:
        quantos = len(self._formularios_endereco())
        self.contador_enderecos_form.setText(f"{quantos}" if quantos else "")
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
        self.contador_fixos.setText(f"{len(regras)}" if regras else "")
        self.tabela_fixos.setVisible(bool(regras))
        self.sem_fixos.setVisible(not regras)
        self.btn_fixo_editar.setVisible(bool(regras))
        self.btn_fixo_excluir.setVisible(bool(regras))

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

    # ============================================================== dados
    def recarregar(self) -> None:
        """Relê a lista; com uma ficha aberta (sem edição), relê a ficha."""
        try:
            with session_scope() as sessao:
                self._clientes = repo_clientes.listar_clientes(sessao)
                vinculos = sessao.execute(
                    VinculoSocio.__table__.select()
                ).all()
                self._lembrancinhas = repo_lembrancinhas.situacao_por_cliente(
                    sessao, date.today().year
                )
        except Exception as erro:
            mostrar_erro(self, erro, "Erro ao listar clientes")
            return

        contagem: dict[int, list[int]] = {}
        for vinculo in vinculos:
            contagem.setdefault(vinculo.empresa_id, [0, 0])[0] += 1
            contagem.setdefault(vinculo.pessoa_id, [0, 0])[1] += 1
        self._contagem_vinculos = {k: (v[0], v[1]) for k, v in contagem.items()}

        pj = sum(1 for c in self._clientes if c.tipo is TipoCliente.PJ)
        self.resumo_lista.setText(
            f"{len(self._clientes)} cadastrados · {pj} empresa(s) ·"
            f" {len(self._clientes) - pj} pessoa(s)"
        )
        self._desenhar_lista()

        if self._cliente_id is not None and not self._editando:
            if any(c.id == self._cliente_id for c in self._clientes):
                if self.pilha.currentIndex() == self.PAGINA_FICHA:
                    self._abrir(self._cliente_id)
            else:
                self._modo_vazio()

    def selecionar_cliente(self, cliente_id: int) -> None:
        """Abre a ficha do cliente, de onde for chamado."""
        self._abrir(cliente_id)

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

    def voltar_para_lista(self) -> None:
        self._carregando = True
        self.tabela.clearSelection()
        self._carregando = False
        self.pilha.setCurrentIndex(self.PAGINA_LISTA)

    def _abrir(self, cliente_id: int) -> None:
        """Mostra a ficha. O formulário também fica pronto, para o Editar."""
        try:
            with session_scope() as sessao:
                cliente = repo_clientes.obter_cliente(sessao, cliente_id)
                if cliente is None:
                    self.recarregar()
                    return
                historico = repo_eventos.historico_cliente(sessao, cliente_id)
                socios = repo_socios.socios_da_empresa(sessao, cliente_id)
                empresas = repo_socios.empresas_da_pessoa(sessao, cliente_id)
        except Exception as erro:
            mostrar_erro(self, erro, "Erro ao abrir cliente")
            return

        self._cliente_id = cliente_id
        self._editando = False
        self._preencher_ficha(cliente, socios, empresas)
        self._preencher_formulario(cliente)
        self._preencher_historico(historico)
        self._preencher_fixos()
        self.pilha.setCurrentIndex(self.PAGINA_FICHA)

    # ------------------------------------------------------------ ficha
    def _preencher_ficha(self, cliente: Cliente, socios: list[VinculoSocio],
                         empresas: list[VinculoSocio]) -> None:
        _limpar(self.lugar_avatar)
        self.lugar_avatar.addWidget(
            Avatar(cliente.nome_exibicao, cliente.tipo, 60), 0, Qt.AlignmentFlag.AlignTop
        )
        self.titulo_ficha.setText(cliente.nome_exibicao)
        self.subtitulo_ficha.setText(
            cliente.nome if cliente.apelido and cliente.apelido != cliente.nome else ""
        )
        self.subtitulo_ficha.setVisible(bool(self.subtitulo_ficha.text()))

        _limpar(self.pilulas_ficha)
        self.pilulas_ficha.addWidget(pilula_tipo(cliente.tipo))
        if cliente.telefone:
            self.pilulas_ficha.addWidget(
                pilula(f"☎  {cliente.telefone}", CORES["tinta_media"], CORES["cinza_claro"])
            )
        quantos = len(cliente.enderecos)
        self.pilulas_ficha.addWidget(
            pilula(
                f"{quantos} endereço(s)" if quantos else "SEM ENDEREÇO",
                CORES["tinta_media"] if quantos else CORES["vermelho"],
                CORES["cinza_claro"] if quantos else CORES["vermelho_claro"],
            )
        )
        situacao = self._lembrancinhas.get(cliente.id)
        if situacao is not None:
            self.pilulas_ficha.addWidget(pilula_lembrancinha(situacao, date.today().year))
        self.pilulas_ficha.addStretch(1)

        # Contato
        _limpar(self.grade_contato)
        linhas = [
            ("Nome / razão social", cliente.nome),
            ("Apelido / fantasia", cliente.apelido or "—"),
            ("Telefone", cliente.telefone or "—"),
            ("Observação", cliente.observacao or "—"),
        ]
        for indice, (campo, valor) in enumerate(linhas):
            self.grade_contato.addWidget(rotulo(campo, "campo"), indice, 0,
                                         Qt.AlignmentFlag.AlignTop)
            texto = QLabel(valor)
            texto.setWordWrap(True)
            texto.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            texto.setStyleSheet(
                f"color: {CORES['tinta'] if valor != '—' else CORES['tinta_fraca']};"
                " font-size: 13px;"
            )
            self.grade_contato.addWidget(texto, indice, 1)
        self.grade_contato.setColumnStretch(1, 1)

        # Endereços, só leitura
        _limpar(self.lista_enderecos_ficha)
        self.contador_enderecos.setText(str(quantos) if quantos else "")
        if not quantos:
            aviso = rotulo(
                "Nenhum endereço cadastrado — sem endereço não dá para marcar"
                " serviço.",
                "fraco",
            )
            aviso.setWordWrap(True)
            self.lista_enderecos_ficha.addWidget(aviso)
        for endereco in cliente.enderecos:
            self.lista_enderecos_ficha.addWidget(self._bloco_endereco(endereco))

        # Vínculos
        e_empresa = cliente.tipo is TipoCliente.PJ
        self.titulo_socios.setText("Sócios e responsáveis" if e_empresa else "Empresas")
        self.btn_vincular.setText("+  Vincular sócio" if e_empresa else "+  Vincular a empresa")
        principais = socios if e_empresa else empresas
        self.apoio_socios.setText(
            (
                "Pessoas ligadas a esta empresa. Útil quando a entrega é para um"
                " sócio — o endereço dele está aqui."
                if e_empresa
                else "Empresas de que esta pessoa faz parte."
            )
            if principais
            else (
                "Nenhum sócio vinculado ainda."
                if e_empresa
                else "Não está ligada a nenhuma empresa."
            )
        )
        _limpar(self.lista_vinculos)
        for vinculo in principais:
            outro = vinculo.pessoa if e_empresa else vinculo.empresa
            self.lista_vinculos.addWidget(self._linha_vinculo(vinculo, outro))

        # PJ que também é sócia de outra empresa
        _limpar(self.lista_faz_parte)
        extras = empresas if e_empresa else []
        for vinculo in extras:
            self.lista_faz_parte.addWidget(self._linha_vinculo(vinculo, vinculo.empresa))
        self.cartao_faz_parte.setVisible(bool(extras))

    def _bloco_endereco(self, endereco) -> QWidget:
        bloco = QFrame()
        bloco.setObjectName("blocoEndereco")
        bloco.setStyleSheet(
            f"QFrame#blocoEndereco {{ background: {CORES['papel_suave']};"
            f" border: 1px solid {CORES['pauta']}; border-radius: 10px; }}"
            "QFrame#blocoEndereco QLabel { background: transparent; }"
        )
        titulo = QLabel(endereco.etiqueta)
        titulo.setStyleSheet(f"color: {CORES['tinta']}; font-weight: 800;")
        tipo = pilula(endereco.tipo.value.upper(), CORES["tinta_media"], CORES["cinza_claro"])
        topo = QHBoxLayout()
        topo.setSpacing(8)
        topo.addWidget(titulo)
        topo.addWidget(tipo)
        if endereco.lembrancinha:
            selo = pilula("🎁  LEMBRANCINHAS", CORES["carimbo"], CORES["carimbo_claro"])
            selo.setToolTip("A lembrancinha de fim de ano vai para este endereço.")
            topo.addWidget(selo)
        topo.addStretch(1)
        resumo = QLabel(endereco.resumo())
        resumo.setWordWrap(True)
        resumo.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        resumo.setStyleSheet(f"color: {CORES['tinta_media']};")
        coluna = QVBoxLayout(bloco)
        coluna.setContentsMargins(12, 10, 12, 10)
        coluna.setSpacing(3)
        coluna.addLayout(topo)
        coluna.addWidget(resumo)
        if endereco.observacao:
            obs = QLabel(f"Obs.: {endereco.observacao}")
            obs.setWordWrap(True)
            obs.setStyleSheet(f"color: {CORES['carimbo']}; font-size: 12px;")
            coluna.addWidget(obs)
        return bloco

    def _linha_vinculo(self, vinculo: VinculoSocio, outro: Cliente) -> LinhaVinculo:
        linha = LinhaVinculo(vinculo, outro)
        linha.abrir.connect(self._abrir)
        linha.mudar_papel.connect(self._mudar_papel)
        linha.remover.connect(self._desvincular)
        return linha

    # ------------------------------------------------------------ vínculos
    def _vincular(self) -> None:
        cliente = self._cliente_carregado()
        if cliente is None:
            return
        dialogo = VinculoDialog(self, cliente, self._clientes)
        if dialogo.exec() != QDialog.DialogCode.Accepted or dialogo.outro_id is None:
            return
        if cliente.tipo is TipoCliente.PJ:
            empresa_id, pessoa_id = cliente.id, dialogo.outro_id
        else:
            empresa_id, pessoa_id = dialogo.outro_id, cliente.id
        try:
            with session_scope() as sessao:
                repo_socios.vincular(sessao, empresa_id, pessoa_id, dialogo.papel)
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para vincular")
            return
        self._apos_vinculo()

    def _mudar_papel(self, vinculo_id: int) -> None:
        cliente = self._cliente_carregado()
        try:
            with session_scope() as sessao:
                vinculo = sessao.get(VinculoSocio, vinculo_id)
        except Exception as erro:
            mostrar_erro(self, erro, "Erro ao abrir o vínculo")
            return
        if cliente is None or vinculo is None:
            return
        dialogo = VinculoDialog(self, cliente, self._clientes, vinculo)
        if dialogo.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            with session_scope() as sessao:
                repo_socios.alterar_papel(sessao, vinculo_id, dialogo.papel)
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para mudar o papel")
            return
        self._apos_vinculo()

    def _desvincular(self, vinculo_id: int) -> None:
        try:
            with session_scope() as sessao:
                vinculo = sessao.get(VinculoSocio, vinculo_id)
                descricao = (
                    f"“{vinculo.pessoa.nome_exibicao}” deixa de aparecer como"
                    f" {vinculo.papel.lower()} de “{vinculo.empresa.nome_exibicao}”."
                    if vinculo else ""
                )
        except Exception as erro:
            mostrar_erro(self, erro, "Erro ao abrir o vínculo")
            return
        if not descricao or not confirmar(
            self, "Desfazer vínculo",
            descricao + "\n\nOs dois cadastros continuam como estão.",
        ):
            return
        try:
            with session_scope() as sessao:
                repo_socios.desvincular(sessao, vinculo_id)
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para desfazer")
            return
        self._apos_vinculo()

    def _apos_vinculo(self) -> None:
        self.recarregar()
        if self._cliente_id is not None:
            self._abrir(self._cliente_id)

    # ----------------------------------------------------------- histórico
    def _preencher_historico(self, historico: list[Evento]) -> None:
        self._historico = historico
        self.titulo_historico.setText(
            f"Histórico de serviços ({len(historico)})" if historico
            else "Histórico de serviços"
        )
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

    # =============================================================== ações
    def _preencher_formulario(self, cliente: Cliente | None) -> None:
        self.campo_tipo.definir_valor(cliente.tipo if cliente else TipoCliente.PF)
        self.nome.setText(cliente.nome if cliente else "")
        self.apelido.setText((cliente.apelido or "") if cliente else "")
        self.telefone.setText((cliente.telefone or "") if cliente else "")
        self.observacao.setPlainText((cliente.observacao or "") if cliente else "")
        self._preencher_enderecos(cliente)

    def _editar(self) -> None:
        """Abre o cadastro do cliente da ficha."""
        if self._cliente_id is None:
            return
        cliente = self._cliente_carregado()
        if cliente is None:
            return
        self._preencher_formulario(cliente)
        self.titulo_cadastro.setText("Editar cadastro")
        self.apoio_cadastro.setText(cliente.nome_exibicao)
        self.btn_descartar.setText("‹  Voltar à ficha sem salvar")
        self._editando = True
        self.pilha.setCurrentIndex(self.PAGINA_CADASTRO)
        self.nome.setFocus()

    def _novo(self) -> None:
        self._cliente_id = None
        self._preencher_formulario(None)
        self.titulo_cadastro.setText("Novo cliente")
        self.apoio_cadastro.setText(
            "Depois de salvar, a ficha abre — e dali dá para vincular sócios."
        )
        self.btn_descartar.setText("‹  Voltar à lista")
        self._editando = True
        self.pilha.setCurrentIndex(self.PAGINA_CADASTRO)
        self.nome.setFocus()

    def _descartar(self) -> None:
        self._editando = False
        if self._cliente_id is None:
            self._modo_vazio()
            self.voltar_para_lista()
        else:
            self._abrir(self._cliente_id)  # relê do banco e volta para a ficha

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
        self._editando = False
        self.recarregar()
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
                vinculos = len(repo_socios.vinculos_do_cliente(sessao, self._cliente_id))
        except Exception as erro:
            mostrar_erro(self, erro, "Erro ao consultar cliente")
            return

        aviso = f"Excluir o cliente “{nome}”?"
        if total:
            aviso += f"\n\nIsto também apaga {total} serviço(s) do histórico."
        if vinculos:
            aviso += f"\n{vinculos} vínculo(s) de sócio são desfeitos."
        if not confirmar(self, "Excluir cliente", aviso):
            return

        try:
            with session_scope() as sessao:
                repo_clientes.excluir_cliente(sessao, self._cliente_id)
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para excluir")
            return

        self._cliente_id = None
        self._modo_vazio()
        self.recarregar()
        self.voltar_para_lista()
        self.dados_alterados.emit()

    # -------------------------------------------------------------- estado
    def _modo_vazio(self) -> None:
        self._cliente_id = None
        self._editando = False
        self._preencher_formulario(None)
        self._preencher_historico([])
        self._preencher_fixos()

    @staticmethod
    def _rotulo(cliente: Cliente) -> str:
        """Texto completo do cliente, usado na dica da lista."""
        if cliente.apelido and cliente.apelido != cliente.nome:
            return f"{cliente.apelido} · {cliente.nome}"
        return cliente.nome
