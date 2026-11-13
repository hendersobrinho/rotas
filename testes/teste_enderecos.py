"""Vários endereços por cliente: inclusão, remoção e rótulos."""

from __future__ import annotations

from comum import preparar_ambiente, semear

preparar_ambiente()

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication([])

from app.db import session_scope  # noqa: E402
from app.models import TipoCliente, TipoEndereco  # noqa: E402
from app.repository import clientes as repo_clientes  # noqa: E402
from app.schemas import DadosCliente, DadosEndereco  # noqa: E402
from app.ui.estilo import aplicar_tema  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402
from app.ui.widgets import dado_da_linha  # noqa: E402

aplicar_tema(app)
dados = semear()

# ---- pelo repositório ----------------------------------------------------
with session_scope() as sessao:
    cliente = repo_clientes.criar_cliente(sessao, DadosCliente(
        tipo=TipoCliente.PJ, nome="Rede Três Lojas LTDA", apelido="Rede Três",
        enderecos=[
            DadosEndereco(TipoEndereco.COMERCIAL, rotulo="Loja 1",
                          logradouro="Rua A", numero="1", cidade="BH"),
            DadosEndereco(TipoEndereco.COMERCIAL, rotulo="Loja 2",
                          logradouro="Rua B", numero="2", cidade="BH"),
            DadosEndereco(TipoEndereco.COMERCIAL, rotulo="Depósito",
                          logradouro="Rua C", numero="3", cidade="Contagem"),
        ]))
    cliente_id = cliente.id
    assert len(cliente.enderecos) == 3, len(cliente.enderecos)
    etiquetas = [e.etiqueta for e in cliente.enderecos]
assert etiquetas == ["LOJA 1", "LOJA 2", "DEPÓSITO"], etiquetas
print("ok três endereços do mesmo tipo:", ", ".join(etiquetas))

# dois com o mesmo nome não passam
with session_scope() as sessao:
    try:
        repo_clientes.atualizar_cliente(sessao, cliente_id, DadosCliente(
            tipo=TipoCliente.PJ, nome="Rede Três Lojas LTDA",
            enderecos=[
                DadosEndereco(TipoEndereco.COMERCIAL, rotulo="Loja 1",
                              logradouro="Rua A", numero="1"),
                DadosEndereco(TipoEndereco.COMERCIAL, rotulo="loja 1",
                              logradouro="Rua Z", numero="9"),
            ]))
        raise AssertionError("aceitou dois endereços com o mesmo nome")
    except ValueError as erro:
        assert "Dê um nome diferente" in str(erro), erro
print("ok dois endereços com o mesmo nome são barrados")

# editar um, acrescentar outro e remover um terceiro, tudo de uma vez
with session_scope() as sessao:
    atual = repo_clientes.obter_cliente(sessao, cliente_id)
    ids = {e.etiqueta: e.id for e in atual.enderecos}
    repo_clientes.atualizar_cliente(sessao, cliente_id, DadosCliente(
        tipo=TipoCliente.PJ, nome="Rede Três Lojas LTDA",
        enderecos=[
            # mantém a Loja 1, mudando o número
            DadosEndereco(TipoEndereco.COMERCIAL, id=ids["LOJA 1"],
                          rotulo="Loja 1", logradouro="Rua A", numero="100",
                          cidade="BH"),
            # mantém o depósito
            DadosEndereco(TipoEndereco.COMERCIAL, id=ids["DEPÓSITO"],
                          rotulo="Depósito", logradouro="Rua C", numero="3",
                          cidade="Contagem"),
            # um novo, sem id
            DadosEndereco(TipoEndereco.RESIDENCIAL, rotulo="Casa do dono",
                          logradouro="Rua D", numero="4", cidade="Nova Lima"),
        ]))
with session_scope() as sessao:
    depois = repo_clientes.obter_cliente(sessao, cliente_id)
    etiquetas = [e.etiqueta for e in depois.enderecos]
    assert etiquetas == ["LOJA 1", "DEPÓSITO", "CASA DO DONO"], etiquetas
    loja = next(e for e in depois.enderecos if e.etiqueta == "LOJA 1")
    assert loja.id == ids["LOJA 1"], "editar não recria o endereço"
    assert loja.numero == "100"
    assert ids["LOJA 2"] not in {e.id for e in depois.enderecos}
print("ok editou, acrescentou e removeu numa só gravação")

# ---- pela tela -----------------------------------------------------------
janela = MainWindow()
janela.abas.setCurrentIndex(MainWindow.ABA_CLIENTES)
app.processEvents()
aba = janela.aba_clientes
for linha in range(aba.tabela.rowCount()):
    if dado_da_linha(aba.tabela, linha) == cliente_id:
        aba.tabela.selectRow(linha)
        break
app.processEvents()

assert len(aba._formularios_endereco()) == 3
assert aba.btn_endereco_novo.isVisibleTo(janela), "o botão fica à vista"
assert not aba._editando, "mas a ficha continua só de leitura até clicar"
print("ok ficha mostra os três endereços e o botão de adicionar")

aba._adicionar_endereco()
app.processEvents()
assert aba._editando, "o botão entra em edição sozinho"
assert len(aba._formularios_endereco()) == 4
novo = aba._formularios_endereco()[-1]
novo.rotulo_endereco.setText("Quiosque")
novo.logradouro.setText("Praça Sete")
novo.numero.setText("s/n")
novo.cidade.setText("Belo Horizonte")
aba._salvar()
app.processEvents()
with session_scope() as sessao:
    guardado = repo_clientes.obter_cliente(sessao, cliente_id)
    assert [e.etiqueta for e in guardado.enderecos][-1] == "QUIOSQUE"
    assert len(guardado.enderecos) == 4
print("ok incluiu o quarto endereço pela tela")

aba._editar()
formularios = aba._formularios_endereco()
aba._remover_endereco(formularios[0])
app.processEvents()
assert len(aba._formularios_endereco()) == 3
aba._salvar()
app.processEvents()
with session_scope() as sessao:
    sobrou = repo_clientes.obter_cliente(sessao, cliente_id)
    assert len(sobrou.enderecos) == 3
    assert "LOJA 1" not in [e.etiqueta for e in sobrou.enderecos]
print("ok removeu pela tela:", ", ".join(e.etiqueta for e in sobrou.enderecos))

# o diálogo do serviço enxerga todos
from app.ui.evento_dialog import EventoDialog  # noqa: E402

with session_scope() as sessao:
    lista = repo_clientes.listar_clientes(sessao)
dialogo = EventoDialog(None, lista, dia=dados["hoje"])
dialogo._definir_cliente(cliente_id)
assert dialogo.campo_endereco.count() == 3, dialogo.campo_endereco.count()
textos = [dialogo.campo_endereco.itemText(i) for i in range(3)]
assert any("QUIOSQUE" in t for t in textos), textos
print("ok marcação oferece os três:", " | ".join(t.split(" — ")[0] for t in textos))
# ---- endereço das lembrancinhas ------------------------------------------
from datetime import date  # noqa: E402

from app.repository import lembrancinhas as repo_lembrancinhas  # noqa: E402
from app.ui.clientes_tab import ClientesTab  # noqa: E402


def destinatarios_de(cid):
    with session_scope() as sessao:
        return [(d.bairro, d.ativo) for d in repo_lembrancinhas.listar(sessao)
                if d.cliente_id == cid]


def dados_com_marca(sessao, cid, marcar_rotulo):
    atual = repo_clientes.obter_cliente(sessao, cid)
    return DadosCliente(
        tipo=atual.tipo, nome=atual.nome, apelido=atual.apelido,
        enderecos=[
            DadosEndereco(e.tipo, id=e.id, rotulo=e.rotulo, logradouro=e.logradouro,
                          numero=e.numero, bairro=e.bairro, cidade=e.cidade,
                          lembrancinha=(e.rotulo == marcar_rotulo))
            for e in atual.enderecos
        ])


with session_scope() as sessao:
    marcado = repo_clientes.criar_cliente(sessao, DadosCliente(
        tipo=TipoCliente.PJ, nome="Escritório Presente LTDA",
        enderecos=[
            DadosEndereco(TipoEndereco.COMERCIAL, rotulo="Sede", logradouro="Rua X",
                          numero="1", bairro="Centro", cidade="BH", lembrancinha=True),
            DadosEndereco(TipoEndereco.RESIDENCIAL, rotulo="Casa do sócio",
                          logradouro="Rua Y", numero="2", bairro="Prado", cidade="BH"),
        ]))
    marcado_id = marcado.id
assert destinatarios_de(marcado_id) == [("CENTRO", True)], destinatarios_de(marcado_id)
print("ok endereço marcado põe o cliente na lista de lembrancinhas")

with session_scope() as sessao:
    repo_clientes.atualizar_cliente(
        sessao, marcado_id, dados_com_marca(sessao, marcado_id, "CASA DO SÓCIO"))
assert destinatarios_de(marcado_id) == [("PRADO", True)], destinatarios_de(marcado_id)
with session_scope() as sessao:
    repo_clientes.atualizar_cliente(
        sessao, marcado_id, dados_com_marca(sessao, marcado_id, None))
assert destinatarios_de(marcado_id) == [("PRADO", False)], destinatarios_de(marcado_id)
with session_scope() as sessao:
    dois = dados_com_marca(sessao, marcado_id, None)
    for e in dois.enderecos:
        e.lembrancinha = True
    try:
        repo_clientes.atualizar_cliente(sessao, marcado_id, dois)
    except ValueError:
        pass
    else:
        raise AssertionError("dois endereços de lembrancinha aceitos")
print("ok trocar o endereço atualiza; desmarcar tira da lista; só um por cliente")

with session_scope() as sessao:
    repo_clientes.atualizar_cliente(
        sessao, marcado_id, dados_com_marca(sessao, marcado_id, "SEDE"))
aba = janela.aba_clientes
aba.recarregar()
aba._abrir(marcado_id)
assert aba._lembrancinhas.get(marcado_id) is not None, "selo na ficha"
nomes = [aba.tabela.item(l, 0).text() for l in range(aba.tabela.rowCount())]
assert any("🎁" in n and "PRESENTE" in n for n in nomes), nomes
aba._editar()
formularios = aba._formularios_endereco()
assert [f.lembrancinha.isChecked() for f in formularios] == [True, False]
formularios[1].lembrancinha.setChecked(True)
assert [f.lembrancinha.isChecked() for f in formularios] == [False, True], "um só"
aba._descartar()
assert aba.pilha.currentIndex() == ClientesTab.PAGINA_FICHA
print("ok lista e ficha mostram o 🎁; no cadastro, marcar um desmarca o outro")
# ---- quem recebe: vários contatos, e o serviço aos cuidados de um ---------
from datetime import timedelta  # noqa: E402

from app.models import Periodo  # noqa: E402
from app.repository import eventos as repo_eventos  # noqa: E402
from app.schemas import DadosContato, DadosEvento  # noqa: E402

with session_scope() as sessao:
    loja = repo_clientes.criar_cliente(sessao, DadosCliente(
        tipo=TipoCliente.PJ, nome="Loja Dois Contatos LTDA",
        contatos=[DadosContato("Ana", "(31) 1111-1111"),
                  DadosContato("financeiro", "(31) 2222-2222"),
                  DadosContato("", "")],
        enderecos=[DadosEndereco(TipoEndereco.COMERCIAL, rotulo="Loja",
                                 logradouro="Rua Z", numero="9", cidade="BH")]))
    loja_id = loja.id
    assert [c.descricao for c in loja.contatos] == [
        "ANA · (31) 1111-1111", "FINANCEIRO · (31) 2222-2222"], "linha vazia some"
    assert loja.telefone == "(31) 1111-1111", "o primeiro é o telefone principal"
    financeiro_id = loja.contatos[1].id
    servico = repo_eventos.criar_evento(sessao, DadosEvento(
        cliente_id=loja.id, tipo_servico_id=dados["tipos"]["Coleta"],
        data=dados["hoje"], periodo=Periodo.MANHA,
        endereco_id=loja.enderecos[0].id, contato_id=financeiro_id))
    assert servico.contato.responsavel == "FINANCEIRO"
    novo = repo_eventos.reagendar(sessao, servico.id, dados["hoje"] + timedelta(days=1))
    assert novo.contato_id == financeiro_id, "a remarcação leva quem recebe"
    outro = repo_clientes.listar_clientes(sessao)[0]
    try:
        repo_eventos.criar_evento(sessao, DadosEvento(
            cliente_id=outro.id, tipo_servico_id=dados["tipos"]["Coleta"],
            data=dados["hoje"], periodo=Periodo.MANHA,
            endereco_id=outro.enderecos[0].id if outro.enderecos else None,
            contato_id=financeiro_id))
    except ValueError:
        pass
    else:
        raise AssertionError("contato de outro cliente aceito")
print("ok dois contatos, telefone principal, serviço aos cuidados de um")

# a planilha (só telefone) não apaga quem recebe
with session_scope() as sessao:
    repo_clientes.atualizar_cliente(sessao, loja_id, DadosCliente(
        tipo=TipoCliente.PJ, nome="Loja Dois Contatos LTDA", telefone="(31) 3333-3333",
        enderecos=[DadosEndereco(TipoEndereco.COMERCIAL, id=e.id, rotulo=e.rotulo,
                                 logradouro=e.logradouro, numero=e.numero, cidade=e.cidade)
                   for e in repo_clientes.obter_cliente(sessao, loja_id).enderecos]))
    loja = repo_clientes.obter_cliente(sessao, loja_id)
    assert [c.responsavel for c in loja.contatos] == ["ANA", "FINANCEIRO"]
    assert loja.contatos[0].telefone == loja.telefone == "(31) 3333-3333"
print("ok telefone avulso (planilha) atualiza o principal sem perder ninguém")

# pela tela: a linha nova, a remoção, e o diálogo do serviço
aba = janela.aba_clientes
aba.recarregar()
aba._abrir(loja_id)
aba._editar()
linhas = aba._linhas_contato()
assert [l.responsavel.text() for l in linhas] == ["ANA", "FINANCEIRO"]
nova = aba._acrescentar_contato()
nova.responsavel.setText("Sócio Carlos")
nova.telefone.setText("(31) 98888-7777")
aba._remover_contato(linhas[0])
aba._salvar()
with session_scope() as sessao:
    loja = repo_clientes.obter_cliente(sessao, loja_id)
    assert [c.responsavel for c in loja.contatos] == ["FINANCEIRO", "SÓCIO CARLOS"]
    assert loja.telefone == "(31) 2222-2222"
    lista = repo_clientes.listar_clientes(sessao)
print("ok tela: acrescenta e tira contato; o principal acompanha")

dialogo = EventoDialog(None, lista, dia=dados["hoje"])
dialogo._definir_cliente(loja_id)
assert dialogo.campo_contato.count() == 3, dialogo.campo_contato.count()
assert dialogo.campo_contato.currentData() is not None, "o primeiro vem escolhido"
dialogo.campo_contato.setCurrentIndex(2)
assert dialogo._dados().contato_id == dialogo.campo_contato.itemData(2)
print("ok diálogo do serviço: aos cuidados de um dos contatos")
print("TESTE ENDERECOS OK")
