"""Lembrancinhas de fim de ano: quem recebe e se já foi entregue.

Um cadastro à parte do de clientes da agenda. Cada ano tem a sua lista de
entregas: o mesmo destinatário aparece "a entregar" de novo quando o ano vira,
e o que foi entregue nos anos anteriores continua anotado.
"""

from __future__ import annotations

import enum
from datetime import date
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app import planilha
from app.db import session_scope
from app.models import Cliente, DestinatarioLembrancinha, SituacaoLembrancinha
from app.repository import clientes as repo_clientes
from app.repository import lembrancinhas as repo
from app.schemas import DadosDestinatario
from app.ui import marca as marca_visual
from app.ui.estilo import CORES, FONTE_DADOS, FONTE_TITULO, marcar
from app.ui.mensagens import confirmar, mostrar_erro
from app.ui.widgets import (
    Etiqueta,
    Segmentado,
    cartao,
    configurar_tabela,
    rotulo,
)

def _cor_situacao(situacao: SituacaoLembrancinha) -> tuple[str, str]:
    """Lida na hora: as cores mudam com o tema."""
    return {
        SituacaoLembrancinha.A_ENTREGAR: (CORES["carimbo"], CORES["carimbo_claro"]),
        SituacaoLembrancinha.ENTREGUE: (CORES["verde"], CORES["verde_claro"]),
        SituacaoLembrancinha.NAO_ENVIAR: (CORES["tinta_media"], CORES["cinza_claro"]),
    }[situacao]
GLIFO_SITUACAO = {
    SituacaoLembrancinha.A_ENTREGAR: "●",
    SituacaoLembrancinha.ENTREGUE: "✓",
    SituacaoLembrancinha.NAO_ENVIAR: "–",
}


class Filtro(enum.Enum):
    TODOS = "Todos"
    A_ENTREGAR = "A entregar"
    ENTREGUE = "Entregues"
    NAO_ENVIAR = "Não enviar"


COLUNAS = ("Nome", "A quem entregar", "Presente", "Endereço", "Telefone", "Situação")
COL_SITUACAO = 5


def ano_da_campanha(hoje: date | None = None) -> int:
    """As lembrancinhas de ano novo saem no fim do ano; em janeiro ainda se
    está fechando a campanha do ano que acabou."""
    hoje = hoje or date.today()
    return hoje.year - 1 if hoje.month == 1 else hoje.year


class DestinatarioDialog(QDialog):
    """Ficha de quem recebe a lembrancinha."""

    def __init__(
        self,
        parent: QWidget | None,
        clientes: list[Cliente],
        destinatario: DestinatarioLembrancinha | None = None,
        dados_iniciais: DadosDestinatario | None = None,
    ) -> None:
        super().__init__(parent)
        self._clientes = clientes
        self._id = destinatario.id if destinatario else None
        self._cliente_id: int | None = None
        self.setWindowTitle("Destinatário de lembrancinha")
        self.setMinimumWidth(620)
        self.setStyleSheet(f"QDialog {{ background: {CORES['papel']}; }}")

        self.nome = QLineEdit()
        self.nome.setPlaceholderText("Empresa ou pessoa")
        self.contato = QLineEdit()
        self.contato.setPlaceholderText("Sr. Paulo, recepção...")
        self.telefone = QLineEdit()
        self.presente = QLineEdit()
        self.presente.setPlaceholderText("Cesta, agenda + caneta...")
        self.logradouro = QLineEdit()
        self.numero = QLineEdit()
        self.numero.setMaximumWidth(110)
        self.complemento = QLineEdit()
        self.bairro = QLineEdit()
        self.cidade = QLineEdit()
        self.cep = QLineEdit()
        self.cep.setMaxLength(9)
        self.cep.setMaximumWidth(140)
        self.cep.setPlaceholderText("00000-000")
        self.observacao = QPlainTextEdit()
        self.observacao.setMaximumHeight(64)
        self.ativo = QCheckBox("Recebe lembrancinha (desmarque para tirar da lista sem apagar)")
        self.ativo.setChecked(True)

        self.vinculo = rotulo("", "fraco")
        trocar = QPushButton("Ligar a um cliente...")
        marcar(trocar, variante="fantasma")
        trocar.clicked.connect(self._escolher_cliente)
        self.btn_desligar = QPushButton("Desligar")
        marcar(self.btn_desligar, variante="fantasma")
        self.btn_desligar.clicked.connect(lambda: self._definir_cliente(None))

        grade = QGridLayout()
        grade.setHorizontalSpacing(12)
        grade.setVerticalSpacing(8)
        linha = 0
        for texto, campo, coluna, extensao in (
            ("Nome *", self.nome, 0, 3),
            ("A quem entregar", self.contato, 0, 1),
            ("Telefone", self.telefone, 2, 1),
            ("Presente", self.presente, 0, 3),
            ("Logradouro", self.logradouro, 0, 1),
            ("Número", self.numero, 2, 1),
            ("Complemento", self.complemento, 0, 1),
            ("Bairro", self.bairro, 2, 1),
            ("Cidade", self.cidade, 0, 1),
            ("CEP", self.cep, 2, 1),
            ("Observação", self.observacao, 0, 3),
        ):
            grade.addWidget(rotulo(texto, "campo"), linha, coluna)
            grade.addWidget(campo, linha, coluna + 1, 1, extensao)
            if coluna == 2 or extensao == 3:
                linha += 1
        grade.setColumnStretch(1, 3)
        grade.setColumnStretch(3, 2)

        linha_vinculo = QHBoxLayout()
        linha_vinculo.addWidget(self.vinculo, 1)
        linha_vinculo.addWidget(self.btn_desligar)
        linha_vinculo.addWidget(trocar)

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

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 22, 26, 20)
        layout.setSpacing(10)
        layout.addWidget(rotulo(
            "Editar destinatário" if destinatario else "Novo destinatário", "titulo"
        ))
        layout.addWidget(rotulo(
            "Quem recebe a lembrancinha de fim de ano do escritório.", "fraco"
        ))
        layout.addSpacing(6)
        layout.addLayout(grade)
        layout.addWidget(self.ativo)
        layout.addLayout(linha_vinculo)
        layout.addSpacing(6)
        layout.addLayout(rodape)

        if destinatario is not None:
            self._preencher(DadosDestinatario(
                **{c: getattr(destinatario, c) for c in DadosDestinatario.CAMPOS_DE_TEXTO},
                cliente_id=destinatario.cliente_id,
                ativo=destinatario.ativo,
            ))
        elif dados_iniciais is not None:
            self._preencher(dados_iniciais)
        else:
            self._definir_cliente(None)
        self.nome.setFocus()

    def _campos(self) -> dict:
        return {
            "nome": self.nome, "contato": self.contato, "telefone": self.telefone,
            "logradouro": self.logradouro, "numero": self.numero,
            "complemento": self.complemento, "bairro": self.bairro,
            "cidade": self.cidade, "cep": self.cep, "presente": self.presente,
        }

    def _preencher(self, dados: DadosDestinatario) -> None:
        for nome, campo in self._campos().items():
            campo.setText(getattr(dados, nome) or "")
        self.observacao.setPlainText(dados.observacao or "")
        self.ativo.setChecked(dados.ativo)
        self._definir_cliente(dados.cliente_id)

    def _definir_cliente(self, cliente_id: int | None) -> None:
        self._cliente_id = cliente_id
        cliente = next((c for c in self._clientes if c.id == cliente_id), None)
        if cliente is None:
            self._cliente_id = None
            self.vinculo.setText("Não está ligado a um cliente da agenda.")
        else:
            self.vinculo.setText(f"Ligado ao cliente {cliente.nome_exibicao}.")
        self.btn_desligar.setVisible(self._cliente_id is not None)

    def _escolher_cliente(self) -> None:
        from app.ui.seletor_cliente import SeletorClienteDialog

        seletor = SeletorClienteDialog(self, self._clientes, self._cliente_id)
        if seletor.exec() == QDialog.DialogCode.Accepted and seletor.cliente_id:
            self._definir_cliente(seletor.cliente_id)

    def dados(self) -> DadosDestinatario:
        valores = {nome: campo.text() for nome, campo in self._campos().items()}
        return DadosDestinatario(
            **valores,
            observacao=self.observacao.toPlainText(),
            cliente_id=self._cliente_id,
            ativo=self.ativo.isChecked(),
        )

    def _salvar(self) -> None:
        try:
            with session_scope() as sessao:
                if self._id is None:
                    repo.criar(sessao, self.dados())
                else:
                    repo.atualizar(sessao, self._id, self.dados())
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para salvar")
            return
        self.accept()


class LembrancinhasTab(QWidget):
    """Lista do ano, com o andamento das entregas."""

    dados_alterados = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.ano = ano_da_campanha()
        self._todos: list[DestinatarioLembrancinha] = []
        self._clientes: list[Cliente] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(16)
        layout.addLayout(self._montar_cabecalho())
        layout.addWidget(self._montar_andamento())
        layout.addWidget(self._montar_lista(), 1)

        self.recarregar()

    # ---------------------------------------------------------------- layout
    def _montar_cabecalho(self) -> QHBoxLayout:
        textos = QVBoxLayout()
        textos.setSpacing(2)
        textos.addWidget(rotulo("Lembrancinhas", "titulo"))
        textos.addWidget(rotulo(
            "Quem recebe o presente de fim de ano do escritório, e o que já foi entregue.",
            "fraco",
        ))

        anterior = QPushButton("‹")
        proximo = QPushButton("›")
        for botao, passo in ((anterior, -1), (proximo, 1)):
            botao.setFixedWidth(34)
            marcar(botao, variante="fantasma")
            botao.setStyleSheet("font-size: 18px;")
            botao.clicked.connect(lambda _c=False, p=passo: self._andar(p))
        self.rotulo_ano = QLabel()
        self.rotulo_ano.setStyleSheet(
            f'font-family: "{FONTE_TITULO}"; font-size: 20px; font-weight: 800;'
            f"color: {CORES['tinta']}; padding: 0 4px;"
        )
        caixa_ano = QHBoxLayout()
        caixa_ano.setSpacing(2)
        caixa_ano.addWidget(rotulo("Campanha", "campo"))
        caixa_ano.addSpacing(6)
        caixa_ano.addWidget(anterior)
        caixa_ano.addWidget(self.rotulo_ano)
        caixa_ano.addWidget(proximo)

        cabecalho = QHBoxLayout()
        cabecalho.addLayout(textos, 1)
        cabecalho.addLayout(caixa_ano)
        return cabecalho

    def _montar_andamento(self) -> QFrame:
        quadro = cartao(plano=True)
        self.texto_andamento = QLabel()
        self.texto_andamento.setStyleSheet(
            f'font-family: "{FONTE_TITULO}"; font-size: 16px; font-weight: 700;'
            f"color: {CORES['tinta']};"
        )
        self.barra = QProgressBar()
        self.barra.setFixedHeight(10)
        self.barra.setTextVisible(False)
        self.contadores = {
            situacao: QLabel() for situacao in SituacaoLembrancinha
        }
        linha_contadores = QHBoxLayout()
        linha_contadores.setSpacing(18)
        for situacao, etiqueta in self.contadores.items():
            linha_contadores.addWidget(etiqueta)
        linha_contadores.addStretch(1)

        coluna = QVBoxLayout(quadro)
        coluna.setContentsMargins(20, 16, 20, 16)
        coluna.setSpacing(10)
        coluna.addWidget(self.texto_andamento)
        coluna.addWidget(self.barra)
        coluna.addLayout(linha_contadores)
        return quadro

    def _montar_lista(self) -> QFrame:
        self.busca = QLineEdit()
        self.busca.setPlaceholderText("Buscar por nome, contato, bairro ou cidade")
        self.busca.setClearButtonEnabled(True)
        self.busca.setMinimumWidth(200)
        self.busca.textChanged.connect(lambda _t: self._desenhar())
        self.filtro = Segmentado(Filtro)
        self.filtro.mudou.connect(lambda _v: self._desenhar())

        trazer = QPushButton("Trazer de Clientes")
        trazer.setToolTip("Cadastrar a partir de um cliente da agenda, com o endereço dele")
        trazer.clicked.connect(self._trazer_cliente)
        exportar = QPushButton("Exportar planilha")
        exportar.clicked.connect(self._exportar)
        novo = QPushButton("Novo destinatário")
        marcar(novo, variante="primario")
        novo.clicked.connect(lambda: self._novo())

        barra = QHBoxLayout()
        barra.setSpacing(8)
        barra.addWidget(self.busca, 1)
        barra.addWidget(self.filtro)
        barra.addSpacing(8)
        barra.addWidget(trazer)
        barra.addWidget(exportar)
        barra.addWidget(novo)

        self.tabela = QTableWidget()
        configurar_tabela(self.tabela, COLUNAS, coluna_elastica=3)
        self.tabela.verticalHeader().setDefaultSectionSize(42)
        # A pastilha é um widget na célula: o ajuste ao conteúdo não a enxerga.
        cabecalho = self.tabela.horizontalHeader()
        cabecalho.setSectionResizeMode(COL_SITUACAO, cabecalho.ResizeMode.Fixed)
        self.tabela.setColumnWidth(COL_SITUACAO, 170)
        self.tabela.doubleClicked.connect(lambda _i: self._editar())
        self.tabela.itemSelectionChanged.connect(self._ao_selecionar)

        self.btn_entregue = QPushButton("✓  Marcar entregue")
        marcar(self.btn_entregue, variante="sucesso")
        self.btn_entregue.clicked.connect(
            lambda: self._marcar(SituacaoLembrancinha.ENTREGUE)
        )
        self.btn_nao_enviar = QPushButton("Não enviar este ano")
        self.btn_nao_enviar.clicked.connect(
            lambda: self._marcar(SituacaoLembrancinha.NAO_ENVIAR)
        )
        self.btn_voltar = QPushButton("↺  Voltar para a entregar")
        marcar(self.btn_voltar, variante="fantasma")
        self.btn_voltar.clicked.connect(
            lambda: self._marcar(SituacaoLembrancinha.A_ENTREGAR)
        )
        self.btn_editar = QPushButton("Editar")
        self.btn_editar.clicked.connect(self._editar)
        self.btn_excluir = QPushButton("Excluir")
        marcar(self.btn_excluir, variante="perigo")
        self.btn_excluir.clicked.connect(self._excluir)
        self.contador = rotulo("", "fraco")

        rodape = QHBoxLayout()
        rodape.setSpacing(8)
        rodape.addWidget(self.contador)
        rodape.addStretch(1)
        for botao in (
            self.btn_voltar, self.btn_nao_enviar, self.btn_entregue,
            self.btn_editar, self.btn_excluir,
        ):
            rodape.addWidget(botao)

        quadro = cartao()
        coluna = QVBoxLayout(quadro)
        coluna.setContentsMargins(16, 14, 16, 14)
        coluna.setSpacing(12)
        coluna.addLayout(barra)
        coluna.addWidget(self.tabela, 1)
        coluna.addLayout(rodape)
        return quadro

    # ---------------------------------------------------------------- dados
    def recarregar(self) -> None:
        try:
            with session_scope() as sessao:
                self._todos = repo.listar(sessao)
                self._clientes = repo_clientes.listar_clientes(sessao)
        except Exception as erro:
            mostrar_erro(self, erro, "Erro ao carregar as lembrancinhas")
            return
        self._desenhar()

    def _andar(self, passo: int) -> None:
        self.ano += passo
        self._desenhar()

    def _visiveis(self) -> list[DestinatarioLembrancinha]:
        from app.ui.seletor_cliente import sem_acento

        termo = sem_acento(self.busca.text().strip())
        filtro = self.filtro.valor()
        resultado = []
        for destinatario in self._todos:
            situacao = destinatario.situacao_no_ano(self.ano)
            if filtro is not Filtro.TODOS and (
                not destinatario.ativo or situacao.name != filtro.name
            ):
                continue
            if termo:
                alvo = sem_acento(" ".join(filter(None, (
                    destinatario.nome, destinatario.contato,
                    destinatario.bairro, destinatario.cidade,
                ))))
                if termo not in alvo:
                    continue
            resultado.append(destinatario)
        # Inativos por último: continuam visíveis para poder reativar.
        resultado.sort(key=lambda d: (not d.ativo, d.nome))
        return resultado

    def _desenhar(self) -> None:
        self.rotulo_ano.setText(str(self.ano))
        selecionado = self._selecionado_id()

        resumo = repo.resumo_do_ano(self._todos, self.ano)
        a_considerar = resumo[SituacaoLembrancinha.A_ENTREGAR] + resumo[
            SituacaoLembrancinha.ENTREGUE
        ]
        entregues = resumo[SituacaoLembrancinha.ENTREGUE]
        if a_considerar:
            self.texto_andamento.setText(
                f"{entregues} de {a_considerar} entregues em {self.ano}"
                + ("  ·  tudo entregue!" if entregues == a_considerar else "")
            )
        else:
            self.texto_andamento.setText(
                f"Ninguém na lista de {self.ano} ainda. "
                "Comece por “Novo destinatário” ou “Trazer de Clientes”."
            )
        self.barra.setRange(0, max(1, a_considerar))
        self.barra.setValue(entregues)
        for situacao, etiqueta in self.contadores.items():
            cor, _fundo = _cor_situacao(situacao)
            etiqueta.setText(
                f'<span style="color:{cor}; font-weight:700;">{GLIFO_SITUACAO[situacao]}'
                f'</span>&nbsp; {situacao.value}&nbsp; <span style="font-family:'
                f"'{FONTE_DADOS}'; font-weight:700; color:{CORES['tinta']};\">"
                f"{resumo[situacao]}</span>"
            )

        visiveis = self._visiveis()
        cabecalho = self.tabela.horizontalHeaderItem(COL_SITUACAO)
        if cabecalho is not None:
            cabecalho.setText(f"SITUAÇÃO {self.ano}")
        self.tabela.setRowCount(len(visiveis))
        fraco = QColor(CORES["tinta_fraca"])
        for linha, destinatario in enumerate(visiveis):
            textos = (
                destinatario.nome,
                destinatario.contato or "—",
                destinatario.presente or "—",
                destinatario.endereco_resumo() or "Sem endereço",
                destinatario.telefone or "—",
            )
            for coluna, texto in enumerate(textos):
                item = QTableWidgetItem(texto)
                if coluna == 0:
                    item.setData(Qt.ItemDataRole.UserRole, destinatario.id)
                    fonte = item.font()
                    fonte.setBold(True)
                    item.setFont(fonte)
                if not destinatario.ativo:
                    item.setForeground(fraco)
                self.tabela.setItem(linha, coluna, item)
            self.tabela.setItem(linha, COL_SITUACAO, QTableWidgetItem(""))
            self.tabela.setCellWidget(
                linha, COL_SITUACAO, self._pastilha(destinatario)
            )

        total_ativos = sum(1 for d in self._todos if d.ativo)
        self.contador.setText(
            f"{len(visiveis)} na lista · {total_ativos} recebem lembrancinha"
        )
        if selecionado is not None:
            self._selecionar(selecionado)
        self._ao_selecionar()

    def _pastilha(self, destinatario: DestinatarioLembrancinha) -> QWidget:
        caixa = QWidget()
        linha = QHBoxLayout(caixa)
        linha.setContentsMargins(6, 0, 6, 0)
        etiqueta = Etiqueta()
        if not destinatario.ativo:
            etiqueta.definir("Fora da lista", CORES["tinta_fraca"], CORES["cinza_claro"])
        else:
            situacao = destinatario.situacao_no_ano(self.ano)
            cor, fundo = _cor_situacao(situacao)
            texto = f"{GLIFO_SITUACAO[situacao]}  {situacao.value}"
            entrega = destinatario.entrega_do_ano(self.ano)
            if entrega is not None and entrega.entregue_em is not None:
                texto += f" · {entrega.entregue_em.strftime('%d/%m')}"
            etiqueta.definir(texto, cor, fundo)
        linha.addWidget(etiqueta)
        linha.addStretch(1)
        return caixa

    def _selecionado_id(self) -> int | None:
        linhas = self.tabela.selectionModel().selectedRows()
        if not linhas:
            return None
        item = self.tabela.item(linhas[0].row(), 0)
        return None if item is None else item.data(Qt.ItemDataRole.UserRole)

    def _selecionar(self, destinatario_id: int) -> None:
        for linha in range(self.tabela.rowCount()):
            item = self.tabela.item(linha, 0)
            if item is not None and item.data(Qt.ItemDataRole.UserRole) == destinatario_id:
                self.tabela.selectRow(linha)
                return

    def _ao_selecionar(self) -> None:
        destinatario = self._destinatario()
        tem = destinatario is not None
        situacao = destinatario.situacao_no_ano(self.ano) if tem else None
        ativo = tem and destinatario.ativo
        self.btn_entregue.setEnabled(ativo and situacao is not SituacaoLembrancinha.ENTREGUE)
        self.btn_nao_enviar.setEnabled(
            ativo and situacao is not SituacaoLembrancinha.NAO_ENVIAR
        )
        self.btn_voltar.setEnabled(ativo and situacao is not SituacaoLembrancinha.A_ENTREGAR)
        self.btn_editar.setEnabled(tem)
        self.btn_excluir.setEnabled(tem)

    def _destinatario(self) -> DestinatarioLembrancinha | None:
        alvo = self._selecionado_id()
        return next((d for d in self._todos if d.id == alvo), None)

    # ---------------------------------------------------------------- ações
    def _novo(self, dados: DadosDestinatario | None = None) -> None:
        dialogo = DestinatarioDialog(self, self._clientes, dados_iniciais=dados)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            self._apos_mudanca()
            self.busca.clear()
            nome = dialogo.dados().normalizado().nome
            novo = next((d for d in self._todos if d.nome == nome), None)
            if novo is not None:
                self._selecionar(novo.id)

    def _trazer_cliente(self) -> None:
        from app.ui.seletor_cliente import SeletorClienteDialog

        if not self._clientes:
            QMessageBox.information(self, "Clientes", "Ainda não há clientes cadastrados.")
            return
        seletor = SeletorClienteDialog(self, self._clientes)
        if seletor.exec() != QDialog.DialogCode.Accepted or not seletor.cliente_id:
            return
        cliente = next(c for c in self._clientes if c.id == seletor.cliente_id)
        ja = next((d for d in self._todos if d.cliente_id == cliente.id), None)
        if ja is not None:
            QMessageBox.information(
                self, "Já está na lista",
                f"“{cliente.nome_exibicao}” já está nas lembrancinhas como “{ja.nome}”.",
            )
            self._selecionar(ja.id)
            return
        self._novo(repo.dados_do_cliente(cliente))

    def _editar(self) -> None:
        destinatario = self._destinatario()
        if destinatario is None:
            return
        dialogo = DestinatarioDialog(self, self._clientes, destinatario=destinatario)
        if dialogo.exec() == QDialog.DialogCode.Accepted:
            self._apos_mudanca()

    def _marcar(self, situacao: SituacaoLembrancinha) -> None:
        destinatario = self._destinatario()
        if destinatario is None:
            return
        try:
            with session_scope() as sessao:
                repo.definir_situacao(sessao, destinatario.id, self.ano, situacao)
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para marcar")
            return
        self._apos_mudanca()

    def _excluir(self) -> None:
        destinatario = self._destinatario()
        if destinatario is None:
            return
        if not confirmar(
            self, "Excluir destinatário",
            f"Excluir “{destinatario.nome}” das lembrancinhas, com o histórico de "
            "entregas de todos os anos?\n\nPara só parar de enviar, edite e "
            "desmarque “Recebe lembrancinha”.",
        ):
            return
        try:
            with session_scope() as sessao:
                repo.excluir(sessao, destinatario.id)
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para excluir")
            return
        self._apos_mudanca()

    def _exportar(self) -> None:
        visiveis = self._visiveis()
        if not visiveis:
            QMessageBox.information(self, "Exportar", "Não há ninguém na lista para exportar.")
            return
        sugestao = str(
            Path.home() / f"lembrancinhas-{self.ano}{planilha.EXTENSAO_PADRAO}"
        )
        caminho, _filtro = QFileDialog.getSaveFileName(
            self, "Exportar lembrancinhas", sugestao, planilha.FILTRO_ESCRITA
        )
        if not caminho:
            return
        if not Path(caminho).suffix:
            caminho += planilha.EXTENSAO_PADRAO
        try:
            exportar(caminho, visiveis, self.ano)
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para exportar")
            return
        QMessageBox.information(self, "Exportar", f"Planilha salva em\n{caminho}")

    def _apos_mudanca(self) -> None:
        self.recarregar()
        self.dados_alterados.emit()


CABECALHO_EXPORTACAO = (
    "Nome", "A quem entregar", "Telefone", "Presente", "Logradouro", "Número",
    "Complemento", "Bairro", "Cidade", "CEP", "Situação", "Entregue em",
    "Observação",
)


def linhas_para_exportar(
    destinatarios: list[DestinatarioLembrancinha], ano: int
) -> list[list[str]]:
    linhas = [list(CABECALHO_EXPORTACAO)]
    for d in destinatarios:
        entrega = d.entrega_do_ano(ano)
        situacao = (
            d.situacao_no_ano(ano).value if d.ativo else "Fora da lista"
        )
        linhas.append([
            d.nome, d.contato or "", d.telefone or "", d.presente or "",
            d.logradouro or "", d.numero or "", d.complemento or "",
            d.bairro or "", d.cidade or "", d.cep or "", situacao,
            entrega.entregue_em.strftime("%d/%m/%Y")
            if entrega is not None and entrega.entregue_em else "",
            d.observacao or "",
        ])
    return linhas


def exportar(caminho: str, destinatarios: list[DestinatarioLembrancinha], ano: int) -> None:
    """Grava a lista do ano em .xlsx (com cabeçalho nas cores da marca) ou .csv."""
    linhas = linhas_para_exportar(destinatarios, ano)
    if Path(caminho).suffix.lower() == ".csv" or not planilha.TEM_XLSX:
        planilha.escrever_csv(caminho, linhas)
        return
    import openpyxl
    from openpyxl.styles import Font, PatternFill

    livro = openpyxl.Workbook()
    aba = livro.active
    aba.title = f"Lembrancinhas {ano}"
    for linha in linhas:
        aba.append(linha)
    for celula in aba[1]:
        celula.font = Font(bold=True, color="FFFFFF")
        celula.fill = PatternFill("solid", fgColor=marca_visual.AZUL_MARCA.lstrip("#"))
    for indice, largura in enumerate(
        (36, 22, 16, 20, 34, 9, 18, 20, 18, 11, 14, 12, 30), start=1
    ):
        aba.column_dimensions[openpyxl.utils.get_column_letter(indice)].width = largura
    aba.freeze_panes = "A2"
    livro.save(caminho)
