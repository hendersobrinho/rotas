"""Importação de clientes por planilha: baixar o modelo, conferir e gravar.

A conferência acontece antes de gravar qualquer coisa: a tela lista linha por
linha o que vai entrar, o que vai ficar de fora e por quê. Só depois disso o
botão de importar faz alguma coisa — planilha vinda de fora quase sempre tem
uma linha torta, e descobrir isso no meio da gravação seria pior.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from app import importacao_clientes as importacao
from app import planilha
from app.db import session_scope
from app.ui.estilo import CORES, marcar
from app.ui.mensagens import confirmar, mostrar_erro
from app.ui.widgets import configurar_tabela, preencher_linha, rotulo

COLUNAS = ("Linha", "Cliente", "Tipo", "Endereços", "O que vai acontecer")
NOME_MODELO = "modelo-clientes"


class ImportarClientesDialog(QDialog):
    """Escolhe a planilha, mostra a prévia e grava o que estiver bom."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._linhas: list[importacao.LinhaImportacao] = []
        self._caminho: Path | None = None
        self.importados = 0

        self.setWindowTitle("Importar clientes")
        self.setMinimumSize(880, 560)
        self.setStyleSheet(f"QDialog {{ background: {CORES['papel']}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(10)
        layout.addWidget(rotulo("Importar clientes de uma planilha", "titulo"))
        explicacao = rotulo(
            "Uma linha por cliente. Cada endereço ocupa o seu bloco de"
            " colunas — “Endereço 1 - ...”, “Endereço 2 - ...” —, então dá"
            " para trazer quantos endereços o cliente tiver.",
            "fraco",
        )
        explicacao.setWordWrap(True)
        layout.addWidget(explicacao)
        layout.addSpacing(6)
        layout.addLayout(self._montar_acoes())

        self.arquivo = rotulo("Nenhuma planilha escolhida.", "fraco")
        layout.addWidget(self.arquivo)

        self.campo_atualizar = QCheckBox(
            "Atualizar os clientes que já estão cadastrados com o mesmo nome"
        )
        self.campo_atualizar.setToolTip(
            "Desmarcado, quem já existe fica como está e a linha é ignorada.\n"
            "Marcado, a ficha é substituída pelo que vier na planilha —"
            " inclusive os endereços."
        )
        self.campo_atualizar.toggled.connect(lambda _v: self._mostrar_previa())
        layout.addWidget(self.campo_atualizar)

        self.tabela = QTableWidget()
        configurar_tabela(self.tabela, COLUNAS, coluna_elastica=1)
        layout.addWidget(self.tabela, 1)

        self.resumo = rotulo("", "fraco")
        layout.addWidget(self.resumo)
        layout.addLayout(self._montar_rodape())
        self._mostrar_previa()

    def _montar_acoes(self) -> QHBoxLayout:
        self.btn_modelo = QPushButton("Baixar modelo da planilha")
        self.btn_modelo.setToolTip(
            "Gera uma planilha em branco, com todas as colunas do cadastro e"
            " uma aba explicando como preencher."
        )
        self.btn_modelo.clicked.connect(self._baixar_modelo)

        self.btn_escolher = QPushButton("Escolher planilha preenchida")
        marcar(self.btn_escolher, variante="primario")
        self.btn_escolher.clicked.connect(self._escolher)

        linha = QHBoxLayout()
        linha.setSpacing(8)
        linha.addWidget(self.btn_modelo)
        linha.addWidget(self.btn_escolher)
        linha.addStretch(1)
        return linha

    def _montar_rodape(self) -> QHBoxLayout:
        self.btn_importar = QPushButton("Importar")
        marcar(self.btn_importar, variante="primario")
        self.btn_importar.setDefault(True)
        self.btn_importar.clicked.connect(self._importar)
        fechar = QPushButton("Fechar")
        fechar.clicked.connect(self.reject)

        rodape = QHBoxLayout()
        rodape.addStretch(1)
        rodape.addWidget(fechar)
        rodape.addWidget(self.btn_importar)
        return rodape

    # ---------------------------------------------------------------- modelo
    def _baixar_modelo(self) -> None:
        sugestao = str(Path.home() / f"{NOME_MODELO}{planilha.EXTENSAO_PADRAO}")
        caminho, _filtro = QFileDialog.getSaveFileName(
            self, "Salvar modelo da planilha", sugestao, planilha.FILTRO_ESCRITA
        )
        if not caminho:
            return
        if Path(caminho).suffix.lower() not in (".xlsx", ".csv"):
            caminho += planilha.EXTENSAO_PADRAO
        try:
            destino = importacao.gerar_modelo(caminho)
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para gerar o modelo")
            return
        QMessageBox.information(
            self,
            "Modelo salvo",
            f"O modelo foi salvo em:\n{destino}\n\n"
            "Preencha uma linha por cliente e volte aqui para importar.",
        )

    # -------------------------------------------------------------- planilha
    def _escolher(self) -> None:
        caminho, _filtro = QFileDialog.getOpenFileName(
            self, "Escolher planilha", str(Path.home()), planilha.FILTRO_LEITURA
        )
        if not caminho:
            return
        try:
            with session_scope() as sessao:
                self._linhas = importacao.analisar(sessao, caminho)
        except Exception as erro:
            self._linhas = []
            self._caminho = None
            self._mostrar_previa()
            mostrar_erro(self, erro, "Não deu para ler a planilha")
            return
        self._caminho = Path(caminho)
        self._mostrar_previa()

    def _mostrar_previa(self) -> None:
        atualizar = self.campo_atualizar.isChecked()
        self.arquivo.setText(
            f"Planilha: {self._caminho}" if self._caminho
            else "Nenhuma planilha escolhida."
        )

        self.tabela.setRowCount(len(self._linhas))
        for indice, linha in enumerate(self._linhas):
            preencher_linha(
                self.tabela,
                indice,
                (
                    str(linha.numero),
                    linha.nome,
                    linha.rotulo_tipo,
                    str(linha.quantos_enderecos),
                    linha.situacao(atualizar),
                ),
                dado=linha.numero,
            )
            self._pintar(indice, linha, atualizar)

        self.resumo.setText(self._texto_resumo(atualizar))
        self.btn_importar.setEnabled(
            any(linha.sera_gravada(atualizar) for linha in self._linhas)
        )

    def _pintar(
        self, indice: int, linha: importacao.LinhaImportacao, atualizar: bool
    ) -> None:
        """Vermelho no que tem problema, cinza no que fica de fora."""
        if linha.problema:
            cor = QColor(CORES["vermelho"])
        elif not linha.sera_gravada(atualizar):
            cor = QColor(CORES["tinta_fraca"])
        else:
            return
        for coluna in range(self.tabela.columnCount()):
            celula = self.tabela.item(indice, coluna)
            if celula is not None:
                celula.setForeground(cor)

    def _contas(self, atualizar: bool) -> tuple[int, int, int, int]:
        novos = sum(
            1 for l in self._linhas if l.valida and l.existente_id is None
        )
        existentes = sum(
            1 for l in self._linhas if l.valida and l.existente_id is not None
        )
        problemas = sum(1 for l in self._linhas if l.problema)
        gravadas = sum(1 for l in self._linhas if l.sera_gravada(atualizar))
        return novos, existentes, problemas, gravadas

    def _texto_resumo(self, atualizar: bool) -> str:
        if not self._linhas:
            return (
                "Baixe o modelo, preencha e escolha o arquivo para ver aqui o"
                " que será importado."
            )
        novos, existentes, problemas, _gravadas = self._contas(atualizar)
        partes = [f"{len(self._linhas)} linha(s) lida(s)", f"{novos} novo(s)"]
        if existentes:
            partes.append(
                f"{existentes} já cadastrado(s)"
                + ("" if atualizar else " — ficam de fora")
            )
        if problemas:
            partes.append(f"{problemas} com problema")
        return " · ".join(partes)

    # -------------------------------------------------------------- gravação
    def _importar(self) -> None:
        atualizar = self.campo_atualizar.isChecked()
        novos, existentes, problemas, gravadas = self._contas(atualizar)
        if not gravadas:
            return

        pendencias = []
        if problemas:
            pendencias.append(f"{problemas} linha(s) com problema")
        if existentes and not atualizar:
            pendencias.append(f"{existentes} já cadastrado(s)")
        pergunta = f"Gravar {gravadas} cliente(s) no sistema?"
        if pendencias:
            pergunta += "\n\nFicam de fora: " + ", ".join(pendencias) + "."
        if atualizar and existentes:
            pergunta += (
                f"\n\nOs {existentes} cliente(s) que já existem serão"
                " substituídos pelo que está na planilha, endereços inclusive."
            )
        if not confirmar(self, "Importar clientes", pergunta):
            return

        try:
            with session_scope() as sessao:
                resultado = importacao.importar(sessao, self._linhas, atualizar)
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para importar")
            return

        self.importados = resultado.criados + resultado.atualizados
        QMessageBox.information(self, "Importação concluída", resultado.resumo() + ".")
        self.accept()
