"""Apoio das verificações: banco descartável e dados de exemplo.

As verificações rodam contra um PostgreSQL de teste, nunca contra o banco de
trabalho. Crie o banco antes:

    createdb rotas_teste
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

def _url_de_teste() -> str:
    """Mesma conexão do .env, mas apontando para o banco de teste."""
    from dotenv import load_dotenv

    load_dotenv(RAIZ / ".env")
    from app.db import database_url

    banco = os.environ.get("ROTAS_BANCO_TESTE", "rotas_teste")
    url = database_url()
    return url.rsplit("/", 1)[0] + "/" + banco


def preparar_ambiente(pasta_dados: Path | None = None) -> None:
    """Aponta o app para o banco de teste e para uma pasta de dados própria."""
    url = os.environ.get("ROTAS_URL_TESTE") or _url_de_teste()
    os.environ["ROTAS_DATABASE_URL"] = url
    os.environ.setdefault(
        "ROTAS_DIR_DADOS", str(pasta_dados or (RAIZ / "testes" / ".dados"))
    )
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def semear(com_eventos: bool = True) -> dict:
    """Cria usuário, tipos, solicitantes, clientes e uma agenda de exemplo."""
    from app import sessao as sessao_app
    from app.db import init_db, session_scope
    from app.models import Periodo, StatusEvento, TipoCliente, TipoEndereco
    from app.repository import clientes as rc
    from app.repository import eventos as re_
    from app.repository import solicitantes as rs
    from app.repository import tipos_servico as rt
    from app.repository import usuarios as ru
    from app.schemas import (
        DadosCliente,
        DadosEndereco,
        DadosEvento,
        DadosSolicitante,
        DadosUsuario,
    )

    init_db()
    hoje = date.today()
    dados: dict = {"hoje": hoje}

    with session_scope() as sessao:
        if not ru.existe_algum(sessao):
            usuario = ru.criar(
                sessao,
                DadosUsuario(nome="Henderson Pereira", login="henderson", senha="1234"),
                anotar=False,
            )
        else:
            usuario = ru.listar(sessao)[0]
        sessao_app.definir_usuario(
            sessao_app.UsuarioLogado(usuario.id, usuario.nome, usuario.login)
        )

        tipos = {t.nome: t.id for t in rt.garantir_padrao(sessao)}
        if "Entrega de guia" not in tipos:
            tipos["Entrega de guia"] = rt.criar(
                sessao,
                __import__("app.schemas", fromlist=["DadosTipoServico"]).DadosTipoServico(
                    nome="Entrega de guia", estilo="roxo"
                ),
            ).id
        dados["tipos"] = tipos

        if not rs.listar(sessao):
            for nome, setor in (("Marcela", "Fiscal"), ("Ricardo", "Contábil")):
                rs.criar(sessao, DadosSolicitante(nome=nome, setor=setor))
        pessoas = [p.id for p in rs.listar(sessao)]
        dados["solicitantes"] = pessoas

        if not rc.listar_clientes(sessao):
            rc.criar_cliente(sessao, DadosCliente(
                tipo=TipoCliente.PJ, nome="Panificadora Estrela do Oriente LTDA",
                apelido="Padaria da Ana", telefone="(31) 3222-1010",
                observacao="Falar com a Ana; o gerente não assina nada.",
                enderecos=[DadosEndereco(
                    TipoEndereco.COMERCIAL, logradouro="Av. Brasil", numero="1200",
                    complemento="Loja 3", bairro="Savassi", cidade="Belo Horizonte",
                    cep="30140-002",
                    observacao="Entrada pela lateral depois das 18h.")]))
            # Fica sem endereço de propósito: é com ele que se verifica a
            # regra de que serviço sem endereço não entra.
            rc.criar_cliente(sessao, DadosCliente(
                tipo=TipoCliente.PF, nome="João Batista da Silva Xavier",
                apelido="Seu João", telefone="(31) 98888-2020"))
            # Tem endereço, mas sem cidade nem bairro: cai no bloco "sem
            # cidade informada" dos relatórios.
            rc.criar_cliente(sessao, DadosCliente(
                tipo=TipoCliente.PJ, nome="Oficina Irmãos Souza LTDA",
                apelido="Oficina do Souza", telefone="(31) 3666-1212",
                enderecos=[DadosEndereco(
                    TipoEndereco.COMERCIAL, logradouro="Rodovia MG-10",
                    numero="km 12")]))
            rc.criar_cliente(sessao, DadosCliente(
                tipo=TipoCliente.PJ, nome="Transportes Aurora ME",
                apelido="Transportes Aurora ME", telefone="(31) 3444-7788",
                enderecos=[DadosEndereco(
                    TipoEndereco.COMERCIAL, logradouro="Rua Sapucaí", numero="88",
                    bairro="Floresta", cidade="Belo Horizonte", cep="30150-904")]))
        clientes = rc.listar_clientes(sessao)
        dados["clientes"] = clientes

        if com_eventos and not re_.listar_eventos(sessao):
            # Só clientes com endereço entram na agenda: serviço sem endereço
            # não é aceito pelo repositório.
            atendiveis = [c for c in clientes if c.enderecos]
            agenda = [
                (0, 0, "Coleta", Periodo.MANHA, StatusEvento.PENDENTE),
                (0, 1, "Entrega de guia", Periodo.MANHA, StatusEvento.CONCLUIDO),
                (0, 2, "Retirada", Periodo.TARDE, StatusEvento.CANCELADO),
                (1, 1, "Coleta", Periodo.MANHA, StatusEvento.PENDENTE),
                (2, 0, "Retirada", Periodo.TARDE, StatusEvento.PENDENTE),
                (-2, 2, "Coleta", Periodo.MANHA, StatusEvento.NAO_REALIZADO),
            ]
            for i, (delta, indice, tipo, periodo, status) in enumerate(agenda):
                cliente = atendiveis[indice % len(atendiveis)]
                re_.criar_evento(sessao, DadosEvento(
                    cliente_id=cliente.id, tipo_servico_id=tipos[tipo],
                    data=hoje + timedelta(days=delta), periodo=periodo,
                    endereco_id=cliente.enderecos[0].id,
                    solicitante_id=pessoas[i % len(pessoas)],
                    status=status,
                    motivo="Estabelecimento fechado"
                    if status is StatusEvento.NAO_REALIZADO else None))
    return dados
