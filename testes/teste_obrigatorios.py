"""Cliente e endereço são obrigatórios para marcar um serviço."""

from __future__ import annotations

from comum import preparar_ambiente, semear

preparar_ambiente()

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication([])

from app.db import session_scope  # noqa: E402
from app.models import FrequenciaRecorrencia, Periodo  # noqa: E402
from app.repository import clientes as repo_clientes  # noqa: E402
from app.repository import eventos as repo_eventos  # noqa: E402
from app.repository import recorrencias as repo_recorrencias  # noqa: E402
from app.schemas import DadosEvento, DadosRecorrencia  # noqa: E402
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

# Cliente sem endereço: a regra até pode ser guardada, mas nasce parada — é o
# que permite desligar uma regra que perdeu o endereço, em vez de só apagá-la.
fixo = RecorrenciaDialog(None, carregado_sem)
assert not fixo.campo_endereco.isEnabled()
assert not fixo.campo_ativo.isChecked() and not fixo.campo_ativo.isEnabled()
fixo._salvar()
assert fixo.recorrencia_id is not None
with session_scope() as sessao:
    parada = repo_recorrencias.obter(sessao, fixo.recorrencia_id)
    assert parada.endereco_id is None and not parada.ativo
print("ok serviço fixo sem endereço nasce parado")

# e parado não abre nada
with session_scope() as sessao:
    repo_recorrencias.gerar(sessao, a_partir_de=hoje)
    abertos_sem = [
        e for e in repo_eventos.listar_eventos(sessao)
        if e.recorrencia_id == fixo.recorrencia_id
    ]
    assert abertos_sem == [], abertos_sem
print("ok regra parada não abre serviço")

# regra ligada que perdeu o endereço também não abre — e ainda aparece na lista
with session_scope() as sessao:
    regra = repo_recorrencias.obter(sessao, fixo.recorrencia_id)
    regra.ativo = True          # simula o que o ON DELETE SET NULL deixaria
    sessao.flush()
with session_scope() as sessao:
    criados = repo_recorrencias.gerar(sessao, a_partir_de=hoje)
    assert all(e.recorrencia_id != fixo.recorrencia_id for e in criados)
    pendentes = repo_recorrencias.listar_sem_endereco(sessao)
    assert any(r.id == fixo.recorrencia_id for r in pendentes)
print("ok regra ligada sem endereço fica de fora da geração")

# e a tela dessa regra reativada precisa ter saída: ou escolher endereço, ou
# desligar — nunca abrir travada num estado que não salva
with session_scope() as sessao:
    reativada = repo_recorrencias.obter(sessao, fixo.recorrencia_id)
tela = RecorrenciaDialog(None, carregado_sem, reativada)
assert not tela.campo_ativo.isChecked(), "não pode abrir marcada e travada"
assert not tela.campo_ativo.isEnabled()
tela._salvar()
with session_scope() as sessao:
    depois = repo_recorrencias.obter(sessao, fixo.recorrencia_id)
    assert not depois.ativo, "dava para desligar"
print("ok regra sem endereço abre desligada e pode ser salva assim")

# com endereço disponível, a regra sem endereço não adota nenhum sozinha
with session_scope() as sessao:
    solta = repo_recorrencias.criar(sessao, DadosRecorrencia(
        cliente_id=com_endereco.id, tipo_servico_id=tipo_id,
        frequencia=FrequenciaRecorrencia.SEMANAL, dia_semana=0, ativo=False))
    solta_id = solta.id
    carregada = repo_recorrencias.obter(sessao, solta_id)
    dono = repo_clientes.obter_cliente(sessao, com_endereco.id)
tela_solta = RecorrenciaDialog(None, dono, carregada)
assert tela_solta.campo_endereco.currentData() is None, (
    "regra sem endereço não pode adotar o primeiro da lista"
)
assert tela_solta.campo_endereco.itemText(0) == "Escolha o endereço"
print("ok regra sem endereço não adota endereço sozinha")

fixo_ok = RecorrenciaDialog(None, carregado_com)
assert fixo_ok.campo_endereco.isEnabled()
assert fixo_ok.campo_endereco.currentData() is not None
assert fixo_ok.campo_ativo.isEnabled()
print("ok tela do serviço fixo: com endereço, segue")

# ---- o que já está gravado sem endereço ----------------------------------
from app.models import Evento  # noqa: E402

with session_scope() as sessao:
    antigo = Evento(
        cliente_id=sem_endereco.id, tipo_servico_id=tipo_id,
        data=hoje, periodo=Periodo.MANHA)
    sessao.add(antigo)
    sessao.flush()
    antigo_id = antigo.id

with session_scope() as sessao:
    # editar continua possível: o cliente não tem de onde escolher
    repo_eventos.atualizar_evento(sessao, antigo_id, DadosEvento(
        cliente_id=sem_endereco.id, tipo_servico_id=tipo_id,
        data=hoje, periodo=Periodo.TARDE))
    assert repo_eventos.obter_evento(sessao, antigo_id).periodo is Periodo.TARDE
print("ok serviço antigo sem endereço continua editável")

with session_scope() as sessao:
    try:
        repo_eventos.reagendar(sessao, antigo_id, hoje)
        print("ok remarcação do antigo segue (cliente sem endereço)")
    except ValueError as erro:
        raise AssertionError(f"não devia barrar: {erro}")

# já um serviço sem endereço de um cliente QUE TEM endereço precisa escolher
with session_scope() as sessao:
    orfao = Evento(
        cliente_id=com_endereco.id, tipo_servico_id=tipo_id,
        data=hoje, periodo=Periodo.MANHA)
    sessao.add(orfao)
    sessao.flush()
    orfao_id = orfao.id
with session_scope() as sessao:
    try:
        repo_eventos.reagendar(sessao, orfao_id, hoje)
        raise AssertionError("remarcou sem endereço tendo onde escolher")
    except ValueError as erro:
        assert "Escolha o endereço" in str(erro), erro
print("ok remarcação exige endereço quando há onde escolher")

# ---- endereço apagado do cadastro não troca de destino sozinho -----------
with session_scope() as sessao:
    cliente_dois = repo_clientes.obter_cliente(sessao, com_endereco.id)
    ids = [e.id for e in cliente_dois.enderecos]
if len(ids) == 1:
    with session_scope() as sessao:
        from app.models import Endereco, TipoEndereco as TE

        extra = Endereco(cliente_id=com_endereco.id, tipo=TE.RESIDENCIAL,
                         logradouro="Rua Nova", numero="9", cidade="Contagem")
        sessao.add(extra)
        sessao.flush()
        extra_id = extra.id
else:
    extra_id = ids[1]

with session_scope() as sessao:
    evento = repo_eventos.criar_evento(sessao, DadosEvento(
        cliente_id=com_endereco.id, tipo_servico_id=tipo_id,
        data=hoje, periodo=Periodo.MANHA, endereco_id=extra_id))
    evento_id = evento.id
with session_scope() as sessao:  # o endereço sai do cadastro
    sessao.delete(sessao.get(type(evento), evento_id).endereco)
with session_scope() as sessao:
    conferindo = repo_eventos.obter_evento(sessao, evento_id)
    assert conferindo.endereco_id is None, "ON DELETE SET NULL"
    lista_clientes = repo_clientes.listar_clientes(sessao)
    alvo = repo_clientes.obter_cliente(sessao, com_endereco.id)
    guardado = repo_eventos.obter_evento(sessao, evento_id)

dialogo_orfao = EventoDialog(None, lista_clientes, evento=guardado)
assert dialogo_orfao.campo_endereco.currentData() is None, (
    "não pode escolher outro endereço sozinho"
)
assert "sem endereço" in dialogo_orfao.aviso_endereco.text(), (
    dialogo_orfao.aviso_endereco.text()
)
assert all(
    dialogo_orfao.campo_endereco.itemData(i) is not None
    for i in range(1, dialogo_orfao.campo_endereco.count())
), "os endereços do cliente continuam na lista, para escolher"
try:
    dialogo_orfao._dados()
    raise AssertionError("salvou adotando outro endereço")
except ValueError as erro:
    assert "Escolha o endereço" in str(erro), erro
print("ok endereço apagado: a tela avisa e não adota outro sozinha")
print("TESTE OBRIGATORIOS OK")
