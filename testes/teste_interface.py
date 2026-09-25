"""Verificações das telas: entrada, clientes, agenda, cadastros e painel."""

from __future__ import annotations

from datetime import timedelta

from comum import preparar_ambiente, semear

preparar_ambiente()

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

app = QApplication([])

from app import sessao as sessao_app  # noqa: E402
from app.db import session_scope  # noqa: E402
from app.models import Periodo, StatusEvento  # noqa: E402
from app.repository import eventos as repo_eventos  # noqa: E402
from app.repository import usuarios as repo_usuarios  # noqa: E402
from app.ui import login as tela_login  # noqa: E402
from app.ui import teclado  # noqa: E402
from app.ui.estilo import aplicar_tema  # noqa: E402
from app.ui.login import LoginDialog, esquecer_neste_computador  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402
from app.ui.reagendar import PendenciasDialog, ReagendarDialog  # noqa: E402
from app.ui.seletor_cliente import SeletorClienteDialog, sem_acento  # noqa: E402
from app.ui.seletor_data import SeletorDeData  # noqa: E402

aplicar_tema(app)
dados = semear()
hoje = dados["hoje"]


def entrada() -> None:
    dialogo = LoginDialog()
    assert not dialogo.primeiro_acesso, "o semeador já criou o usuário"
    dialogo.campo_login.setText("henderson")
    dialogo.campo_senha.setText("errada")
    dialogo._entrar()
    assert dialogo.usuario is None and "não conferem" in dialogo.aviso.text()

    dialogo.campo_senha.setText("1234")
    dialogo.lembrar.setChecked(True)
    dialogo._entrar()
    assert dialogo.usuario is not None
    arquivo = sessao_app.caminho_do_arquivo()
    assert arquivo.exists() and oct(arquivo.stat().st_mode)[-3:] == "600"
    assert tela_login.entrar_pelo_token() is not None, "entra sem digitar senha"
    esquecer_neste_computador()
    assert not arquivo.exists()
    sessao_app.definir_usuario(dialogo.usuario)
    print("ok entrada: senha errada barrada, sessão lembrada e esquecida")

    # aviso de Caps Lock, com a leitura do teclado forçada nos dois estados
    teclado_real = teclado.caps_lock_ligado
    try:
        tela_login.caps_lock_ligado = lambda: True
        dialogo._conferir_caps()
        assert "Caps Lock ligado" in dialogo.aviso_caps.text()
        tela_login.caps_lock_ligado = lambda: False
        dialogo._conferir_caps()
        assert dialogo.aviso_caps.text() == ""
        tela_login.caps_lock_ligado = lambda: None
        dialogo.eventFilter(
            dialogo.campo_senha,
            QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A,
                      Qt.KeyboardModifier.NoModifier, "A"),
        )
        assert "Caps Lock ligado" in dialogo.aviso_caps.text()
    finally:
        tela_login.caps_lock_ligado = teclado_real
    print("ok Caps Lock: pelo teclado e pela digitação")


def clientes(janela: MainWindow) -> None:
    aba = janela.aba_clientes
    janela.abas.setCurrentIndex(MainWindow.ABA_CLIENTES)
    app.processEvents()
    aba.tabela.selectRow(0)
    app.processEvents()
    assert aba._cliente_id is not None and not aba._editando
    formularios = aba._formularios_endereco()
    assert aba.nome.isReadOnly()
    assert all(f.logradouro.isReadOnly() for f in formularios)
    assert aba.btn_editar.isVisibleTo(janela) and not aba.btn_salvar.isVisibleTo(janela)

    aba.tabela.selectRow(1)
    app.processEvents()
    assert not aba._editando, "navegar não abre a edição"

    aba._editar()
    assert aba._editando and not aba.nome.isReadOnly()
    assert all(
        not f.logradouro.isReadOnly() for f in aba._formularios_endereco()
    )

    assert not aba.tabela.isEnabled(), "lista travada durante a edição"
    antes = aba.telefone.text()
    aba.telefone.setText("(31) 4002-8922")
    aba._descartar()
    app.processEvents()
    assert aba.telefone.text() == antes and not aba._editando
    print("ok clientes: ficha só de leitura até o botão, e descartar desfaz")

    historico = aba.tabela_historico
    assert historico.rowCount() >= 0
    aba.campo_agrupamento.definir_valor(
        type(aba.campo_agrupamento.valor())["ANO"]
    )
    aba._desenhar_historico()
    print("ok histórico agrupado por ano")


def agenda(janela: MainWindow) -> None:
    aba = janela.aba_eventos
    janela.abas.setCurrentIndex(MainWindow.ABA_AGENDA)
    app.processEvents()
    assert aba.calendario.mes == hoje.replace(day=1)
    assert aba.calendario._legenda_layout.count() >= 2, "legenda vem dos tipos"

    aba.abrir_dia(hoje)
    app.processEvents()
    linhas = [
        aba.faixas[p].itemAt(i).widget()
        for p in Periodo
        for i in range(aba.faixas[p].count())
    ]
    linhas = [w for w in linhas if w.__class__.__name__ == "LinhaEvento"]
    assert linhas, "o dia semeado tem serviços"

    def botao(linha, prefixo):
        for b in linha.findChildren(QPushButton):
            if b.toolTip().startswith(prefixo):
                return b
        return None

    pendente = next(
        linha for linha in linhas if botao(linha, "Dar baixa") is not None
    )
    evento_id = pendente._evento_id
    botao(pendente, "Dar baixa").click()
    app.processEvents()
    with session_scope() as sessao:
        assert repo_eventos.obter_evento(sessao, evento_id).status is (
            StatusEvento.CONCLUIDO
        )
    print("ok baixa rápida num clique")

    with session_scope() as sessao:
        evento = repo_eventos.obter_evento(sessao, evento_id)
    dialogo = ReagendarDialog(None, evento)
    dialogo.campo_motivo.setCurrentText("Ninguém para receber")
    dialogo.calendario.definir_data(hoje + timedelta(days=3))
    dialogo._salvar()
    assert dialogo.remarcado_para == hoje + timedelta(days=3)
    with session_scope() as sessao:
        original = repo_eventos.obter_evento(sessao, evento_id)
        assert original.status is StatusEvento.NAO_REALIZADO
        assert original.data == hoje, "a original não muda de lugar"
        assert original.remarcacao.data == hoje + timedelta(days=3)
        assert original.remarcacao.origem.id == evento_id
    print("ok remarcação mantém a original e liga as duas pontas")

    aba.recarregar()
    app.processEvents()
    pendencias = PendenciasDialog(None)
    assert pendencias.tabela.rowCount() >= 1
    print("ok pendências:", pendencias.contador.text())


def escolhas() -> None:
    clientes_lista = dados["clientes"]
    seletor = SeletorClienteDialog(None, clientes_lista)
    assert seletor.tabela.rowCount() == len(clientes_lista)
    seletor.busca.setText("joao")
    assert seletor.tabela.rowCount() == 1, "busca ignora acento"
    seletor.busca.setText("zzz")
    assert seletor.tabela.rowCount() == 0 and not seletor.btn_escolher.isEnabled()
    assert sem_acento("ANTÔNIA") == "antonia"
    print("ok busca de cliente sem acento e sem caixa")

    calendario = SeletorDeData()
    calendario.definir_data(hoje)
    assert calendario.intervalo() == (hoje, hoje)
    calendario.definir_por_semana(True)
    inicio, fim = calendario.intervalo()
    assert (inicio.weekday() + 1) % 7 == 0 and (fim - inicio).days == 6
    calendario._andar(-1)
    assert calendario.data() == hoje, "navegar não muda a escolha"
    print("ok seletor de data: dia, semana e navegação")


def cadastros_e_painel(janela: MainWindow) -> None:
    janela.abas.setCurrentIndex(MainWindow.ABA_CADASTROS)
    app.processEvents()
    aba = janela.aba_cadastros
    assert aba.tabela_tipos.rowCount() >= 3
    assert aba.tabela_solicitantes.rowCount() >= 2
    assert aba.tabela_usuarios.rowCount() >= 1
    assert "(você)" in aba.tabela_usuarios.item(0, 0).text()
    print("ok cadastros: tipos, solicitantes e usuários")

    janela.abas.setCurrentIndex(MainWindow.ABA_PAINEL)
    app.processEvents()
    painel = janela.aba_painel
    total = int(painel.indicadores["total"].valor.text())
    assert total == sum(f.valor for f in painel.grafico_tempo._fatias)
    assert total == sum(f.valor for f in painel.grafico_tipo._fatias)
    print("ok painel: barras somam o total do período —", painel.titulo.text())

    janela.abas.setCurrentIndex(MainWindow.ABA_REGISTRO)
    app.processEvents()
    assert janela.aba_registro.tabela.rowCount() > 0
    print("ok registro de atividades:", janela.aba_registro.contador.text())


def marca_visivel(janela: MainWindow) -> None:
    assert not janela.windowIcon().isNull(), "ícone da janela"
    # A barra de abas fica limpa: o logotipo mora na tela de entrada.
    assert janela.abas.cornerWidget(Qt.Corner.TopLeftCorner) is None
    print("ok marca: ícone da janela, barra de abas sem logotipo")


def conexao() -> None:
    """A tela de conexão lê, testa e grava sem estragar o resto do .env."""
    import os

    from app import configuracao
    from app.ui.conexao_dialog import ConexaoDialog

    original = configuracao.ARQUIVO
    temporario = original.parent / "testes" / ".dados" / "env-de-teste"
    temporario.parent.mkdir(parents=True, exist_ok=True)
    temporario.write_text(
        "# comentário que precisa sobreviver\n"
        "ROTAS_SQL_ECHO=0\n"
        "ROTAS_DB_HOST=localhost\n",
        encoding="utf-8",
    )
    configuracao.ARQUIVO = temporario
    guardado = dict(os.environ)
    try:
        dialogo = ConexaoDialog(None)
        assert dialogo.campos["banco"].text(), "abre com o que está valendo"

        dialogo.campos["senha"].setText("senha-errada-de-proposito")
        assert dialogo._testar() is False
        assert "Não conectou" in dialogo.resposta.text()

        for nome, valor in configuracao.ler().items():
            dialogo.campos[nome].setText(valor)
        assert dialogo._testar() is True, dialogo.resposta.text()
        assert "Conectou em PostgreSQL" in dialogo.resposta.text()

        dialogo._salvar()
        assert dialogo.salvou
        gravado = temporario.read_text(encoding="utf-8")
        assert "# comentário que precisa sobreviver" in gravado
        assert "ROTAS_SQL_ECHO=0" in gravado, "o que não é conexão fica"
        assert "ROTAS_DB_NAME=" in gravado and "ROTAS_DB_USER=" in gravado
        assert oct(temporario.stat().st_mode)[-3:] == "600", "senha não fica legível"
    finally:
        configuracao.ARQUIVO = original
        os.environ.clear()
        os.environ.update(guardado)
    print("ok conexão: testa antes de salvar e preserva o resto do arquivo")


entrada()
conexao()
janela = MainWindow()
janela.resize(1320, 880)
janela.show()
app.processEvents()
app.processEvents()

marca_visivel(janela)
clientes(janela)
agenda(janela)
escolhas()
cadastros_e_painel(janela)

with session_scope() as sessao:
    assert repo_usuarios.existe_algum(sessao)
print("TESTE INTERFACE OK")
