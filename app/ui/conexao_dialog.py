"""Tela de configuração da conexão com o banco."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app import configuracao
from app.db import reiniciar
from app.ui import marca as marca_visual
from app.ui.estilo import CORES, FONTE_DADOS, marcar
from app.ui.widgets import rotulo


class ConexaoDialog(QDialog):
    """Onde o sistema procura o banco — some depois que tudo está no lugar."""

    def __init__(
        self,
        parent: QWidget | None = None,
        aviso: str = "",
        orientacao: str = "",
    ) -> None:
        super().__init__(parent)
        self.salvou = False

        self.setWindowTitle("Conexão com o banco")
        self.setMinimumWidth(460)
        self.setStyleSheet(f"QDialog {{ background: {CORES['papel']}; }}")

        atual = configuracao.ler()
        self.campos: dict[str, QLineEdit] = {}
        for nome in ("host", "porta", "banco", "usuario", "senha"):
            campo = QLineEdit(atual.get(nome, ""))
            if nome == "senha":
                campo.setEchoMode(QLineEdit.EchoMode.Password)
            self.campos[nome] = campo
        self.campos["porta"].setMaximumWidth(120)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(8)

        logotipo = QLabel()
        logotipo.setPixmap(marca_visual.pixmap(34))
        layout.addWidget(logotipo)
        layout.addSpacing(6)
        layout.addWidget(marca_visual.faixa(3))
        layout.addSpacing(10)
        layout.addWidget(rotulo("Conexão com o banco", "titulo"))
        layout.addWidget(
            rotulo("Onde o PostgreSQL está e com qual usuário entrar.", "fraco")
        )
        layout.addSpacing(8)

        # Duas tarjas diferentes de propósito: vermelha quando uma tentativa
        # falhou, azul quando é só a explicação de quem chega aqui na primeira
        # vez — não houve erro nenhum, e pintar de vermelho assustaria à toa.
        for texto, tinta, fundo in (
            (aviso, CORES["vermelho"], CORES["vermelho_claro"]),
            (orientacao, CORES["azul"], CORES["azul_claro"]),
        ):
            if not texto:
                continue
            tarja = QLabel(texto)
            tarja.setWordWrap(True)
            tarja.setStyleSheet(
                f"background: {fundo}; color: {tinta};"
                "border-radius: 8px; padding: 8px 10px; font-size: 12px;"
            )
            layout.addWidget(tarja)
            layout.addSpacing(8)

        linha_servidor = QHBoxLayout()
        bloco_host = QVBoxLayout()
        bloco_host.setSpacing(6)
        bloco_host.addWidget(rotulo("Servidor", "campo"))
        bloco_host.addWidget(self.campos["host"])
        bloco_porta = QVBoxLayout()
        bloco_porta.setSpacing(6)
        bloco_porta.addWidget(rotulo("Porta", "campo"))
        bloco_porta.addWidget(self.campos["porta"])
        linha_servidor.addLayout(bloco_host, 3)
        linha_servidor.addLayout(bloco_porta, 1)
        layout.addLayout(linha_servidor)
        layout.addSpacing(6)

        for nome, etiqueta in (
            ("banco", "Banco de dados"),
            ("usuario", "Usuário"),
            ("senha", "Senha"),
        ):
            layout.addWidget(rotulo(etiqueta, "campo"))
            layout.addWidget(self.campos[nome])
            layout.addSpacing(4)

        self.resposta = QLabel()
        self.resposta.setWordWrap(True)
        self.resposta.setStyleSheet(
            f'font-family: "{FONTE_DADOS}"; font-size: 11px;'
            f"color: {CORES['tinta_media']};"
        )
        layout.addSpacing(4)
        layout.addWidget(self.resposta)
        layout.addSpacing(10)

        testar = QPushButton("Testar conexão")
        testar.clicked.connect(self._testar)
        salvar = QPushButton("Salvar")
        marcar(salvar, variante="primario")
        salvar.setDefault(True)
        salvar.clicked.connect(self._salvar)
        fechar = QPushButton("Fechar")
        fechar.clicked.connect(self.reject)

        rodape = QHBoxLayout()
        rodape.addWidget(testar)
        rodape.addStretch(1)
        rodape.addWidget(fechar)
        rodape.addWidget(salvar)
        layout.addLayout(rodape)

        self.campos["host"].setFocus()

    def _dados(self) -> dict[str, str]:
        return {nome: campo.text() for nome, campo in self.campos.items()}

    def _dizer(self, texto: str, cor: str) -> None:
        self.resposta.setText(texto)
        self.resposta.setStyleSheet(
            f'font-family: "{FONTE_DADOS}"; font-size: 11px; color: {cor};'
        )

    def _testar(self) -> bool:
        try:
            versao = configuracao.testar(self._dados())
        except Exception as erro:
            self._dizer(f"Não conectou: {_resumo(erro)}", CORES["vermelho"])
            return False
        self._dizer(f"Conectou em {versao}", CORES["verde"])
        return True

    def _salvar(self) -> None:
        if not self._testar():
            return
        try:
            arquivo = configuracao.salvar(self._dados())
        except Exception as erro:
            self._dizer(f"Não deu para gravar: {_resumo(erro)}", CORES["vermelho"])
            return
        reiniciar()  # a próxima consulta já usa a configuração nova
        self.salvou = True
        self._dizer(f"Guardado em {arquivo}", CORES["verde"])
        self.accept()

    def keyPressEvent(self, evento) -> None:  # noqa: N802
        if evento.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._salvar()
            return
        super().keyPressEvent(evento)


def _resumo(erro: Exception) -> str:
    """A primeira linha útil do erro do banco, sem a pilha toda."""
    texto = str(getattr(erro, "orig", erro)).strip()
    for linha in texto.splitlines():
        if linha.strip():
            return linha.strip()
    return type(erro).__name__
