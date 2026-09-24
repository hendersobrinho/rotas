"""Cliente e endereço são obrigatórios para marcar um serviço."""

from __future__ import annotations

from datetime import date

from comum import preparar_ambiente, semear

preparar_ambiente()

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication([])

from app.db import session_scope  # noqa: E402
from app.models import FrequenciaRecorrencia, Periodo, TipoCliente  # noqa: E402
from app.repository import clientes as repo_clientes  # noqa: E402
from app.repository import eventos as repo_eventos  # noqa: E402
from app.repository import recorrencias as repo_recorrencias  # noqa: E402
from app.schemas import (  # noqa: E402
    DadosCliente,
    DadosEvento,
    DadosRecorrencia,
)
from app.ui.estilo import aplicar_tema  # noqa: E402
from app.ui.evento_dialog import EventoDialog  # noqa: E402
from app.ui.recorrencia_dialog import RecorrenciaDialog  # noqa: E402

aplicar_tema(app)
dados = semear()
hoje = dados["hoje"]
tipo_id = dados["tipos"]["Coleta"]

com_endereco = next(c for c in dados["clientes"] if c.enderecos)
sem_endereco = next(c for c in dados["clientes"] if not c.enderecos)

# ---- pelo repositório ----------------------------------------------------
with session_scope() as sessao:
    try:
        repo_eventos.criar_evento(sessao, DadosEvento(
            cliente_id=com_endereco.id, tipo_servico_id=tipo_id,
            data=hoje, periodo=Periodo.MANHA))
        raise AssertionError("aceitou serviço sem endereço")
    except ValueError as erro:
        assert "Escolha o endereço" in str(erro), erro
        print("ok sem endereço:", str(erro).splitlines()[0])

with session_scope() as sessao:
    try:
        repo_eventos.criar_evento(sessao, DadosEvento(
            cliente_id=sem_endereco.id, tipo_servico_id=tipo_id,
            data=hoje, periodo=Periodo.MANHA))
        raise AssertionError("aceitou cliente sem endereço cadastrado")
    except ValueError as erro:
        assert "não tem endereço cadastrado" in str(erro), erro
        print("ok cliente sem endereço:", str(erro).splitlines()[0])

with session_scope() as sessao:
    outro = com_endereco.enderecos[0].id
    try:
        repo_eventos.criar_evento(sessao, DadosEvento(
            cliente_id=sem_endereco.id, tipo_servico_id=tipo_id,
            data=hoje, periodo=Periodo.MANHA, endereco_id=outro))
        raise AssertionError("aceitou endereço de outro cliente")
    except ValueError as erro:
        assert "não pertence a este cliente" in str(erro), erro
        print("ok endereço de outro cliente barrado")

# com endereço, passa
with session_scope() as sessao:
    evento = repo_eventos.criar_evento(sessao, DadosEvento(
        cliente_id=com_endereco.id, tipo_servico_id=tipo_id,
        data=hoje, periodo=Periodo.MANHA,
        endereco_id=com_endereco.enderecos[0].id))
    criado_id = evento.id
print("ok com endereço, o serviço é criado")

# editar também exige
with session_scope() as sessao:
    try:
        repo_eventos.atualizar_evento(sessao, criado_id, DadosEvento(
            cliente_id=com_endereco.id, tipo_servico_id=tipo_id,
            data=hoje, periodo=Periodo.TARDE))
        raise AssertionError("edição aceitou apagar o endereço")
    except ValueError as erro:
        assert "Escolha o endereço" in str(erro)
print("ok a edição não deixa tirar o endereço")

# ---- serviço fixo --------------------------------------------------------
with session_scope() as sessao:
    try:
        repo_recorrencias.criar(sessao, DadosRecorrencia(
            cliente_id=com_endereco.id, tipo_servico_id=tipo_id,
            frequencia=FrequenciaRecorrencia.SEMANAL, dia_semana=0))
        raise AssertionError("regra aceita sem endereço")
    except ValueError as erro:
        assert "Escolha o endereço" in str(erro), erro
print("ok serviço fixo também exige endereço")

# ---- pelas telas ---------------------------------------------------------
with session_scope() as sessao:
    lista = repo_clientes.listar_clientes(sessao)
    carregado_com = repo_clientes.obter_cliente(sessao, com_endereco.id)
    carregado_sem = repo_clientes.obter_cliente(sessao, sem_endereco.id)

dialogo = EventoDialog(None, lista, dia=hoje)
assert dialogo._cliente_id is None
assert not dialogo.campo_endereco.isEnabled(), "sem cliente, nem escolhe endereço"
try:
    dialogo._dados()
    raise AssertionError("aceitou sem cliente")
except ValueError as erro:
    assert "cliente" in str(erro).lower(), erro
print("ok tela: sem cliente não salva")

dialogo._definir_cliente(sem_endereco.id)
assert not dialogo.campo_endereco.isEnabled()
assert dialogo.aviso_endereco.isVisibleTo(dialogo)
assert "não tem endereço" in dialogo.aviso_endereco.text()
try:
    dialogo._dados()
    raise AssertionError("aceitou cliente sem endereço")
except ValueError as erro:
    assert "não tem endereço cadastrado" in str(erro), erro
print("ok tela: cliente sem endereço avisa e não salva")

dialogo._definir_cliente(com_endereco.id)
assert dialogo.campo_endereco.isEnabled()
assert dialogo.campo_endereco.count() == len(carregado_com.enderecos)
assert dialogo.campo_endereco.currentData() is not None, "já vem com um escolhido"
assert all(
    dialogo.campo_endereco.itemData(i) is not None
    for i in range(dialogo.campo_endereco.count())
), "não existe opção de deixar em branco"
dados_ok = dialogo._dados()
assert dados_ok.endereco_id in {e.id for e in carregado_com.enderecos}
print("ok tela: com endereço, os dados saem prontos")

# O diálogo avisa o erro numa caixa modal, que travaria o teste: aqui ela vira
# uma lista. Trocar o atributo do módulo funciona; mexer na classe do Qt, não.
from app.ui import recorrencia_dialog as modulo_fixo  # noqa: E402

erros: list[str] = []
modulo_fixo.mostrar_erro = lambda _pai, erro, *_r: erros.append(str(erro))

fixo = RecorrenciaDialog(None, carregado_sem)
assert not fixo.campo_endereco.isEnabled()
fixo._salvar()
assert erros and "não tem endereço" in erros[0], erros
assert fixo.recorrencia_id is None, "não salvou sem endereço"
print("ok tela do serviço fixo: sem endereço, não salva")

fixo_ok = RecorrenciaDialog(None, carregado_com)
assert fixo_ok.campo_endereco.isEnabled()
assert fixo_ok.campo_endereco.currentData() is not None
print("ok tela do serviço fixo: com endereço, segue")
print("TESTE OBRIGATORIOS OK")
