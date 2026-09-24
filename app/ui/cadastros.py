"""Aba de cadastros: tipos de serviço e solicitantes."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from app import sessao as sessao_app
from app.db import session_scope
from app.models import Solicitante, TipoServico, Usuario
from app.repository import solicitantes as repo_solicitantes
from app.repository import tipos_servico as repo_tipos
from app.repository import usuarios as repo_usuarios
from app.schemas import DadosSolicitante, DadosTipoServico, DadosUsuario
from app.ui.estilo import (
    ESTILO_PADRAO,
    PALETA_ETIQUETA,
    cores_da_etiqueta,
    glifo_da_etiqueta,
    marcar,
    nome_da_etiqueta,
)
from app.ui.mensagens import confirmar, mostrar_erro
from app.ui.widgets import (
    cartao,
    configurar_tabela,
    dado_da_linha,
    preencher_linha,
    rotulo,
)

COLUNAS_TIPOS = ("Tipo de serviço", "Cor", "Situação", "Usos")
COLUNAS_SOLICITANTES = ("Nome", "Setor", "Situação", "Pedidos")
COLUNAS_USUARIOS = ("Nome", "Login", "Situação")


def combo_estilos() -> QComboBox:
    """Combo com as cores da paleta, cada uma já mostrando o seu glifo."""
    combo = QComboBox()
    for chave, (cor, _fundo, _barra, glifo, nome) in PALETA_ETIQUETA.items():
        combo.addItem(f"{glifo}   {nome}", chave)
        combo.setItemData(
            combo.count() - 1, QColor(cor), Qt.ItemDataRole.ForegroundRole
        )
    return combo


class TipoServicoDialog(QDialog):
    """Inclusão e edição de um tipo de serviço."""

    def __init__(self, parent: QWidget | None, tipo: TipoServico | None = None) -> None:
        super().__init__(parent)
        self._tipo_id = tipo.id if tipo else None
        self.tipo_id: int | None = self._tipo_id
        self.setWindowTitle("Tipo de serviço")
        self.setMinimumWidth(420)
        self.setStyleSheet("QDialog { background: #FFFFFF; }")

        self.campo_nome = QLineEdit()
        self.campo_nome.setPlaceholderText("Coleta, Retirada, Entrega de guia...")
        self.campo_estilo = combo_estilos()
        self.campo_ativo = QCheckBox("Disponível para novas marcações")
        self.campo_ativo.setChecked(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(10)
        layout.addWidget(
            rotulo("Novo tipo" if tipo is None else "Editar tipo", "titulo")
        )
        layout.addWidget(
            rotulo("A cor e o símbolo aparecem no calendário e na agenda.", "fraco")
        )
        layout.addSpacing(8)
        layout.addWidget(rotulo("Nome", "campo"))
        layout.addWidget(self.campo_nome)
        layout.addWidget(rotulo("Cor", "campo"))
        layout.addWidget(self.campo_estilo)
        layout.addSpacing(4)
        layout.addWidget(self.campo_ativo)
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

        if tipo is not None:
            self.campo_nome.setText(tipo.nome)
            indice = self.campo_estilo.findData(tipo.estilo)
            self.campo_estilo.setCurrentIndex(max(indice, 0))
            self.campo_ativo.setChecked(tipo.ativo)
        self.campo_nome.setFocus()

    def _salvar(self) -> None:
        dados = DadosTipoServico(
            nome=self.campo_nome.text(),
            estilo=self.campo_estilo.currentData() or ESTILO_PADRAO,
            ativo=self.campo_ativo.isChecked(),
        )
        try:
            with session_scope() as sessao:
                if self._tipo_id is None:
                    tipo = repo_tipos.criar(sessao, dados)
                else:
                    tipo = repo_tipos.atualizar(sessao, self._tipo_id, dados)
                self.tipo_id = tipo.id
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para salvar")
            return
        self.accept()


class SolicitanteDialog(QDialog):
    """Inclusão e edição de quem pede os serviços."""

    def __init__(
        self, parent: QWidget | None, solicitante: Solicitante | None = None
    ) -> None:
        super().__init__(parent)
        self._solicitante_id = solicitante.id if solicitante else None
        self.solicitante_id: int | None = self._solicitante_id
        self.setWindowTitle("Solicitante")
        self.setMinimumWidth(420)
        self.setStyleSheet("QDialog { background: #FFFFFF; }")

        try:
            with session_scope() as sessao:
                conhecidos = repo_solicitantes.setores(sessao)
        except Exception:
            conhecidos = []

        self.campo_nome = QLineEdit()
        self.campo_nome.setPlaceholderText("Nome de quem pede o serviço")
        self.campo_setor = QComboBox()
        self.campo_setor.setEditable(True)
        self.campo_setor.addItem("")
        for setor in conhecidos:
            self.campo_setor.addItem(setor)
        self.campo_setor.setCurrentText("")
        self.campo_setor.lineEdit().setPlaceholderText("Fiscal, Contábil, Recepção...")
        self.campo_ativo = QCheckBox("Disponível para novas marcações")
        self.campo_ativo.setChecked(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(10)
        layout.addWidget(
            rotulo("Novo solicitante" if solicitante is None else "Editar solicitante",
                   "titulo")
        )
        layout.addWidget(
            rotulo("Aparece na lista de quem pediu, ao marcar um serviço.", "fraco")
        )
        layout.addSpacing(8)
        layout.addWidget(rotulo("Nome", "campo"))
        layout.addWidget(self.campo_nome)
        layout.addWidget(rotulo("Setor", "campo"))
        layout.addWidget(self.campo_setor)
        layout.addSpacing(4)
        layout.addWidget(self.campo_ativo)
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

        if solicitante is not None:
            self.campo_nome.setText(solicitante.nome)
            self.campo_setor.setCurrentText(solicitante.setor or "")
            self.campo_ativo.setChecked(solicitante.ativo)
        self.campo_nome.setFocus()

    def _salvar(self) -> None:
        dados = DadosSolicitante(
            nome=self.campo_nome.text(),
            setor=self.campo_setor.currentText(),
            ativo=self.campo_ativo.isChecked(),
        )
        try:
            with session_scope() as sessao:
                if self._solicitante_id is None:
                    pessoa = repo_solicitantes.criar(sessao, dados)
                else:
                    pessoa = repo_solicitantes.atualizar(
                        sessao, self._solicitante_id, dados
                    )
                self.solicitante_id = pessoa.id
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para salvar")
            return
        self.accept()


class UsuarioDialog(QDialog):
    """Inclusão e edição de quem entra no sistema."""

    def __init__(self, parent: QWidget | None, usuario: Usuario | None = None) -> None:
        super().__init__(parent)
        self._usuario_id = usuario.id if usuario else None
        self.usuario_id: int | None = self._usuario_id
        self.setWindowTitle("Usuário")
        self.setMinimumWidth(430)
        self.setStyleSheet("QDialog { background: #FFFFFF; }")

        self.campo_nome = QLineEdit()
        self.campo_nome.setPlaceholderText("Nome completo")
        self.campo_login = QLineEdit()
        self.campo_login.setPlaceholderText("nome.sobrenome")
        self.campo_senha = QLineEdit()
        self.campo_senha.setEchoMode(QLineEdit.EchoMode.Password)
        self.campo_senha.setPlaceholderText(
            "Senha" if usuario is None else "Deixe em branco para manter a atual"
        )
        self.campo_ativo = QCheckBox("Pode entrar no sistema")
        self.campo_ativo.setChecked(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(10)
        layout.addWidget(
            rotulo("Novo usuário" if usuario is None else "Editar usuário", "titulo")
        )
        layout.addWidget(
            rotulo("O login não diferencia maiúsculas e não aceita espaços.", "fraco")
        )
        layout.addSpacing(8)
        layout.addWidget(rotulo("Nome", "campo"))
        layout.addWidget(self.campo_nome)
        layout.addWidget(rotulo("Login", "campo"))
        layout.addWidget(self.campo_login)
        layout.addWidget(rotulo("Senha", "campo"))
        layout.addWidget(self.campo_senha)
        layout.addWidget(
            rotulo("Trocar a senha encerra os “continuar conectado” do usuário.",
                   "fraco")
        )
        layout.addSpacing(4)
        layout.addWidget(self.campo_ativo)
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

        if usuario is not None:
            self.campo_nome.setText(usuario.nome)
            self.campo_login.setText(usuario.login)
            self.campo_ativo.setChecked(usuario.ativo)
        self.campo_nome.setFocus()

    def _salvar(self) -> None:
        dados = DadosUsuario(
            nome=self.campo_nome.text(),
            login=self.campo_login.text(),
            senha=self.campo_senha.text() or None,
            ativo=self.campo_ativo.isChecked(),
        )
        try:
            with session_scope() as sessao:
                if self._usuario_id is None:
                    usuario = repo_usuarios.criar(sessao, dados)
                else:
                    usuario = repo_usuarios.atualizar(sessao, self._usuario_id, dados)
                self.usuario_id = usuario.id
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para salvar")
            return
        self.accept()


class CadastrosTab(QWidget):
    """Duas listas lado a lado: tipos de serviço e solicitantes."""

    dados_alterados = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 10, 18, 18)
        layout.setSpacing(16)
        layout.addWidget(self._montar_tipos(), 1)
        layout.addWidget(self._montar_solicitantes(), 1)
        layout.addWidget(self._montar_usuarios(), 1)

        self.recarregar()

    def _montar_tipos(self) -> QWidget:
        painel = cartao()
        coluna = QVBoxLayout(painel)
        coluna.setContentsMargins(16, 14, 16, 16)
        coluna.setSpacing(10)

        topo = QHBoxLayout()
        topo.addWidget(rotulo("Tipos de serviço", "secao"))
        topo.addStretch(1)
        self.contador_tipos = rotulo("", "fraco")
        topo.addWidget(self.contador_tipos)
        coluna.addLayout(topo)
        coluna.addWidget(
            rotulo("O que o motoboy pode fazer numa visita.", "fraco")
        )

        self.tabela_tipos = QTableWidget()
        configurar_tabela(self.tabela_tipos, COLUNAS_TIPOS, coluna_elastica=0)
        self.tabela_tipos.doubleClicked.connect(lambda _i: self._editar_tipo())
        coluna.addWidget(self.tabela_tipos)

        novo = QPushButton("Novo tipo")
        marcar(novo, variante="primario")
        novo.clicked.connect(self._novo_tipo)
        editar = QPushButton("Editar")
        editar.clicked.connect(self._editar_tipo)
        excluir = QPushButton("Excluir")
        marcar(excluir, variante="perigo")
        excluir.clicked.connect(self._excluir_tipo)

        acoes = QHBoxLayout()
        acoes.addWidget(novo)
        acoes.addStretch(1)
        acoes.addWidget(editar)
        acoes.addWidget(excluir)
        coluna.addLayout(acoes)
        return painel

    def _montar_solicitantes(self) -> QWidget:
        painel = cartao()
        coluna = QVBoxLayout(painel)
        coluna.setContentsMargins(16, 14, 16, 16)
        coluna.setSpacing(10)

        topo = QHBoxLayout()
        topo.addWidget(rotulo("Solicitantes", "secao"))
        topo.addStretch(1)
        self.contador_solicitantes = rotulo("", "fraco")
        topo.addWidget(self.contador_solicitantes)
        coluna.addLayout(topo)
        coluna.addWidget(
            rotulo("Quem pede o serviço, e de qual setor.", "fraco")
        )

        self.tabela_solicitantes = QTableWidget()
        configurar_tabela(
            self.tabela_solicitantes, COLUNAS_SOLICITANTES, coluna_elastica=0
        )
        self.tabela_solicitantes.doubleClicked.connect(
            lambda _i: self._editar_solicitante()
        )
        coluna.addWidget(self.tabela_solicitantes)

        novo = QPushButton("Novo solicitante")
        marcar(novo, variante="primario")
        novo.clicked.connect(self._novo_solicitante)
        editar = QPushButton("Editar")
        editar.clicked.connect(self._editar_solicitante)
        excluir = QPushButton("Excluir")
        marcar(excluir, variante="perigo")
        excluir.clicked.connect(self._excluir_solicitante)

        acoes = QHBoxLayout()
        acoes.addWidget(novo)
        acoes.addStretch(1)
        acoes.addWidget(editar)
        acoes.addWidget(excluir)
        coluna.addLayout(acoes)
        return painel

    def _montar_usuarios(self) -> QWidget:
        painel = cartao()
        coluna = QVBoxLayout(painel)
        coluna.setContentsMargins(16, 14, 16, 16)
        coluna.setSpacing(10)

        topo = QHBoxLayout()
        topo.addWidget(rotulo("Usuários", "secao"))
        topo.addStretch(1)
        self.contador_usuarios = rotulo("", "fraco")
        topo.addWidget(self.contador_usuarios)
        coluna.addLayout(topo)
        coluna.addWidget(rotulo("Quem pode entrar no sistema.", "fraco"))

        self.tabela_usuarios = QTableWidget()
        configurar_tabela(self.tabela_usuarios, COLUNAS_USUARIOS, coluna_elastica=0)
        self.tabela_usuarios.doubleClicked.connect(lambda _i: self._editar_usuario())
        coluna.addWidget(self.tabela_usuarios)

        novo = QPushButton("Novo usuário")
        marcar(novo, variante="primario")
        novo.clicked.connect(self._novo_usuario)
        editar = QPushButton("Editar")
        editar.clicked.connect(self._editar_usuario)
        excluir = QPushButton("Excluir")
        marcar(excluir, variante="perigo")
        excluir.clicked.connect(self._excluir_usuario)

        acoes = QHBoxLayout()
        acoes.addWidget(novo)
        acoes.addStretch(1)
        acoes.addWidget(editar)
        acoes.addWidget(excluir)
        coluna.addLayout(acoes)
        return painel

    # ----------------------------------------------------------------- dados
    def recarregar(self) -> None:
        try:
            with session_scope() as sessao:
                tipos = [
                    (t, repo_tipos.contar_uso(sessao, t.id))
                    for t in repo_tipos.listar(sessao)
                ]
                pessoas = [
                    (p, repo_solicitantes.contar_uso(sessao, p.id))
                    for p in repo_solicitantes.listar(sessao)
                ]
                contas = repo_usuarios.listar(sessao)
        except Exception as erro:
            mostrar_erro(self, erro, "Erro ao carregar os cadastros")
            return

        self.tabela_tipos.setRowCount(len(tipos))
        for linha, (tipo, usos) in enumerate(tipos):
            cor, _ = cores_da_etiqueta(tipo.estilo)
            glifo = glifo_da_etiqueta(tipo.estilo)
            nome_cor = nome_da_etiqueta(tipo.estilo)
            preencher_linha(
                self.tabela_tipos,
                linha,
                (tipo.nome, f"{glifo}  {nome_cor}", "Ativo" if tipo.ativo else "Inativo",
                 str(usos)),
                dado=tipo.id,
            )
            item_cor = self.tabela_tipos.item(linha, 1)
            if item_cor is not None:
                item_cor.setForeground(QColor(cor))
            if not tipo.ativo:
                self._esmaecer(self.tabela_tipos, linha)
        self.contador_tipos.setText(f"{len(tipos)}")

        self.tabela_solicitantes.setRowCount(len(pessoas))
        for linha, (pessoa, usos) in enumerate(pessoas):
            preencher_linha(
                self.tabela_solicitantes,
                linha,
                (pessoa.nome, pessoa.setor or "—",
                 "Ativo" if pessoa.ativo else "Inativo", str(usos)),
                dado=pessoa.id,
            )
            if not pessoa.ativo:
                self._esmaecer(self.tabela_solicitantes, linha)
        self.contador_solicitantes.setText(f"{len(pessoas)}")

        logado = sessao_app.id_atual()
        self.tabela_usuarios.setRowCount(len(contas))
        for linha, conta in enumerate(contas):
            nome = conta.nome + ("  (você)" if conta.id == logado else "")
            preencher_linha(
                self.tabela_usuarios,
                linha,
                (nome, conta.login, "Ativo" if conta.ativo else "Inativo"),
                dado=conta.id,
            )
            if not conta.ativo:
                self._esmaecer(self.tabela_usuarios, linha)
        self.contador_usuarios.setText(f"{len(contas)}")

    @staticmethod
    def _esmaecer(tabela: QTableWidget, linha: int) -> None:
        for coluna in range(tabela.columnCount()):
            item = tabela.item(linha, coluna)
            if item is not None:
                item.setForeground(QColor("#98A0AE"))

    @staticmethod
    def _selecionado(tabela: QTableWidget) -> int | None:
        linhas = tabela.selectionModel().selectedRows()
        if not linhas:
            return None
        valor = dado_da_linha(tabela, linhas[0].row())
        return None if valor is None else int(valor)

    # ----------------------------------------------------------------- ações
    def _novo_tipo(self) -> None:
        if TipoServicoDialog(self).exec() == QDialog.DialogCode.Accepted:
            self._apos_mudanca()

    def _editar_tipo(self) -> None:
        tipo_id = self._selecionado(self.tabela_tipos)
        if tipo_id is None:
            return
        with session_scope() as sessao:
            tipo = repo_tipos.obter(sessao, tipo_id)
        if tipo is None:
            self.recarregar()
            return
        if TipoServicoDialog(self, tipo).exec() == QDialog.DialogCode.Accepted:
            self._apos_mudanca()

    def _excluir_tipo(self) -> None:
        tipo_id = self._selecionado(self.tabela_tipos)
        if tipo_id is None:
            return
        with session_scope() as sessao:
            tipo = repo_tipos.obter(sessao, tipo_id)
            nome = tipo.nome if tipo else ""
        if not confirmar(self, "Excluir tipo", f"Excluir o tipo “{nome}”?"):
            return
        try:
            with session_scope() as sessao:
                repo_tipos.excluir(sessao, tipo_id)
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para excluir")
            return
        self._apos_mudanca()

    def _novo_solicitante(self) -> None:
        if SolicitanteDialog(self).exec() == QDialog.DialogCode.Accepted:
            self._apos_mudanca()

    def _editar_solicitante(self) -> None:
        pessoa_id = self._selecionado(self.tabela_solicitantes)
        if pessoa_id is None:
            return
        with session_scope() as sessao:
            pessoa = repo_solicitantes.obter(sessao, pessoa_id)
        if pessoa is None:
            self.recarregar()
            return
        if SolicitanteDialog(self, pessoa).exec() == QDialog.DialogCode.Accepted:
            self._apos_mudanca()

    def _excluir_solicitante(self) -> None:
        pessoa_id = self._selecionado(self.tabela_solicitantes)
        if pessoa_id is None:
            return
        with session_scope() as sessao:
            pessoa = repo_solicitantes.obter(sessao, pessoa_id)
            nome = pessoa.nome_exibicao if pessoa else ""
            usos = repo_solicitantes.contar_uso(sessao, pessoa_id)
        aviso = f"Excluir “{nome}”?"
        if usos:
            aviso += (
                f"\n\n{usos} serviço(s) ficam sem solicitante — o histórico"
                " continua, só perde o nome de quem pediu."
            )
        if not confirmar(self, "Excluir solicitante", aviso):
            return
        try:
            with session_scope() as sessao:
                repo_solicitantes.excluir(sessao, pessoa_id)
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para excluir")
            return
        self._apos_mudanca()

    def _novo_usuario(self) -> None:
        if UsuarioDialog(self).exec() == QDialog.DialogCode.Accepted:
            self._apos_mudanca()

    def _editar_usuario(self) -> None:
        usuario_id = self._selecionado(self.tabela_usuarios)
        if usuario_id is None:
            return
        with session_scope() as sessao:
            usuario = repo_usuarios.obter(sessao, usuario_id)
        if usuario is None:
            self.recarregar()
            return
        if UsuarioDialog(self, usuario).exec() == QDialog.DialogCode.Accepted:
            self._apos_mudanca()

    def _excluir_usuario(self) -> None:
        usuario_id = self._selecionado(self.tabela_usuarios)
        if usuario_id is None:
            return
        with session_scope() as sessao:
            usuario = repo_usuarios.obter(sessao, usuario_id)
            nome = usuario.nome if usuario else ""
        if not confirmar(
            self,
            "Excluir usuário",
            f"Excluir o usuário “{nome}”?\n\n"
            "O que ele fez continua no registro de atividades.",
        ):
            return
        try:
            with session_scope() as sessao:
                repo_usuarios.excluir(sessao, usuario_id, sessao_app.id_atual())
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para excluir")
            return
        self._apos_mudanca()

    def _apos_mudanca(self) -> None:
        self.recarregar()
        self.dados_alterados.emit()
