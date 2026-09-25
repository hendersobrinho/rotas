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
assert etiquetas == ["Loja 1", "Loja 2", "Depósito"], etiquetas
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
            DadosEndereco(TipoEndereco.COMERCIAL, id=ids["Loja 1"],
                          rotulo="Loja 1", logradouro="Rua A", numero="100",
                          cidade="BH"),
            # mantém o depósito
            DadosEndereco(TipoEndereco.COMERCIAL, id=ids["Depósito"],
                          rotulo="Depósito", logradouro="Rua C", numero="3",
                          cidade="Contagem"),
            # um novo, sem id
            DadosEndereco(TipoEndereco.RESIDENCIAL, rotulo="Casa do dono",
                          logradouro="Rua D", numero="4", cidade="Nova Lima"),
        ]))
with session_scope() as sessao:
    depois = repo_clientes.obter_cliente(sessao, cliente_id)
    etiquetas = [e.etiqueta for e in depois.enderecos]
    assert etiquetas == ["Loja 1", "Depósito", "Casa do dono"], etiquetas
    loja = next(e for e in depois.enderecos if e.etiqueta == "Loja 1")
    assert loja.id == ids["Loja 1"], "editar não recria o endereço"
    assert loja.numero == "100"
    assert ids["Loja 2"] not in {e.id for e in depois.enderecos}
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
    assert [e.etiqueta for e in guardado.enderecos][-1] == "Quiosque"
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
    assert "Loja 1" not in [e.etiqueta for e in sobrou.enderecos]
print("ok removeu pela tela:", ", ".join(e.etiqueta for e in sobrou.enderecos))

# o diálogo do serviço enxerga todos
from app.ui.evento_dialog import EventoDialog  # noqa: E402

with session_scope() as sessao:
    lista = repo_clientes.listar_clientes(sessao)
dialogo = EventoDialog(None, lista, dia=dados["hoje"])
dialogo._definir_cliente(cliente_id)
assert dialogo.campo_endereco.count() == 3, dialogo.campo_endereco.count()
textos = [dialogo.campo_endereco.itemText(i) for i in range(3)]
assert any("Quiosque" in t for t in textos), textos
print("ok marcação oferece os três:", " | ".join(t.split(" — ")[0] for t in textos))
print("TESTE ENDERECOS OK")
