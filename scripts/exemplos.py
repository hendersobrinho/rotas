"""Cadastra situações de exemplo para ver como o programa fica com dados.

    .venv-win\\Scripts\\python scripts\\exemplos.py           # cadastra
    .venv-win\\Scripts\\python scripts\\exemplos.py --apagar  # tira tudo de novo

Cria clientes (empresas e pessoas, com sócios), solicitantes, um tipo de
serviço a mais, serviços em todas as situações — atrasados, de hoje, baixados,
não realizados, remarcados, cancelados, futuros e automáticos — e destinatários
de lembrancinha. O que foi criado fica anotado em `exemplos.json`, na pasta de
dados do programa, e o --apagar remove exatamente isso, sem tocar no resto.
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app import caminhos  # noqa: E402
from app import sessao as sessao_app  # noqa: E402
from app.db import init_db, session_scope, url_mascarada  # noqa: E402
from app.models import (  # noqa: E402
    FrequenciaRecorrencia,
    Periodo,
    SituacaoLembrancinha,
    TipoCliente,
    TipoEndereco,
)
from app.repository import clientes as rc  # noqa: E402
from app.repository import eventos as re_  # noqa: E402
from app.repository import lembrancinhas as rl  # noqa: E402
from app.repository import recorrencias as rr  # noqa: E402
from app.repository import socios as rsoc  # noqa: E402
from app.repository import solicitantes as rs  # noqa: E402
from app.repository import tipos_servico as rt  # noqa: E402
from app.repository import usuarios as ru  # noqa: E402
from app.schemas import (  # noqa: E402
    DadosCliente,
    DadosDestinatario,
    DadosEndereco,
    DadosEvento,
    DadosRecorrencia,
    DadosSolicitante,
    DadosTipoServico,
    maiusculo,
)

ARQUIVO = caminhos.garantir(caminhos.pasta_dados()) / "exemplos.json"
BH = "Belo Horizonte"
COM = TipoEndereco.COMERCIAL
RES = TipoEndereco.RESIDENCIAL
M, T = Periodo.MANHA, Periodo.TARDE


def _end(tipo, rotulo, logradouro, numero, bairro, cidade=BH, cep=None,
         complemento=None, observacao=None, lembrancinha=False) -> DadosEndereco:
    return DadosEndereco(tipo, rotulo=rotulo, logradouro=logradouro, numero=numero,
                         complemento=complemento, bairro=bairro, cidade=cidade,
                         cep=cep, observacao=observacao, lembrancinha=lembrancinha)


CLIENTES = [
    # chave, tipo, nome, apelido, telefone, observação, endereços
    ("padaria", TipoCliente.PJ, "Panificadora Estrela do Oriente LTDA", "Padaria Estrela",
     "(31) 3222-1010", "Falar com a Ana; o gerente não assina nada.", [
         _end(COM, "Matriz", "Av. Brasil", "1200", "Savassi", cep="30140-002",
              complemento="Loja 3", observacao="Entrada pela lateral depois das 18h.",
              lembrancinha=True),
         _end(COM, "Filial Barreiro", "Av. Olinto Meireles", "90", "Barreiro",
              cep="30640-010"),
     ]),
    ("construtora", TipoCliente.PJ, "Construtora Horizonte Mineiro S.A.", "Construtora Horizonte",
     "(31) 3333-4500", "Documentos sempre com a recepção do 4º andar.", [
         _end(COM, "Sede", "Rua dos Timbiras", "2250", "Lourdes", cep="30140-061",
              complemento="4º andar", lembrancinha=True),
         _end(COM, "Canteiro Buritis", "Rua Engenheiro Alberto Pontes", "300", "Buritis"),
     ]),
    ("farmacia", TipoCliente.PJ, "Drogaria Pampulha Comércio de Medicamentos LTDA",
     "Drogaria Pampulha", "(31) 3441-7788", None, [
         _end(COM, "Loja", "Av. Otacílio Negrão de Lima", "4100", "Pampulha",
              cep="31365-450", lembrancinha=True),
     ]),
    ("transportes", TipoCliente.PJ, "Rápido Contagem Transportes EIRELI", "Rápido Contagem",
     "(31) 3391-2020", "Portaria fecha às 17h.", [
         _end(COM, "Galpão", "Av. João César de Oliveira", "1800", "Eldorado",
              cidade="Contagem", cep="32310-000"),
     ]),
    ("restaurante", TipoCliente.PJ, "Sabor de Minas Restaurante LTDA", "Restaurante Sabor de Minas",
     "(31) 3287-0909", None, [
         _end(COM, "Restaurante", "Rua Pernambuco", "880", "Funcionários", cep="30130-151",
              lembrancinha=True),
     ]),
    ("ana", TipoCliente.PF, "Ana Paula Ferreira Costa", "Ana", "(31) 99876-5544",
     "Sócia da padaria e da drogaria.", [
         _end(RES, "Casa", "Rua Ouro Preto", "501", "Santo Agostinho", complemento="Apto 802",
              cep="30170-041", lembrancinha=True),
     ]),
    ("joao", TipoCliente.PF, "João Batista da Silva Xavier", "Seu João", "(31) 98888-2020",
     "Sem endereço cadastrado: só por telefone.", []),
    ("marcos", TipoCliente.PF, "Marcos Vinícius Andrade", "Marcos", "(31) 99123-4567", None, [
        _end(RES, "Casa", "Rua Itaú", "145", "Sagrada Família"),
    ]),
    ("lucia", TipoCliente.PF, "Lúcia Helena Rocha", "Dona Lúcia", "(31) 98765-1122",
     "Prefere à tarde.", [
         _end(RES, "Casa", "Rua Contorno", "77", "Centro", cidade="Contagem"),
     ]),
]

SOCIOS = [
    ("padaria", "ana", "Sócia-administradora"),
    ("padaria", "joao", "Sócio"),
    ("farmacia", "ana", "Sócia"),
    ("construtora", "marcos", "Procurador"),
]

# Os clientes com um endereço marcado como "das lembrancinhas" entram na lista
# sozinhos; aqui só se escolhe o presente e a situação do ano.
DESTINATARIOS = [
    # cliente, presente, situação
    ("padaria", "Cesta de Natal", SituacaoLembrancinha.ENTREGUE),
    ("construtora", "Panetone + vinho", SituacaoLembrancinha.A_ENTREGAR),
    ("farmacia", "Agenda 2027", SituacaoLembrancinha.A_ENTREGAR),
    ("restaurante", "Cesta de Natal", SituacaoLembrancinha.NAO_ENVIAR),
    ("ana", "Vinho", SituacaoLembrancinha.A_ENTREGAR),
]


def cadastrar() -> None:
    if ARQUIVO.exists():
        print(f"Os exemplos já estão cadastrados ({ARQUIVO}).")
        print("Rode com --apagar antes, se quiser recriar.")
        return
    init_db()
    hoje = date.today()
    criado: dict[str, list[int]] = {
        "clientes": [], "solicitantes": [], "tipos": [], "lembrancinhas": [],
    }
    with session_scope() as sessao:
        usuario = ru.listar(sessao)[0]
        sessao_app.definir_usuario(
            sessao_app.UsuarioLogado(usuario.id, usuario.nome, usuario.login))

        tipos = {t.nome: t.id for t in rt.garantir_padrao(sessao)}
        if "Entrega de guia" not in tipos:
            tipo = rt.criar(sessao, DadosTipoServico(nome="Entrega de guia", estilo="roxo"))
            tipos[tipo.nome] = tipo.id
            criado["tipos"].append(tipo.id)
        coleta, retirada, guia = tipos["Coleta"], tipos["Retirada"], tipos["Entrega de guia"]

        pedem = []
        for nome, setor in (("Marcela", "Fiscal"), ("Ricardo", "Contábil"),
                            ("Patrícia", "Pessoal")):
            s = rs.criar(sessao, DadosSolicitante(nome=nome, setor=setor))
            pedem.append(s.id)
            criado["solicitantes"].append(s.id)

        c = {}
        for chave, tipo, nome, apelido, fone, obs, ends in CLIENTES:
            cliente = rc.criar_cliente(sessao, DadosCliente(
                tipo=tipo, nome=nome, apelido=apelido, telefone=fone,
                observacao=obs, enderecos=ends))
            c[chave] = cliente
            criado["clientes"].append(cliente.id)

        for empresa, pessoa, papel in SOCIOS:
            rsoc.vincular(sessao, c[empresa].id, c[pessoa].id, papel)

        def servico(chave, tipo, dias, periodo, end=0, quem=0):
            cliente = c[chave]
            return re_.criar_evento(sessao, DadosEvento(
                cliente_id=cliente.id, tipo_servico_id=tipo,
                data=hoje + timedelta(days=dias), periodo=periodo,
                endereco_id=cliente.enderecos[end].id if cliente.enderecos else None,
                solicitante_id=pedem[quem % len(pedem)]))

        # Atrasados: dias que passaram sem ninguém dar baixa.
        servico("construtora", coleta, -1, M, quem=0)
        servico("transportes", guia, -3, T, quem=1)
        servico("lucia", retirada, -6, T, quem=2)
        # Baixados na semana (verdes no calendário).
        for chave, tipo, dias, per, end in (
            ("padaria", coleta, -1, T, 0), ("farmacia", guia, -2, M, 0),
            ("restaurante", retirada, -2, T, 0), ("construtora", guia, -4, M, 1),
            ("ana", retirada, -5, M, 0), ("padaria", guia, -7, T, 1),
        ):
            re_.concluir_evento(sessao, servico(chave, tipo, dias, per, end).id)
        # Não deu e ainda não foi remarcado.
        e = servico("marcos", retirada, -2, M)
        re_.nao_realizado(sessao, e.id, "Ninguém em casa; interfone quebrado.")
        # Não deu e foi remarcado para amanhã.
        e = servico("farmacia", coleta, -1, T, quem=1)
        re_.reagendar(sessao, e.id, hoje + timedelta(days=1), M,
                      motivo="Loja fechada para balanço.")
        # Cancelado.
        re_.cancelar_evento(sessao, servico("restaurante", guia, 1, T, quem=2).id)
        # Hoje: manhã e tarde, um já baixado.
        servico("padaria", coleta, 0, M)
        servico("construtora", guia, 0, M, end=0, quem=1)
        servico("transportes", retirada, 0, T, quem=2)
        servico("lucia", guia, 0, T)
        re_.concluir_evento(sessao, servico("ana", retirada, 0, M).id)
        # Próximos dias e semana que vem.
        for chave, tipo, dias, per, end in (
            ("restaurante", coleta, 1, M, 0), ("padaria", retirada, 2, T, 1),
            ("marcos", guia, 3, M, 0), ("transportes", coleta, 4, T, 0),
            ("construtora", retirada, 7, M, 1), ("farmacia", guia, 9, T, 0),
            ("lucia", coleta, 11, M, 0),
        ):
            servico(chave, tipo, dias, per, end, quem=dias)

        # Serviços automáticos (fixos).
        rr.criar(sessao, DadosRecorrencia(
            cliente_id=c["padaria"].id, tipo_servico_id=coleta,
            frequencia=FrequenciaRecorrencia.SEMANAL, periodo=M,
            endereco_id=c["padaria"].enderecos[0].id, solicitante_id=pedem[0],
            dia_semana=0))  # toda segunda
        rr.criar(sessao, DadosRecorrencia(
            cliente_id=c["construtora"].id, tipo_servico_id=guia,
            frequencia=FrequenciaRecorrencia.MENSAL_DIA, periodo=T,
            endereco_id=c["construtora"].enderecos[0].id, solicitante_id=pedem[1],
            dia_mes=20))
        rr.criar(sessao, DadosRecorrencia(
            cliente_id=c["transportes"].id, tipo_servico_id=retirada,
            frequencia=FrequenciaRecorrencia.MENSAL_ORDINAL, periodo=M,
            endereco_id=c["transportes"].enderecos[0].id, solicitante_id=pedem[2],
            dia_semana=4, ordinal=1))  # 1ª sexta do mês
        gerados = rr.gerar(sessao, a_partir_de=hoje + timedelta(days=1))

        # Lembrancinhas: as que vieram do cadastro, e uma avulsa.
        por_cliente = {d.cliente_id: d for d in rl.listar(sessao) if d.cliente_id}
        for chave, presente, situacao in DESTINATARIOS:
            d = por_cliente[c[chave].id]
            d.presente = maiusculo(presente)
            criado["lembrancinhas"].append(d.id)
            if situacao is not SituacaoLembrancinha.A_ENTREGAR:
                rl.definir_situacao(sessao, d.id, hoje.year, situacao,
                                    hoje - timedelta(days=2)
                                    if situacao is SituacaoLembrancinha.ENTREGUE else None)
        avulso = rl.criar(sessao, DadosDestinatario(
            nome="Dr. Fernando Albuquerque", contato="Dr. Fernando",
            telefone="(31) 99654-3210", logradouro="Rua Gonçalves Dias", numero="1500",
            complemento="Sala 1203", bairro="Lourdes", cidade=BH,
            presente="Vinho", observacao="Advogado parceiro (não é cliente)."))
        criado["lembrancinhas"].append(avulso.id)

    ARQUIVO.write_text(json.dumps(criado, indent=2), encoding="utf-8")
    print(f"Pronto: {len(criado['clientes'])} clientes, {len(SOCIOS)} vínculos de sócio, "
          f"{len(criado['solicitantes'])} solicitantes, {len(gerados)} serviços automáticos "
          f"gerados e {len(criado['lembrancinhas'])} lembrancinhas.")
    print(f"Anotado em {ARQUIVO} (para o --apagar).")


def apagar() -> None:
    if not ARQUIVO.exists():
        print("Não há exemplos anotados para apagar.")
        return
    init_db()
    criado = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    with session_scope() as sessao:
        usuario = ru.listar(sessao)[0]
        sessao_app.definir_usuario(
            sessao_app.UsuarioLogado(usuario.id, usuario.nome, usuario.login))
        for i in criado["lembrancinhas"]:
            if rl.obter(sessao, i):
                rl.excluir(sessao, i)
        # Excluir o cliente leva junto os serviços, os fixos e os vínculos.
        for i in criado["clientes"]:
            if rc.obter_cliente(sessao, i):
                rc.excluir_cliente(sessao, i)
        sessao.flush()
        for i in criado["solicitantes"]:
            if rs.obter(sessao, i):
                rs.excluir(sessao, i)
        for i in criado["tipos"]:
            if rt.obter(sessao, i):
                rt.excluir(sessao, i)
    ARQUIVO.unlink()
    print("Exemplos apagados.")


if __name__ == "__main__":
    print("banco:", url_mascarada())
    apagar() if "--apagar" in sys.argv else cadastrar()
