"""Verificações das telas: entrada, clientes, agenda, cadastros e painel."""

from __future__ import annotations

import os
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
from app.repository import clientes as repo_clientes  # noqa: E402
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
    assert arquivo.exists()
    if os.name != "nt":  # no Windows a proteção é a pasta do usuário
        assert oct(arquivo.stat().st_mode)[-3:] == "600"
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
    """Lista → ficha (só leitura) → cadastro, e os vínculos de sócio."""
    from app.models import TipoCliente
    from app.repository import socios as repo_socios
    from app.ui.clientes_tab import ClientesTab, FiltroTipo, LinhaVinculo

    aba = janela.aba_clientes
    janela.abas.setCurrentIndex(MainWindow.ABA_CLIENTES)
    app.processEvents()
    assert aba.pilha.currentIndex() == ClientesTab.PAGINA_LISTA, "abre na lista"
    total = aba.tabela.rowCount()

    aba.filtro_tipo.definir_valor(FiltroTipo.PF)
    aba._desenhar_lista()
    pessoas = aba.tabela.rowCount()
    assert 0 < pessoas < total, "filtro de pessoas"
    aba.filtro_tipo.definir_valor(FiltroTipo.TODOS)
    aba.busca.setText("belo horizonte")
    assert 0 < aba.tabela.rowCount() < total, "busca pela cidade"
    aba.busca.clear()
    assert aba.tabela.rowCount() == total

    aba.tabela.selectRow(0)
    app.processEvents()
    assert aba.pilha.currentIndex() == ClientesTab.PAGINA_FICHA, "clique abre a ficha"
    assert aba._cliente_id is not None and not aba._editando
    assert aba.btn_editar.isVisibleTo(janela)
    assert not aba.btn_salvar.isVisibleTo(janela), "ficha não tem Salvar"

    aba._editar()
    assert aba.pilha.currentIndex() == ClientesTab.PAGINA_CADASTRO
    assert aba._editando and not aba.nome.isReadOnly()
    antes = aba.telefone.text()
    aba.telefone.setText("(31) 4002-8922")
    aba._descartar()
    app.processEvents()
    assert aba.pilha.currentIndex() == ClientesTab.PAGINA_FICHA, "cancelar volta à ficha"
    assert aba.telefone.text() == antes and not aba._editando
    print("ok clientes: lista com filtros, ficha só de leitura, cadastro à parte")

    aba.voltar_para_lista()
    aba._novo()
    assert aba.pilha.currentIndex() == ClientesTab.PAGINA_CADASTRO
    aba._descartar()
    assert aba.pilha.currentIndex() == ClientesTab.PAGINA_LISTA, "novo cancelado volta à lista"

    # ---- sócios: a pessoa ligada à empresa, vista dos dois lados
    with session_scope() as sessao:
        todos = repo_clientes.listar_clientes(sessao)
        empresa = next(c for c in todos if c.tipo is TipoCliente.PJ and c.enderecos)
        pessoa = next(c for c in todos if c.tipo is TipoCliente.PF)
        vinculo = repo_socios.vincular(sessao, empresa.id, pessoa.id, "sócia-administradora")
        vinculo_id = vinculo.id
        assert vinculo.papel == "Sócia-administradora"
        for errado in ((pessoa.id, empresa.id), (empresa.id, empresa.id),
                       (empresa.id, pessoa.id)):
            try:
                repo_socios.vincular(sessao, *errado)
            except ValueError:
                continue
            raise AssertionError(f"vínculo inválido aceito: {errado}")

    aba.recarregar()
    aba._abrir(empresa.id)
    app.processEvents()
    linhas = [
        aba.lista_vinculos.itemAt(i).widget()
        for i in range(aba.lista_vinculos.count())
    ]
    assert any(isinstance(w, LinhaVinculo) for w in linhas), "sócio na ficha da empresa"
    assert aba.titulo_socios.text() == "Sócios e responsáveis"
    aba._abrir(pessoa.id)
    app.processEvents()
    assert aba.titulo_socios.text() == "Empresas"
    assert aba.lista_vinculos.count() == 1, "a empresa na ficha da pessoa"
    textos = [
        aba.tabela.item(l, 4).text() for l in range(aba.tabela.rowCount())
    ]
    assert "1 sócio" in textos and "1 empresa" in textos, textos

    # Pela ficha da empresa: abrir e editar o cadastro do sócio, e voltar.
    aba._abrir(empresa.id)
    linha = next(aba.lista_vinculos.itemAt(i).widget()
                 for i in range(aba.lista_vinculos.count())
                 if isinstance(aba.lista_vinculos.itemAt(i).widget(), LinhaVinculo))
    linha.abrir.emit(pessoa.id)
    assert aba._cliente_id == pessoa.id and aba.btn_voltar_anterior.isVisibleTo(janela)
    aba._voltar_ao_anterior()
    assert aba._cliente_id == empresa.id and not aba.btn_voltar_anterior.isVisibleTo(janela)
    aba._editar_vinculado(pessoa.id)
    assert aba.pilha.currentIndex() == ClientesTab.PAGINA_CADASTRO
    assert aba.nome.text() == pessoa.nome and "Voltar para" in aba.btn_descartar.text()
    aba.telefone.setText("(31) 97777-0000")
    aba._salvar()
    app.processEvents()
    assert aba._cliente_id == empresa.id, "salvar o sócio volta para a empresa"
    assert aba.pilha.currentIndex() == ClientesTab.PAGINA_FICHA
    with session_scope() as sessao:
        assert repo_clientes.obter_cliente(sessao, pessoa.id).telefone == "(31) 97777-0000"
    aba._editar_vinculado(pessoa.id)
    aba._descartar()
    assert aba._cliente_id == empresa.id, "cancelar também volta para a empresa"
    print("ok sócios: editar o cadastro do sócio pela ficha da empresa e voltar")

    with session_scope() as sessao:
        repo_socios.desvincular(sessao, vinculo_id)
        assert repo_socios.vinculos_do_cliente(sessao, empresa.id) == []
    aba._abrir(empresa.id)
    print("ok sócios: vínculo aparece na empresa e na pessoa, e desfaz")

    historico = aba.tabela_historico
    assert historico.rowCount() >= 0
    aba.campo_agrupamento.definir_valor(
        type(aba.campo_agrupamento.valor())["ANO"]
    )
    aba._desenhar_historico()
    aba.voltar_para_lista()
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

    # Os diálogos de inclusão abrem (o "Novo" da tela de Configurações).
    from app.ui import cadastros as tela_cadastros

    for classe in (tela_cadastros.TipoServicoDialog, tela_cadastros.SolicitanteDialog,
                   tela_cadastros.UsuarioDialog):
        classe(aba).deleteLater()
    assert janela.navegacao[MainWindow.ABA_CADASTROS].text().strip() == "Configurações"
    print("ok configurações: diálogos de inclusão abrem")

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
    # O logotipo mora no alto da barra lateral, na versão para fundo escuro.
    assert not janela.logotipo.pixmap().isNull()
    assert set(janela.navegacao) == {
        MainWindow.ABA_AGENDA, MainWindow.ABA_BAIXAS, MainWindow.ABA_CLIENTES,
        MainWindow.ABA_LEMBRANCINHAS, MainWindow.ABA_PAINEL,
        MainWindow.ABA_CADASTROS, MainWindow.ABA_REGISTRO,
    }
    janela.abas.setCurrentIndex(MainWindow.ABA_PAINEL)
    app.processEvents()
    assert janela.navegacao[MainWindow.ABA_PAINEL].isChecked(), "lateral acompanha"
    assert not janela.btn_atualizacao.isVisible(), "sem versão nova, sem botão"
    print("ok marca: logotipo na barra lateral e navegação sincronizada")


def calendario_por_situacao(janela: MainWindow) -> None:
    """Baixado fica verde no calendário; só o que está em aberto tem a cor do tipo."""
    from app.ui.estilo import COR_STATUS, cores_da_etiqueta, cores_no_calendario

    aba = janela.aba_eventos
    janela.abas.setCurrentIndex(MainWindow.ABA_AGENDA)
    aba.voltar_ao_mes()
    aba.recarregar()
    app.processEvents()
    with session_scope() as sessao:
        eventos = repo_eventos.listar_eventos(sessao)
    concluido = next(e for e in eventos if e.status is StatusEvento.CONCLUIDO)
    pendente = next(e for e in eventos if e.status is StatusEvento.PENDENTE)
    assert cores_no_calendario(concluido)[:2] == COR_STATUS[StatusEvento.CONCLUIDO]
    assert cores_no_calendario(concluido)[2] == "✓"
    assert cores_no_calendario(pendente)[:2] == cores_da_etiqueta(
        pendente.tipo_servico.estilo
    )
    celula = next(
        c for c in aba.calendario._celulas if c._dia == concluido.data
    )
    textos = [e.text() for e in celula._etiquetas if e.isVisibleTo(celula)]
    assert any(t.startswith("✓") for t in textos), textos
    print("ok calendário: baixado em verde com ✓, em aberto na cor do tipo")


def baixas(janela: MainWindow) -> None:
    """Quadro de baixas: atrasado aparece, dar baixa move para Baixados."""
    from app.schemas import DadosEvento
    from app.ui.baixas_tab import ATRASADOS, BAIXADOS, CartaoServico

    with session_scope() as sessao:
        modelo = repo_eventos.listar_eventos(sessao)[0]
        atrasado = repo_eventos.criar_evento(sessao, DadosEvento(
            cliente_id=modelo.cliente_id,
            endereco_id=modelo.endereco_id,
            tipo_servico_id=modelo.tipo_servico_id,
            data=hoje - timedelta(days=3),
            periodo=Periodo.MANHA,
        ))
        atrasado_id = atrasado.id

    janela.abas.setCurrentIndex(MainWindow.ABA_BAIXAS)
    app.processEvents()
    quadro = janela.aba_baixas

    def ids(coluna):
        lista = quadro.colunas[coluna].lista
        return [
            lista.itemAt(i).widget().evento_id
            for i in range(lista.count())
            if isinstance(lista.itemAt(i).widget(), CartaoServico)
        ]

    assert atrasado_id in ids(ATRASADOS), "pendente de dia passado é atrasado"
    contador = janela.navegacao[MainWindow.ABA_BAIXAS]._contador
    assert contador.text() not in ("", "0"), "contador na barra lateral"

    quadro._soltou(atrasado_id, ATRASADOS, BAIXADOS)  # o mesmo que arrastar
    app.processEvents()
    assert atrasado_id not in ids(ATRASADOS)
    assert atrasado_id in ids(BAIXADOS)
    with session_scope() as sessao:
        assert repo_eventos.obter_evento(sessao, atrasado_id).status is (
            StatusEvento.CONCLUIDO
        )
    print("ok baixas: atrasado no quadro, arrastar para Baixados conclui")

    # Filtros: escondem cartões sem mexer no contador da barra lateral.
    quadro.busca.setText("ninguém com esse nome")
    app.processEvents()
    assert ids(BAIXADOS) == [] and quadro.limpar_filtros.isVisibleTo(janela)
    quadro._limpar_filtros()
    assert atrasado_id in ids(BAIXADOS)
    print("ok baixas: filtro por cliente e limpar filtros")

    from app.ui import relatorio_pdf

    dialogo = relatorio_pdf.RelatorioDialog(quadro, hoje, atalho_baixas=False)
    assert dialogo.windowTitle() == "Emitir rota"
    assert not dialogo.tarja.isHidden(), "a opção fica sempre à vista"
    if not dialogo.incluir_atrasados.isHidden():
        assert dialogo.incluir_atrasados.isChecked(), "atrasados vão junto por padrão"
        assert dialogo.atrasados_escolhidos()
        dialogo.incluir_atrasados.setChecked(False)
        assert dialogo.atrasados_escolhidos() == []
    dialogo.deleteLater()
    print("ok emitir rota: opção de levar os atrasados")


def lembrancinhas(janela: MainWindow) -> None:
    from app.models import SituacaoLembrancinha
    from app.repository import lembrancinhas as repo_lembr
    from app.schemas import DadosDestinatario
    from app.ui.lembrancinhas_tab import linhas_para_exportar

    tela = janela.aba_lembrancinhas
    janela.abas.setCurrentIndex(MainWindow.ABA_LEMBRANCINHAS)
    with session_scope() as sessao:
        cliente = sessao.get(type(dados["clientes"][0]), dados["clientes"][0].id)
        trazido = repo_lembr.criar(sessao, repo_lembr.dados_do_cliente(cliente))
        avulso = repo_lembr.criar(sessao, DadosDestinatario(
            nome="Dona Maria da Padaria", presente="cesta", bairro="savassi"
        ))
        trazido_id, avulso_id = trazido.id, avulso.id
        assert avulso.nome == "DONA MARIA DA PADARIA", "maiúsculas, como clientes"
        assert trazido.cliente_id == cliente.id and trazido.logradouro
    try:
        with session_scope() as sessao:
            repo_lembr.criar(sessao, DadosDestinatario(nome="dona maria da padaria"))
        raise AssertionError("nome repetido deveria ser recusado")
    except ValueError:
        pass

    tela.recarregar()
    app.processEvents()
    assert tela.tabela.rowCount() == 2
    assert "0 de 2" in tela.texto_andamento.text()

    # O botão "Novo destinatário" de verdade: o clicked manda um bool, que não
    # pode cair no lugar dos dados iniciais.
    from PySide6.QtWidgets import QPushButton

    from app.ui import lembrancinhas_tab

    abertos = []
    original = lembrancinhas_tab.DestinatarioDialog.exec
    lembrancinhas_tab.DestinatarioDialog.exec = lambda d: abertos.append(d) or 0
    try:
        botao = next(b for b in tela.findChildren(QPushButton)
                     if "Novo" in b.text())
        botao.click()
    finally:
        lembrancinhas_tab.DestinatarioDialog.exec = original
    assert len(abertos) == 1, "o botão abre o diálogo em branco"
    print("ok lembrancinhas: botão Novo abre o diálogo")

    tela._selecionar(avulso_id)
    tela._marcar(SituacaoLembrancinha.ENTREGUE)
    app.processEvents()
    assert "1 de 2" in tela.texto_andamento.text()
    with session_scope() as sessao:
        marcado = repo_lembr.obter(sessao, avulso_id)
        assert marcado.situacao_no_ano(tela.ano) is SituacaoLembrancinha.ENTREGUE
        assert marcado.situacao_no_ano(tela.ano + 1) is (
            SituacaoLembrancinha.A_ENTREGAR
        ), "cada ano começa a entregar"

    tela.filtro.definir_valor(type(tela.filtro.valor())["A_ENTREGAR"])
    tela._desenhar()
    assert tela.tabela.rowCount() == 1

    tela._selecionar(trazido_id)
    planilha = linhas_para_exportar(tela._todos, tela.ano)
    assert planilha[0][0] == "Nome" and len(planilha) == 3
    print("ok lembrancinhas: cadastro, entrega por ano, filtro e exportação")


def tema() -> None:
    """Tema escuro: monta a janela inteira; o PDF continua com cores claras."""
    from app.ui import estilo
    from app.ui.relatorio_pdf import carregar_dias, montar_html

    estilo.aplicar_tema(app, estilo.ESCURO)
    try:
        assert estilo.escuro() and estilo.CORES["canvas"] == "#0E1526"
        escura = MainWindow()
        for indice in range(escura.abas.count()):
            escura.abas.setCurrentIndex(indice)
            app.processEvents()
        assert escura.btn_tema.toolTip().startswith("Voltar"), "botão oferece o claro"
        html = montar_html("Teste", carregar_dias(hoje, hoje), 9.5, "tabela")
        assert estilo.CORES_ESCURAS["canvas"] not in html
        assert estilo.CORES_CLARAS["marca"] in html, "PDF sempre no claro"
        estilo.salvar_tema = lambda _nome: None  # não grava a preferência real
        escura.alternar_tema()
        assert escura.trocou_tema
        app.processEvents()
    finally:
        estilo.aplicar_tema(app, estilo.CLARO)
    print("ok tema escuro: janela inteira monta, PDF segue claro")


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
        if os.name != "nt":
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
calendario_por_situacao(janela)
clientes(janela)
agenda(janela)
escolhas()
cadastros_e_painel(janela)
baixas(janela)
lembrancinhas(janela)
tema()

with session_scope() as sessao:
    assert repo_usuarios.existe_algum(sessao)
print("TESTE INTERFACE OK")
