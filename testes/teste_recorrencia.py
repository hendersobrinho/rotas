"""Verifica as regras de repetição dos serviços fixos e a abertura automática."""

from __future__ import annotations

from datetime import date, timedelta

from comum import preparar_ambiente, semear

preparar_ambiente()

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication([])

from app.db import session_scope  # noqa: E402
from app.models import FrequenciaRecorrencia, Periodo, Recorrencia, StatusEvento  # noqa: E402
from app.repository import eventos as repo_eventos  # noqa: E402
from app.repository import recorrencias as repo  # noqa: E402
from app.schemas import DadosRecorrencia  # noqa: E402

SEGUNDA, SEXTA, SABADO = 0, 4, 5


def regra(**campos) -> Recorrencia:
    """Uma regra solta, só para conferir as datas."""
    return Recorrencia(**campos)


# ---- toda semana ---------------------------------------------------------
semanal = regra(frequencia=FrequenciaRecorrencia.SEMANAL, dia_semana=SEGUNDA)
datas = repo.ocorrencias(semanal, date(2026, 9, 1), date(2026, 9, 30))
assert datas == [date(2026, 9, 7), date(2026, 9, 14), date(2026, 9, 21),
                 date(2026, 9, 28)], datas
assert all(d.weekday() == SEGUNDA for d in datas)
# começando exatamente numa segunda, ela entra
assert repo.ocorrencias(semanal, date(2026, 9, 7), date(2026, 9, 7)) == [date(2026, 9, 7)]
assert repo.ocorrencias(semanal, date(2026, 9, 8), date(2026, 9, 13)) == []
print("ok semanal:", ", ".join(d.strftime("%d/%m") for d in datas))

# ---- dia da semana no mês ("toda primeira segunda útil") ----------------
primeira_segunda = regra(
    frequencia=FrequenciaRecorrencia.MENSAL_ORDINAL, dia_semana=SEGUNDA, ordinal=1
)
datas = repo.ocorrencias(primeira_segunda, date(2026, 9, 1), date(2026, 12, 31))
assert datas == [date(2026, 9, 7), date(2026, 10, 5), date(2026, 11, 2),
                 date(2026, 12, 7)], datas
print("ok 1ª segunda do mês:", ", ".join(d.strftime("%d/%m") for d in datas))

ultima_sexta = regra(
    frequencia=FrequenciaRecorrencia.MENSAL_ORDINAL, dia_semana=SEXTA, ordinal=-1
)
datas = repo.ocorrencias(ultima_sexta, date(2026, 9, 1), date(2026, 11, 30))
assert datas == [date(2026, 9, 25), date(2026, 10, 30), date(2026, 11, 27)], datas
assert all(d.weekday() == SEXTA for d in datas)
print("ok última sexta do mês:", ", ".join(d.strftime("%d/%m") for d in datas))

# 5ª segunda: só existe nos meses que têm cinco
quinta_segunda = regra(
    frequencia=FrequenciaRecorrencia.MENSAL_ORDINAL, dia_semana=SEGUNDA, ordinal=5
)
datas = repo.ocorrencias(quinta_segunda, date(2026, 1, 1), date(2026, 12, 31))
assert all(d.weekday() == SEGUNDA and d.day > 28 for d in datas), datas
assert len(datas) < 12, "mês sem quinta segunda é pulado, não empurrado"
print(f"ok 5ª segunda existe em {len(datas)} meses de 2026")

# ---- dia fixo do mês -----------------------------------------------------
dia_31 = regra(
    frequencia=FrequenciaRecorrencia.MENSAL_DIA, dia_mes=31, apenas_util=False
)
datas = repo.ocorrencias(dia_31, date(2026, 1, 1), date(2026, 4, 30))
assert datas == [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31),
                 date(2026, 4, 30)], datas
print("ok dia 31 cai no último dia dos meses curtos:",
      ", ".join(d.strftime("%d/%m") for d in datas))

dia_5_util = regra(
    frequencia=FrequenciaRecorrencia.MENSAL_DIA, dia_mes=5, apenas_util=True
)
datas = repo.ocorrencias(dia_5_util, date(2026, 9, 1), date(2026, 12, 31))
assert all(d.weekday() < SABADO for d in datas), datas
assert date(2026, 12, 7) in datas, "5/12/2026 é sábado; vai para a segunda"
print("ok dia 5 útil:", ", ".join(d.strftime("%d/%m (%a)") for d in datas))

dia_5_corrido = regra(
    frequencia=FrequenciaRecorrencia.MENSAL_DIA, dia_mes=5, apenas_util=False
)
assert date(2026, 12, 5) in repo.ocorrencias(
    dia_5_corrido, date(2026, 12, 1), date(2026, 12, 31)
), "sem 'apenas útil', o sábado vale"
print("ok sem 'apenas útil', fim de semana é aceito")

# ---- como a regra é escrita na tela --------------------------------------
assert repo.descrever(semanal) == "Toda segunda-feira"
assert repo.descrever(primeira_segunda) == "Na primeira segunda-feira do mês"
assert repo.descrever(ultima_sexta) == "Na última sexta-feira do mês"
assert "pulando fim de semana" in repo.descrever(dia_5_util)
print("ok descrições:", repo.descrever(primeira_segunda))

# ---- abertura automática na agenda --------------------------------------
dados = semear()
hoje = dados["hoje"]
cliente = dados["clientes"][0]
with session_scope() as sessao:
    fixa = repo.criar(sessao, DadosRecorrencia(
        cliente_id=cliente.id,
        tipo_servico_id=dados["tipos"]["Coleta"],
        frequencia=FrequenciaRecorrencia.MENSAL_ORDINAL,
        dia_semana=SEGUNDA, ordinal=1, periodo=Periodo.TARDE,
        endereco_id=cliente.enderecos[0].id if cliente.enderecos else None,
        solicitante_id=dados["solicitantes"][0]))
    regra_id = fixa.id

with session_scope() as sessao:
    criados = repo.gerar(sessao, ate=hoje + timedelta(days=120), a_partir_de=hoje)
    assert criados, "a regra deveria abrir serviços"
    quantos = len(criados)
    for evento in criados:
        assert evento.recorrencia_id == regra_id
        assert evento.status is StatusEvento.PENDENTE
        assert evento.periodo is Periodo.TARDE, "herda o período da regra"
        assert evento.data.weekday() == SEGUNDA
print(f"ok gerou {quantos} serviço(s) fixos")

with session_scope() as sessao:
    de_novo = repo.gerar(sessao, ate=hoje + timedelta(days=120), a_partir_de=hoje)
    assert de_novo == [], "rodar de novo não duplica"
print("ok rodar de novo não duplica")

# cancelar um gerado e rodar outra vez não o ressuscita
with session_scope() as sessao:
    algum = [e for e in repo_eventos.listar_eventos(sessao)
             if e.recorrencia_id == regra_id][0]
    alvo_id, alvo_data = algum.id, algum.data
    repo_eventos.cancelar_evento(sessao, alvo_id)
with session_scope() as sessao:
    assert repo.gerar(sessao, ate=hoje + timedelta(days=120), a_partir_de=hoje) == []
    ainda = repo_eventos.obter_evento(sessao, alvo_id)
    assert ainda.status is StatusEvento.CANCELADO, "não mexe no que já existe"
    mesmos_dias = [e for e in repo_eventos.listar_eventos(sessao)
                   if e.recorrencia_id == regra_id and e.data == alvo_data]
    assert len(mesmos_dias) == 1
print("ok serviço cancelado não volta na próxima geração")

# apagar a regra deixa o histórico em paz
with session_scope() as sessao:
    antes = repo.contar_gerados(sessao, regra_id)
    repo.excluir(sessao, regra_id)
with session_scope() as sessao:
    assert repo.obter(sessao, regra_id) is None
    sobraram = [e for e in repo_eventos.listar_eventos(sessao)
                if e.data >= hoje and e.recorrencia_id is None]
    assert len(sobraram) >= antes - 1
print(f"ok regra apagada, os {antes} serviços já abertos continuam")

# validações
with session_scope() as sessao:
    for campos, esperado in (
        (dict(frequencia=FrequenciaRecorrencia.SEMANAL), "dia da semana"),
        (dict(frequencia=FrequenciaRecorrencia.MENSAL_ORDINAL, dia_semana=0,
              ordinal=9), "semana do mês"),
        (dict(frequencia=FrequenciaRecorrencia.MENSAL_DIA, dia_mes=45), "entre 1 e 31"),
    ):
        try:
            repo.criar(sessao, DadosRecorrencia(
                cliente_id=cliente.id,
                tipo_servico_id=dados["tipos"]["Coleta"], **campos))
            raise AssertionError(f"aceitou regra inválida: {campos}")
        except ValueError as erro:
            assert esperado in str(erro), erro
print("ok validações da regra")

# ---- a tela ---------------------------------------------------------------
from app.ui.estilo import aplicar_tema  # noqa: E402
from app.ui.recorrencia_dialog import RecorrenciaDialog  # noqa: E402

aplicar_tema(app)
with session_scope() as sessao:
    from app.repository import clientes as repo_clientes

    alvo = repo_clientes.obter_cliente(sessao, cliente.id)

dialogo = RecorrenciaDialog(None, alvo)
assert dialogo.campo_servico.count() >= 1
dialogo.campo_frequencia.definir_valor(FrequenciaRecorrencia.MENSAL_ORDINAL)
dialogo._trocar_frequencia(FrequenciaRecorrencia.MENSAL_ORDINAL)
dialogo.campo_ordinal.setCurrentIndex(dialogo.campo_ordinal.findData(1))
dialogo.campo_dia_semana_mes.setCurrentIndex(0)   # segunda
dialogo._atualizar_previa()
assert "primeira segunda-feira" in dialogo.previa.text(), dialogo.previa.text()
assert "próximas:" in dialogo.previa.text()
print("ok prévia na tela:", dialogo.previa.text())

dialogo.campo_frequencia.definir_valor(FrequenciaRecorrencia.MENSAL_DIA)
dialogo._trocar_frequencia(FrequenciaRecorrencia.MENSAL_DIA)
dialogo.campo_dia_mes.setValue(31)
dialogo._atualizar_previa()
assert "Todo dia 31" in dialogo.previa.text(), dialogo.previa.text()
dialogo._salvar()
assert dialogo.recorrencia_id is not None
with session_scope() as sessao:
    salva = repo.obter(sessao, dialogo.recorrencia_id)
    assert salva.dia_mes == 31 and salva.apenas_util
print("ok diálogo salvou a regra")

# o cartão dentro da ficha do cliente
from app.ui.main_window import MainWindow  # noqa: E402

janela = MainWindow()
janela.abas.setCurrentIndex(MainWindow.ABA_CLIENTES)
app.processEvents()
aba = janela.aba_clientes
for linha in range(aba.tabela.rowCount()):
    from app.ui.widgets import dado_da_linha

    if dado_da_linha(aba.tabela, linha) == cliente.id:
        aba.tabela.selectRow(linha)
        break
app.processEvents()
assert aba.tabela_fixos.rowCount() == 1, aba.tabela_fixos.rowCount()
assert "Todo dia 31" in aba.tabela_fixos.item(0, 0).text()
print("ok cartão na ficha:", aba.tabela_fixos.item(0, 0).text())

# O botão avisa por caixa de diálogo, que travaria o teste. Trocar o atributo
# do módulo funciona; mexer na classe do PySide, não.
from app.ui import clientes_tab as modulo_clientes  # noqa: E402

avisos: list[str] = []


class CaixaFalsa:
    @staticmethod
    def information(_pai, _titulo, texto, *_resto):
        avisos.append(texto)


modulo_clientes.QMessageBox = CaixaFalsa
aba._gerar_fixos()
app.processEvents()
with session_scope() as sessao:
    abertos = [e for e in repo_eventos.listar_eventos(sessao)
               if e.recorrencia_id == dialogo.recorrencia_id]
assert abertos, "o botão Gerar agora abriu os serviços"
assert avisos and "serviço" in avisos[0], avisos
print(f"ok botão Gerar agora abriu {len(abertos)} serviço(s) —", avisos[0])
print("TESTE RECORRENCIA OK")
