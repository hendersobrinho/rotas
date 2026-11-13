"""Emissão do PDF da agenda — para imprimir ou para ler no celular."""

from __future__ import annotations

import enum
import subprocess
from urllib.parse import quote_plus
from datetime import date, datetime, timedelta
from pathlib import Path

from PySide6.QtCore import QMarginsF, QPointF, QRectF, QSizeF, Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QPageLayout,
    QPageSize,
    QPainter,
    QPainterPath,
    QPdfWriter,
    QPen,
    QTextDocument,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.db import session_scope
from app.models import Evento, Periodo, StatusEvento
from app.repository import eventos as repo_eventos
from app.schemas import FiltroEventos
from app.ui import marca
from app.ui.datas import (
    Agrupamento,
    DIAS_POR_EXTENSO,
    MESES,
    data_por_extenso,
    inicio_da_semana,
    rotulo_do_periodo,
)
from app import sessao as sessao_app
from app.ui.estilo import CORES as CORES_TELA
from app.ui.estilo import (
    COR_STATUS_CLARO as COR_STATUS,
    CORES_CLARAS as CORES,
    FONTE_DADOS,
    FONTE_TITULO,
    FONTE_UI,
    PALETA_CLARA,
    ROTULO_PERIODO,
    glifo_da_etiqueta,
    marcar,
)
from app.ui.estilo import cores_da_etiqueta as _cores_da_etiqueta
from app.ui.mensagens import mostrar_erro
from app.ui.seletor_data import SeletorDeData
from app.ui.widgets import Segmentado, rotulo

def cores_da_etiqueta(estilo: str | None) -> tuple[str, str]:
    return _cores_da_etiqueta(estilo, PALETA_CLARA)


# Duas páginas possíveis: A4 para imprimir e uma estreita que enche a tela do
# celular sem precisar dar zoom.
FORMATOS = {
    "A4": dict(
        tamanho=QPageSize(QPageSize.PageSizeId.A4),
        deitada=True,          # a folha do computador sai na horizontal
        margem=11.0,
        base=9.5,
        modo="tabela",
        cabecalho=17.0,
        rodape=9.0,
    ),
    "Celular": dict(
        tamanho=QPageSize(QSizeF(95.0, 170.0), QPageSize.Unit.Millimeter),
        deitada=False,
        margem=5.5,
        base=7.0,
        modo="lista",
        cabecalho=14.0,
        rodape=7.5,
    ),
}

# O desenho é feito numa grade de 300 dpi em vez dos 72 dpi de um ponto. Não é
# o texto que muda — ele é vetorial dos dois jeitos —, são os fios: "1px" a
# 72 dpi vira um traço de 0,34 mm, grosso; a 300 dpi vira fio de 0,085 mm.
RESOLUCAO = 300
ESCALA = RESOLUCAO / 72.0


TITULO_PDF = "Rota do motoboy"


def _mm(valor: float) -> float:
    """Milímetros em pontos da grade de 300 dpi."""
    return valor / 25.4 * RESOLUCAO


def _pt(valor: float) -> int:
    """Corpo de letra (em pontos tipográficos) em pixels da grade."""
    return max(1, round(valor / 72.0 * RESOLUCAO))


class FormatoPdf:
    A4 = "A4"
    CELULAR = "Celular"


class Abrangencia(enum.Enum):
    """O que entra no PDF."""

    DIA = "Dia"
    SEMANA = "Semana"


class Formato(enum.Enum):
    A4 = "A4 (imprimir)"
    CELULAR = "Celular"


def _escapar(texto: str) -> str:
    return (
        texto.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )


def _endereco(evento: Evento) -> str:
    if evento.endereco is None:
        return "Endereço não informado"
    return f"{evento.endereco.etiqueta_com_tipo}: {evento.endereco.resumo()}"


def _mapa(evento: Evento) -> str | None:
    """Link que o celular abre no mapa/GPS."""
    endereco = evento.endereco
    if endereco is None:
        return None
    partes = [
        p for p in (
            f"{endereco.logradouro or ''} {endereco.numero or ''}".strip(),
            endereco.bairro,
            endereco.cidade,
            endereco.cep,
        ) if p
    ]
    if not partes:
        return None
    consulta = quote_plus(", ".join(partes))
    # &amp; porque isto entra num documento HTML.
    return f"https://www.google.com/maps/search/?api=1&amp;query={consulta}"


SEM_CIDADE = "Sem cidade informada"
SEM_BAIRRO = "Sem bairro informado"


def _local(evento: Evento) -> tuple[str, str]:
    endereco = evento.endereco
    if endereco is None:
        return SEM_CIDADE, SEM_BAIRRO
    return (
        (endereco.cidade or "").strip() or SEM_CIDADE,
        (endereco.bairro or "").strip() or SEM_BAIRRO,
    )


def agrupar_por_local(
    eventos: list[Evento],
) -> list[tuple[str, list[tuple[str, list[Evento]]]]]:
    """Cidade, e dentro dela o bairro — é assim que a rota se organiza.

    Cidade e bairro saem em ordem alfabética, com os sem endereço no fim.
    Dentro do bairro, manhã antes da tarde e depois pelo nome do cliente.
    """
    cidades: dict[str, dict[str, list[Evento]]] = {}
    for evento in eventos:
        cidade, bairro = _local(evento)
        cidades.setdefault(cidade, {}).setdefault(bairro, []).append(evento)

    def ordem_cidade(nome: str) -> tuple[int, str]:
        return (1 if nome == SEM_CIDADE else 0, nome.casefold())

    def ordem_bairro(nome: str) -> tuple[int, str]:
        return (1 if nome == SEM_BAIRRO else 0, nome.casefold())

    resultado = []
    for cidade in sorted(cidades, key=ordem_cidade):
        bairros = []
        for bairro in sorted(cidades[cidade], key=ordem_bairro):
            lista = sorted(
                cidades[cidade][bairro],
                key=lambda e: (e.periodo.name, e.cliente.nome_exibicao.casefold()),
            )
            bairros.append((bairro, lista))
        resultado.append((cidade, bairros))
    return resultado


def _faixa_cidade(cidade: str, quantos: int, b: float) -> str:
    """Abre o bloco da cidade."""
    return (
        f'<div style="font-size:{b * 0.95:.2f}pt; font-weight:600;'
        f' color:#FFFFFF; background:{CORES["marca"]};'
        f' margin-top:{round(b * 0.9)}px;">'
        f"&nbsp;&nbsp;{_escapar(cidade.upper())}&nbsp;&nbsp;"
        f'<span style="color:{CORES["ciano"]}; font-size:{b * 0.78:.2f}pt;">'
        f"· {quantos} serviço(s)&nbsp;</span></div>"
    )


def _faixa_bairro(bairro: str, quantos: int, b: float) -> str:
    return (
        f'<div style="font-size:{b * 0.8:.2f}pt; font-weight:600;'
        f' color:{CORES["tinta_media"]}; background:{CORES["cinza_claro"]};'
        f' margin-top:{round(b * 0.5)}px;">'
        f"&nbsp;{_escapar(bairro)}&nbsp;"
        f'<span style="color:{CORES["tinta_fraca"]};">· {quantos}&nbsp;</span></div>'
    )


def _marca_periodo(periodo: Periodo, b: float) -> str:
    """O período vira etiqueta dentro do serviço, já que a divisão agora é o lugar."""
    glifo = "☀" if periodo is Periodo.MANHA else "☾"
    fundo = CORES["laranja_claro"] if periodo is Periodo.MANHA else CORES["ciano_claro"]
    cor = CORES["carimbo"] if periodo is Periodo.MANHA else CORES["marca"]
    return _pastilha(f"{glifo} {ROTULO_PERIODO[periodo]}", cor, fundo, b * 0.74)


def _pastilha(texto: str, cor: str, fundo: str, corpo: float) -> str:
    """Etiqueta com fundo — o Qt não arredonda cantos em texto rico, então
    o efeito vem do fundo colorido com respiro nas laterais."""
    return (
        f'<span style="background:{fundo}; color:{cor}; font-size:{corpo:.2f}pt;'
        f' font-weight:600;">&nbsp;{texto}&nbsp;</span>'
    )


def _resumo(
    contagem: dict[str, tuple[str, int]],
    totais: dict[str, int],
    b: float,
    empilhado: bool = False,
) -> str:
    """Abertura da primeira página: os números da rota e os tipos de serviço.

    O logotipo e o título moram no cabeçalho de cada página (ver
    _desenhar_cabecalho); aqui fica só o que ajuda a planejar o dia.
    """
    recheio = round((3 if empilhado else 5) * ESCALA)
    corpo_numero = b * (1.45 if empilhado else 1.9)
    corpo_legenda = b * (0.62 if empilhado else 0.74)

    def bloco(numero: int, legenda: str, cor: str, fundo: str) -> str:
        return (
            f'<td style="background:{fundo};" valign="middle">'
            f'<span style="font-family:\'{FONTE_TITULO}\'; font-size:{corpo_numero:.2f}pt;'
            f' font-weight:700; color:{cor};">{numero}</span>'
            f'<br><span style="font-size:{corpo_legenda:.2f}pt; font-weight:600;'
            f' color:{CORES["tinta_media"]};">{legenda.upper()}</span></td>'
        )

    blocos = [
        bloco(totais["total"], "serviços", CORES["marca"], CORES["papel_suave"]),
        bloco(totais["manha"], "☀ manhã", CORES["carimbo"], CORES["laranja_claro"]),
        bloco(totais["tarde"], "☾ tarde", CORES["marca"], CORES["ciano_claro"]),
    ]
    if totais.get("atrasados"):
        blocos.append(
            bloco(totais["atrasados"],
                  "atrasados" if empilhado else "atrasados sem baixa",
                  CORES["vermelho"], CORES["vermelho_claro"])
        )

    chips = "&nbsp;&nbsp;".join(
        _pastilha(f"{glifo} {nome} · {total}", cor, fundo, b * 0.8)
        for nome, (estilo, total) in contagem.items()
        for cor, fundo in [cores_da_etiqueta(estilo)]
        for glifo in [glifo_da_etiqueta(estilo)]
    )
    espaco = f'<td width="{round(4 * ESCALA)}"></td>'
    # Uma linha só, nas duas folhas: na estreita os blocos dividem a largura.
    numeros = (
        f'<table cellspacing="0" cellpadding="{recheio}"'
        + (' width="100%"' if empilhado else "")
        + "><tr>"
        + espaco.join(blocos)
        + "</tr></table>"
    )
    tipos = (
        f'<div style="margin-top:{round(b * 0.6)}px;">'
        f'<span style="font-size:{b * 0.72:.2f}pt; font-weight:600;'
        f' color:{CORES["tinta_fraca"]};">POR TIPO&nbsp;&nbsp;</span>{chips}</div>'
        if chips else ""
    )
    return numeros + tipos


def _faixa_atrasados(quantos: int, b: float) -> str:
    """Abre a seção do que ficou para trás sem baixa."""
    return (
        f'<div style="margin-top:{round(b * 1.2)}px;">'
        f'<span style="background:{CORES["vermelho"]}; color:#FFFFFF;'
        f' font-size:{b * 1.0:.2f}pt; font-weight:700;">'
        f"&nbsp;&nbsp;! PENDENTES DE DIAS ANTERIORES&nbsp;&nbsp;</span>"
        f'<span style="font-size:{b * 0.8:.2f}pt; color:{CORES["vermelho"]};'
        f' font-weight:600;">&nbsp;&nbsp;{quantos} serviço(s) ainda sem baixa</span>'
        f'</div><div style="font-size:{b * 0.78:.2f}pt; color:{CORES["tinta_media"]};">'
        "Confira se foram feitos; os que estiverem na rota de hoje, faça junto."
        "</div>"
    )


def _titulo_do_dia(dia: date, quantos: int, b: float) -> str:
    """Número do dia em destaque, seguido do nome por extenso.

    Sem tabela de propósito: a coluna estreita de uma tabela do Qt aperta o
    número e quebra "24" em duas linhas. Um trecho com fundo resolve.
    """
    nome_dia = DIAS_POR_EXTENSO[dia.weekday()].split("-")[0]
    return (
        f'<div style="margin-top:{round(b * 1.4)}px;">'
        f'<span style="background:{CORES["marca"]}; color:#FFFFFF;'
        f' font-size:{b * 1.15:.2f}pt; font-weight:600;">'
        f"&nbsp;&nbsp;{dia.day}&nbsp;&nbsp;</span>"
        f'<span style="font-size:{b * 1.05:.2f}pt; font-weight:600;'
        f' color:{CORES["marca"]};">'
        f"&nbsp;&nbsp;{_escapar(nome_dia.capitalize())}, {dia.day} de "
        f"{MESES[dia.month - 1]}</span>"
        f'<span style="font-size:{b * 0.8:.2f}pt; color:{CORES["tinta_fraca"]};">'
        f"&nbsp;&nbsp;· {quantos} serviço(s)</span></div>"
    )


def _desde(evento: Evento, b: float) -> str:
    """Pastilha do atraso: de que dia o serviço é."""
    dias = (date.today() - evento.data).days
    quando = "" if dias <= 0 else " · ontem" if dias == 1 else f" · há {dias} dias"
    return _pastilha(
        f"⏱ {evento.data.strftime('%d/%m')}{quando}",
        CORES["vermelho"], CORES["vermelho_claro"], b * 0.74,
    )


def _bloco_servico(evento: Evento, b: float, fio: str, atrasado: bool = False) -> str:
    """Um serviço: barra na cor do tipo, quem é, onde, como tratar e o combinado."""
    cor, fundo = cores_da_etiqueta(evento.tipo_servico.estilo)
    glifo = glifo_da_etiqueta(evento.tipo_servico.estilo)
    cancelado = evento.status is StatusEvento.CANCELADO
    if cancelado:
        cor, fundo = CORES["tinta_fraca"], CORES["cinza_claro"]
    risco = "text-decoration: line-through;" if cancelado else "text-decoration: none;"
    cliente = evento.cliente

    linhas = [
        f'<div>{_pastilha(f"{glifo} {_escapar(evento.tipo_servico.nome)}", cor, fundo, b * 0.82)}'
        f"&nbsp;{_marca_periodo(evento.periodo, b)}"
        + (f"&nbsp;{_desde(evento, b)}" if atrasado else "")
        + f'<span style="font-size:{b * 1.12:.2f}pt; font-weight:600;'
        f' color:{CORES["tinta"]}; {risco}">'
        f"&nbsp;&nbsp;{_escapar(cliente.nome)}</span></div>"
    ]

    if cliente.apelido and cliente.apelido.strip() != cliente.nome.strip():
        linhas.append(
            f'<div style="font-size:{b * 0.85:.2f}pt; color:{CORES["tinta_media"]};">'
            f"Tratar por <b>{_escapar(cliente.apelido)}</b></div>"
        )
    if evento.contato is not None:
        linhas.append(
            f'<div style="font-size:{b * 0.88:.2f}pt; color:{CORES["tinta"]};">'
            f"A/C <b>{_escapar(evento.contato.descricao)}</b></div>"
        )

    if evento.endereco is not None:
        endereco = _escapar(f"{evento.endereco.etiqueta_com_tipo}: {evento.endereco.resumo()}")
        mapa = _mapa(evento)
        if mapa:
            linhas.append(
                f'<div style="font-size:{b * 0.88:.2f}pt;">'
                f'<a href="{mapa}" style="color:{CORES["azul"]};'
                f' text-decoration: none;">{endereco}</a>'
                f'<span style="color:{CORES["azul"]}; font-size:{b * 0.78:.2f}pt;">'
                "&nbsp;&nbsp;↗ abrir no mapa</span></div>"
            )
        else:
            linhas.append(
                f'<div style="font-size:{b * 0.88:.2f}pt;'
                f' color:{CORES["tinta_media"]};">{endereco}</div>'
            )
    else:
        linhas.append(
            f'<div style="font-size:{b * 0.88:.2f}pt; color:{CORES["tinta_fraca"]};">'
            "Endereço não informado</div>"
        )

    rodape = [evento.status.value]
    if evento.motivo:
        rodape.append(evento.motivo)
    if evento.remarcacao is not None:
        rodape.append(f"remarcado para {evento.remarcacao.data.strftime('%d/%m')}")
    elif evento.origem is not None:
        rodape.append(f"veio do dia {evento.origem.data.strftime('%d/%m')}")
    if evento.solicitante is not None:
        rodape.append(f"Pedido por {evento.solicitante.nome_exibicao}")
    if evento.contato is None and cliente.telefone:
        rodape.append(cliente.telefone)
    linhas.append(
        f'<div style="font-size:{b * 0.82:.2f}pt; color:{CORES["tinta_fraca"]};">'
        f"{_escapar(' · '.join(rodape))}</div>"
    )

    observacoes = [
        texto.strip()
        for texto in (
            cliente.observacao,
            evento.endereco.observacao if evento.endereco is not None else None,
        )
        if texto and texto.strip()
    ]
    for texto in observacoes:
        linhas.append(
            f'<div style="font-size:{b * 0.84:.2f}pt; color:{CORES["tinta"]};'
            f' background:{CORES["papel_suave"]};'
            f' border-left:{max(1, round(ESCALA))}px solid {CORES["pauta_forte"]};">'
            f"&nbsp;Obs.: {_escapar(texto)}&nbsp;</div>"
        )

    largura_barra = max(2, round(2.2 * ESCALA))
    return (
        "<tr>"
        f'<td width="{largura_barra}" style="background:{cor};"></td>'
        f'<td width="{round(24 * ESCALA)}" valign="top"'
        f' style="font-size:{b * 1.3:.2f}pt; color:{CORES["tinta_fraca"]};'
        f' padding-left:{round(6 * ESCALA)}px;">&#9744;</td>'
        f'<td valign="top" style="border-bottom:{fio} solid {CORES["pauta"]};">'
        + "".join(linhas)
        + "</td></tr>"
    )


def _cabecalho_tabela(b: float, fio: str) -> str:
    colunas = (
        ("", "3%"), ("Período", "9%"), ("Serviço", "11%"), ("Cliente", "21%"),
        ("Endereço", "31%"), ("Quem pediu", "12%"), ("Situação", "13%"),
    )
    celulas = "".join(
        f'<td width="{largura}" style="font-size:{b * 0.72:.2f}pt;'
        f' font-weight:600; color:{CORES["tinta_fraca"]};'
        f' border-bottom:{fio} solid {CORES["pauta_forte"]};">{nome.upper()}</td>'
        for nome, largura in colunas
    )
    return f"<tr>{celulas}</tr>"


def _linha_tabela(evento: Evento, b: float, fio: str, atrasado: bool = False) -> str:
    """Um serviço numa linha, para a folha deitada."""
    cor, fundo = cores_da_etiqueta(evento.tipo_servico.estilo)
    glifo = glifo_da_etiqueta(evento.tipo_servico.estilo)
    cancelado = evento.status is StatusEvento.CANCELADO
    if cancelado:
        cor, fundo = CORES["tinta_fraca"], CORES["cinza_claro"]
    risco = "text-decoration: line-through;" if cancelado else "text-decoration: none;"
    cliente = evento.cliente
    borda = f"border-bottom:{fio} solid {CORES['pauta']};"

    tratar = ""
    if cliente.apelido and cliente.apelido.strip() != cliente.nome.strip():
        tratar = (
            f'<div style="font-size:{b * 0.78:.2f}pt;'
            f' color:{CORES["tinta_media"]};">Tratar por '
            f"<b>{_escapar(cliente.apelido)}</b></div>"
        )
    if evento.contato is not None:
        telefone = (
            f'<div style="font-size:{b * 0.78:.2f}pt; color:{CORES["tinta"]};">'
            f"A/C <b>{_escapar(evento.contato.descricao)}</b></div>"
        )
    elif cliente.telefone:
        telefone = (
            f'<div style="font-size:{b * 0.78:.2f}pt; color:{CORES["tinta_fraca"]};">'
            f"{_escapar(cliente.telefone)}</div>"
        )
    else:
        telefone = ""

    if evento.endereco is not None:
        texto_endereco = _escapar(
            f"{evento.endereco.etiqueta_com_tipo}: {evento.endereco.resumo()}"
        )
        mapa = _mapa(evento)
        endereco = (
            f'<a href="{mapa}" style="color:{CORES["azul"]};'
            f' text-decoration:none;">{texto_endereco}</a>'
            f'<span style="color:{CORES["azul"]};'
            f' font-size:{b * 0.72:.2f}pt;">&nbsp;↗ mapa</span>'
            if mapa
            else f'<span style="color:{CORES["tinta_media"]};">{texto_endereco}</span>'
        )
    else:
        endereco = (
            f'<span style="color:{CORES["tinta_fraca"]};">'
            "Endereço não informado</span>"
        )

    observacoes = "".join(
        f'<div style="font-size:{b * 0.76:.2f}pt; color:{CORES["tinta"]};'
        f' background:{CORES["papel_suave"]};">&nbsp;Obs.: {_escapar(t.strip())}'
        "&nbsp;</div>"
        for t in (
            cliente.observacao,
            evento.endereco.observacao if evento.endereco is not None else None,
        )
        if t and t.strip()
    )

    situacao = [_pastilha(_escapar(evento.status.value), *COR_STATUS[evento.status],
                          b * 0.76)]
    if evento.motivo:
        situacao.append(
            f'<div style="font-size:{b * 0.74:.2f}pt;'
            f' color:{CORES["tinta_media"]};">{_escapar(evento.motivo)}</div>'
        )
    if evento.remarcacao is not None:
        situacao.append(
            f'<div style="font-size:{b * 0.74:.2f}pt; color:{CORES["tinta_fraca"]};">'
            f"remarcado p/ {evento.remarcacao.data.strftime('%d/%m')}</div>"
        )
    elif evento.origem is not None:
        situacao.append(
            f'<div style="font-size:{b * 0.74:.2f}pt; color:{CORES["tinta_fraca"]};">'
            f"veio de {evento.origem.data.strftime('%d/%m')}</div>"
        )

    return (
        f'<tr><td valign="top" style="{borda} font-size:{b * 1.1:.2f}pt;'
        f' color:{CORES["tinta_fraca"]};">&#9744;</td>'
        f'<td valign="top" style="{borda}">'
        f"{_marca_periodo(evento.periodo, b)}"
        + (f"<div>{_desde(evento, b)}</div>" if atrasado else "")
        + "</td>"
        f'<td valign="top" style="{borda}">'
        f"{_pastilha(f'{glifo} ' + _escapar(evento.tipo_servico.nome), cor, fundo, b * 0.78)}"
        "</td>"
        f'<td valign="top" style="{borda}">'
        f'<div style="font-size:{b * 0.95:.2f}pt; font-weight:600;'
        f' color:{CORES["tinta"]}; {risco}">{_escapar(cliente.nome)}</div>'
        f"{tratar}{telefone}</td>"
        f'<td valign="top" style="{borda} font-size:{b * 0.82:.2f}pt;">'
        f"{endereco}{observacoes}</td>"
        f'<td valign="top" style="{borda} font-size:{b * 0.8:.2f}pt;'
        f' color:{CORES["tinta_media"]};">'
        + (
            _escapar(evento.solicitante.nome_exibicao)
            if evento.solicitante is not None
            else "—"
        )
        + "</td>"
        f'<td valign="top" style="{borda}">' + "".join(situacao) + "</td></tr>"
    )


def _servicos_por_local(
    eventos: list[Evento], b: float, fio: str, modo: str, atrasado: bool = False
) -> list[str]:
    """Cidade, depois bairro, depois os serviços — a ordem em que a rota anda."""
    partes: list[str] = []
    for cidade, bairros in agrupar_por_local(eventos):
        quantos_na_cidade = sum(len(lista) for _b, lista in bairros)
        partes.append(_faixa_cidade(cidade, quantos_na_cidade, b))
        for indice, (bairro, do_bairro) in enumerate(bairros):
            partes.append(_faixa_bairro(bairro, len(do_bairro), b))
            partes.append(
                f'<table cellspacing="0" cellpadding="{round(6 * ESCALA)}"'
                ' width="100%">'
            )
            # O nome das colunas aparece uma vez por cidade: as larguras são
            # percentuais, então as tabelas dos bairros se alinham.
            if modo == "tabela" and indice == 0:
                partes.append(_cabecalho_tabela(b, fio))
            for evento in do_bairro:
                partes.append(
                    _linha_tabela(evento, b, fio, atrasado)
                    if modo == "tabela"
                    else _bloco_servico(evento, b, fio, atrasado)
                )
            partes.append("</table>")
    return partes


def montar_html(
    titulo: str,
    dias: list[tuple[date, list[Evento]]],
    base: float,
    modo: str = "lista",
    largura: int = 2000,
    atrasados: list[Evento] | None = None,
) -> str:
    """Monta o miolo do documento (cabeçalho e rodapé são desenhados à parte).

    O mesmo HTML serve aos dois formatos, em corpos diferentes. `atrasados`
    são os pendentes de dias anteriores que a pessoa quis levar junto.
    """
    b = base * ESCALA
    fio = f"{max(1, round(ESCALA * 0.35))}px"
    espaco = round(b * 0.9)
    atrasados = list(atrasados or [])

    # Resumo por tipo, para as pastilhas do topo.
    contagem: dict[str, tuple[str, int]] = {}
    totais = {"total": 0, "manha": 0, "tarde": 0, "atrasados": len(atrasados)}
    for _dia, eventos in dias:
        for evento in eventos:
            nome = evento.tipo_servico.nome
            estilo, total = contagem.get(nome, (evento.tipo_servico.estilo, 0))
            contagem[nome] = (estilo, total + 1)
            totais["total"] += 1
            totais["manha" if evento.periodo is Periodo.MANHA else "tarde"] += 1

    partes = [
        "<html><body>",
        f'<div style="font-size:{b * 1.35:.2f}pt; font-weight:700;'
        f' color:{CORES["tinta"]};">{_escapar(titulo)}</div>',
        f'<div style="margin-top:{round(b * 0.5)}px;"></div>',
        _resumo(contagem, totais, b, empilhado=modo != "tabela"),
    ]

    if atrasados:
        partes.append(_faixa_atrasados(len(atrasados), b))
        partes.extend(_servicos_por_local(atrasados, b, fio, modo, atrasado=True))

    um_dia_so = len(dias) == 1
    for dia, eventos in dias:
        if not eventos:
            # Dia vazio não merece um bloco inteiro: uma linha basta.
            if not um_dia_so:
                nome_dia = DIAS_POR_EXTENSO[dia.weekday()].split("-")[0]
                partes.append(
                    f'<div style="font-size:{b * 0.85:.2f}pt;'
                    f' color:{CORES["tinta_fraca"]};'
                    f' margin-top:{round(espaco * 0.5)}px;">'
                    f"{dia.day:02d}/{dia.month:02d} · {nome_dia.capitalize()}"
                    " — sem serviços</div>"
                )
            else:
                partes.append(
                    f'<div style="font-size:{b * 0.9:.2f}pt;'
                    f' color:{CORES["tinta_fraca"]};'
                    f' background:{CORES["papel_suave"]};'
                    f' margin-top:{round(espaco * 0.8)}px;">'
                    "&nbsp;Nenhum serviço marcado.&nbsp;</div>"
                )
            continue

        if not um_dia_so or atrasados:
            partes.append(_titulo_do_dia(dia, len(eventos), b))
        partes.extend(_servicos_por_local(eventos, b, fio, modo))

    total = totais["total"] + totais["atrasados"]
    partes.append(
        f'<div style="margin-top:{espaco}px; border-top:{fio} solid'
        f' {CORES["pauta_forte"]};"></div>'
        f'<div style="font-size:{b * 0.78:.2f}pt; color:{CORES["tinta_fraca"]};">'
        f"Fim da rota · {total} serviço(s)</div>"
        "</body></html>"
    )
    return "".join(partes)


def _fonte(familia: str, corpo: float, peso: QFont.Weight) -> QFont:
    fonte = QFont(familia)
    fonte.setPixelSize(_pt(corpo))
    fonte.setWeight(peso)
    return fonte


def _desenhar_cabecalho(
    pintor: QPainter, largura: float, altura: float, titulo: str,
    resumo: str, estreito: bool,
) -> None:
    """Topo de cada página: logotipo, título, o período e a faixa da marca."""
    faixa = _mm(1.1)
    meio = (altura - faixa) / 2

    # Logotipo à esquerda, na altura certa para a folha.
    altura_logo = _mm(6.2 if estreito else 8.0)
    logo = marca.imagem(round(altura_logo))
    pintor.drawImage(
        QRectF(0, meio - altura_logo / 2,
               altura_logo * logo.width() / max(1, logo.height()), altura_logo),
        logo,
    )
    x = altura_logo * logo.width() / max(1, logo.height()) + _mm(4)

    # Fio vertical separando a marca do título.
    pintor.setPen(QPen(QColor(CORES["pauta_forte"]), _mm(0.25)))
    pintor.drawLine(QPointF(x, meio - _mm(3.6)), QPointF(x, meio + _mm(3.6)))
    x += _mm(4)

    direita = largura
    if not estreito:
        # À direita: quando foi emitido, num selo discreto.
        emitido = datetime.now().strftime("%d/%m/%Y · %H:%M")
        pintor.setFont(_fonte(FONTE_DADOS, 6.5, QFont.Weight.DemiBold))
        pintor.setPen(QColor(CORES["tinta_fraca"]))
        pintor.drawText(
            QRectF(0, meio - _mm(4.4), largura, _mm(4)),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            f"EMITIDO {emitido}",
        )
        pintor.setFont(_fonte(FONTE_TITULO, 10, QFont.Weight.Bold))
        pintor.setPen(QColor(CORES["marca"]))
        pintor.drawText(
            QRectF(0, meio - _mm(0.2), largura, _mm(5)),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            resumo,
        )
        direita = largura - _mm(70)

    pintor.setFont(_fonte(FONTE_TITULO, 9.5 if estreito else 12.5, QFont.Weight.Bold))
    pintor.setPen(QColor(CORES["marca"]))
    pintor.drawText(
        QRectF(x, meio - _mm(4.6 if not estreito else 3.8), direita - x, _mm(5)),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        TITULO_PDF,
    )
    pintor.setFont(_fonte(FONTE_UI, 6.6 if estreito else 8.5, QFont.Weight.Medium))
    pintor.setPen(QColor(CORES["tinta_media"]))
    subtitulo = pintor.fontMetrics().elidedText(
        titulo, Qt.TextElideMode.ElideRight, round(direita - x)
    )
    pintor.drawText(
        QRectF(x, meio + _mm(0.3), direita - x, _mm(4.4)),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        subtitulo,
    )

    # A faixa tricolor fecha o cabeçalho, de ponta a ponta.
    total = sum(marca.PROPORCOES_FAIXA)
    x_faixa = 0.0
    for cor, peso in zip(marca.CORES_FAIXA, marca.PROPORCOES_FAIXA):
        pedaco = largura * peso / total
        pintor.fillRect(QRectF(x_faixa, altura - faixa, pedaco + 1, faixa), QColor(cor))
        x_faixa += pedaco


def _desenhar_rodape(
    pintor: QPainter, topo: float, largura: float, altura: float,
    pagina: int, paginas: int, estreito: bool,
) -> None:
    """Pé de cada página: quem emitiu, quando, e a numeração."""
    pintor.setPen(QPen(QColor(CORES["pauta_forte"]), _mm(0.2)))
    pintor.drawLine(QPointF(0, topo + _mm(1.2)), QPointF(largura, topo + _mm(1.2)))

    linha = QRectF(0, topo + _mm(1.8), largura, altura - _mm(1.8))
    simbolo = marca.imagem(round(_mm(3.4)), simbolo=True)
    lado = _mm(3.4)
    pintor.drawImage(
        QRectF(0, linha.center().y() - lado / 2,
               lado * simbolo.width() / max(1, simbolo.height()), lado),
        simbolo,
    )

    # A numeração numa pastilha marinho, à direita.
    texto_pagina = f"{pagina} / {paginas}"
    pintor.setFont(_fonte(FONTE_DADOS, 6.2 if estreito else 7, QFont.Weight.Bold))
    medida = pintor.fontMetrics().horizontalAdvance(texto_pagina)
    pastilha = QRectF(
        largura - medida - _mm(5), linha.center().y() - _mm(2.1),
        medida + _mm(5), _mm(4.2),
    )
    caminho = QPainterPath()
    caminho.addRoundedRect(pastilha, _mm(2.1), _mm(2.1))
    pintor.fillPath(caminho, QColor(CORES["marca"]))
    pintor.setPen(QColor("#FFFFFF"))
    pintor.drawText(pastilha, Qt.AlignmentFlag.AlignCenter, texto_pagina)
    if not estreito:
        pintor.setFont(_fonte(FONTE_UI, 6.8, QFont.Weight.DemiBold))
        pintor.setPen(QColor(CORES["tinta_fraca"]))
        pintor.drawText(
            QRectF(0, linha.top(), pastilha.left() - _mm(3), linha.height()),
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
            "PÁGINA",
        )

    quem = sessao_app.usuario_atual()
    emitido = datetime.now().strftime("%d/%m/%Y às %H:%M")
    texto = (
        f"Rotas · emitido em {emitido}"
        + (f" por {quem.nome}" if quem is not None and not estreito else "")
    )
    pintor.setFont(_fonte(FONTE_UI, 6.0 if estreito else 6.8, QFont.Weight.Medium))
    pintor.setPen(QColor(CORES["tinta_media"]))
    pintor.drawText(
        QRectF(lado + _mm(2.2), linha.top(), largura / 1.6, linha.height()),
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
        texto,
    )


def gerar_pdf(
    caminho: str | Path,
    titulo: str,
    dias,
    formato: str,
    atrasados: list[Evento] | None = None,
) -> Path:
    """Desenha o PDF página a página: cabeçalho, miolo e rodapé.

    O miolo é um QTextDocument paginado na altura que sobra entre o
    cabeçalho e o rodapé; cada página recebe a sua fatia dele. Tudo é
    vetorial, numa grade de 300 dpi (ver ESCALA): o texto não rasteriza, e os
    fios ficam finos de verdade.
    """
    ajustes = FORMATOS[formato]
    destino = Path(caminho)
    estreito = ajustes["modo"] != "tabela"

    escritor = QPdfWriter(str(destino))
    escritor.setPageSize(ajustes["tamanho"])
    escritor.setPageOrientation(
        QPageLayout.Orientation.Landscape
        if ajustes["deitada"]
        else QPageLayout.Orientation.Portrait
    )
    escritor.setPageMargins(
        QMarginsF(*([ajustes["margem"]] * 4)), QPageLayout.Unit.Millimeter
    )
    escritor.setResolution(RESOLUCAO)
    escritor.setTitle(f"{TITULO_PDF} · {titulo}")
    escritor.setCreator("Rotas")

    largura = escritor.width()
    altura = escritor.height()
    alto_cabecalho = _mm(ajustes["cabecalho"])
    alto_rodape = _mm(ajustes["rodape"])
    folga = _mm(2.5)
    alto_miolo = altura - alto_cabecalho - alto_rodape - 2 * folga

    documento = QTextDocument()
    documento.setDefaultFont(QFont(FONTE_UI, round(ajustes["base"] * ESCALA)))
    documento.setDocumentMargin(0)
    documento.setHtml(
        montar_html(titulo, dias, ajustes["base"], ajustes["modo"], largura, atrasados)
    )
    documento.setPageSize(QSizeF(largura, alto_miolo))
    paginas = max(1, documento.pageCount())

    total = sum(len(eventos) for _dia, eventos in dias) + len(atrasados or [])
    resumo = f"{total} serviço(s)"

    pintor = QPainter(escritor)
    pintor.setRenderHint(QPainter.RenderHint.Antialiasing)
    pintor.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    try:
        for indice in range(paginas):
            if indice:
                escritor.newPage()
            _desenhar_cabecalho(pintor, largura, alto_cabecalho, titulo, resumo, estreito)
            pintor.save()
            pintor.translate(0, alto_cabecalho + folga - indice * alto_miolo)
            documento.drawContents(
                pintor, QRectF(0, indice * alto_miolo, largura, alto_miolo)
            )
            pintor.restore()
            _desenhar_rodape(
                pintor, altura - alto_rodape, largura, alto_rodape,
                indice + 1, paginas, estreito,
            )
    finally:
        pintor.end()
    return destino


def carregar_dias(inicio: date, fim: date) -> list[tuple[date, list[Evento]]]:
    with session_scope() as sessao:
        eventos = repo_eventos.listar_eventos(
            sessao, FiltroEventos(data_inicio=inicio, data_fim=fim)
        )
    por_dia: dict[date, list[Evento]] = {}
    for evento in eventos:
        por_dia.setdefault(evento.data, []).append(evento)
    for lista in por_dia.values():
        lista.sort(key=lambda e: (e.periodo.name, e.cliente.nome_exibicao))

    dias = []
    dia = inicio
    while dia <= fim:
        dias.append((dia, por_dia.get(dia, [])))
        dia += timedelta(days=1)
    return dias


def carregar_atrasados(antes_de: date) -> list[Evento]:
    """Pendentes de dias anteriores a `antes_de`: o que ficou sem baixa."""
    with session_scope() as sessao:
        eventos = repo_eventos.listar_sem_baixa(sessao, antes_de - timedelta(days=1))
    return [e for e in eventos if e.data < antes_de]


class RelatorioDialog(QDialog):
    """Escolhe o que sai na rota, em qual formato, e se leva os atrasados."""

    def __init__(
        self,
        parent: QWidget | None,
        dia: date | None = None,
        atalho_baixas: bool = True,
    ) -> None:
        super().__init__(parent)
        self._dia = dia or date.today()
        self.caminho: Path | None = None
        # A pessoa pediu para ir conferir as baixas em vez de emitir.
        self.ver_baixas = False
        self._atalho_baixas = atalho_baixas
        self._atrasados: list[Evento] = []

        self.setWindowTitle("Emitir rota")
        self.setMinimumWidth(460)
        self.setStyleSheet(f"QDialog {{ background: {CORES_TELA['papel']}; }}")

        self.campo_abrangencia = Segmentado(Abrangencia)
        self.campo_abrangencia.definir_valor(Abrangencia.DIA)
        self.campo_abrangencia.mudou.connect(self._trocar_abrangencia)
        self.campo_formato = Segmentado(Formato)
        self.campo_formato.definir_valor(Formato.A4)

        self.calendario = SeletorDeData(self)
        self.calendario.definir_data(self._dia)
        self.calendario.escolhida.connect(lambda _d: self._atualizar_resumo())

        self.resumo = rotulo("", "secao")

        self.incluir_atrasados = QCheckBox()
        self.incluir_atrasados.setChecked(True)  # quem manda a rota quase sempre quer
        self.incluir_atrasados.toggled.connect(lambda _v: self._atualizar_resumo())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(26, 24, 26, 22)
        layout.setSpacing(10)
        layout.addWidget(rotulo("Emitir rota", "titulo"))
        layout.addWidget(
            rotulo(
                "O PDF que vai para a rua: cliente, endereço com link do mapa,"
                " tipo e período.",
                "fraco",
            )
        )
        layout.addSpacing(8)
        linha_abrangencia = QHBoxLayout()
        linha_abrangencia.addWidget(rotulo("O que sai", "campo"))
        linha_abrangencia.addSpacing(8)
        linha_abrangencia.addWidget(self.campo_abrangencia)
        linha_abrangencia.addStretch(1)
        layout.addLayout(linha_abrangencia)
        layout.addSpacing(4)

        layout.addWidget(self.calendario)
        layout.addWidget(self.resumo)

        self.tarja = self._tarja_atrasados()
        layout.addSpacing(4)
        layout.addWidget(self.tarja)
        layout.addSpacing(8)

        linha_formato = QHBoxLayout()
        linha_formato.addWidget(rotulo("Formato da página", "campo"))
        linha_formato.addSpacing(8)
        linha_formato.addWidget(self.campo_formato)
        linha_formato.addStretch(1)
        layout.addLayout(linha_formato)
        layout.addWidget(
            rotulo("A4 imprime; Celular é estreito e lê sem zoom.", "fraco")
        )
        layout.addSpacing(10)

        salvar = QPushButton("Salvar PDF")
        marcar(salvar, variante="primario")
        salvar.setDefault(True)
        salvar.clicked.connect(self._salvar)
        fechar = QPushButton("Cancelar")
        fechar.clicked.connect(self.reject)
        rodape = QHBoxLayout()
        rodape.addStretch(1)
        rodape.addWidget(fechar)
        rodape.addWidget(salvar)
        layout.addLayout(rodape)

        self._atualizar_resumo()

    def _tarja_atrasados(self) -> QFrame:
        """O que ficou para trás sem baixa, com a opção de levar junto na rota."""
        tarja = QFrame()
        tarja.setObjectName("tarjaBaixa")
        tarja.setStyleSheet(
            f"QFrame#tarjaBaixa {{ background: {CORES_TELA['laranja_claro']};"
            f" border: 1px solid {CORES_TELA['alerta_borda']}; border-radius: 12px; }}"
            "QFrame#tarjaBaixa QLabel, QFrame#tarjaBaixa QCheckBox"
            " { background: transparent; }"
        )
        self.texto_tarja = QLabel()
        self.texto_tarja.setWordWrap(True)
        self.texto_tarja.setStyleSheet(f"color: {CORES_TELA['tinta']};")
        self.incluir_atrasados.setStyleSheet(
            f"color: {CORES_TELA['tinta']}; font-weight: 700;"
        )

        coluna = QVBoxLayout()
        coluna.setSpacing(6)
        coluna.addWidget(self.texto_tarja)
        coluna.addWidget(self.incluir_atrasados)

        linha = QHBoxLayout(tarja)
        linha.setContentsMargins(14, 12, 12, 12)
        linha.setSpacing(10)
        linha.addLayout(coluna, 1)
        if self._atalho_baixas:
            ver = QPushButton("Ver baixas")
            marcar(ver, variante="alerta")
            ver.clicked.connect(self._ir_para_baixas)
            linha.addWidget(ver, 0, Qt.AlignmentFlag.AlignTop)
        return tarja

    def _ir_para_baixas(self) -> None:
        self.ver_baixas = True
        self.reject()

    def _trocar_abrangencia(self, valor: Abrangencia) -> None:
        self.calendario.definir_por_semana(valor is Abrangencia.SEMANA)
        self._atualizar_resumo()

    def _intervalo(self) -> tuple[date, date, str]:
        escolhida = self.calendario.data()
        if self.campo_abrangencia.valor() is Abrangencia.SEMANA:
            inicio = inicio_da_semana(escolhida)
            fim = inicio + timedelta(days=6)
            return inicio, fim, rotulo_do_periodo(inicio, Agrupamento.SEMANA)
        return escolhida, escolhida, data_por_extenso(escolhida).capitalize()

    def _atualizar_resumo(self) -> None:
        inicio, _fim, titulo = self._intervalo()
        self.resumo.setText(titulo)
        # Atrasados são os de antes do primeiro dia da rota escolhida.
        try:
            self._atrasados = carregar_atrasados(inicio)
        except Exception:
            self._atrasados = []
        quantos = len(self._atrasados)
        # A tarja fica sempre à vista: sem atrasados, ela diz que não há o que
        # incluir — assim ninguém fica procurando a opção.
        self.incluir_atrasados.setVisible(bool(quantos))
        if not quantos:
            self.texto_tarja.setText(
                f'<span style="color:{CORES_TELA["verde"]};">✓</span>&nbsp; '
                "Nenhum serviço de dias anteriores sem baixa — a rota sai só com"
                " o período escolhido."
            )
            return
        antigo = min(e.data for e in self._atrasados)
        self.texto_tarja.setText(
            f'<span style="color:{CORES_TELA["carimbo"]};">●</span>&nbsp; '
            f"<b>{quantos}</b> serviço(s) de dias anteriores ainda sem baixa"
            f" (o mais antigo de {antigo.strftime('%d/%m')})."
        )
        marcado = self.incluir_atrasados.isChecked()
        self.incluir_atrasados.blockSignals(True)
        self.incluir_atrasados.setText(
            f"Incluir os {quantos} atrasados na rota"
            if quantos > 1 else "Incluir o atrasado na rota"
        )
        self.incluir_atrasados.setChecked(marcado)
        self.incluir_atrasados.blockSignals(False)

    def _sugestao(self, inicio: date, fim: date) -> str:
        if inicio == fim:
            nome = f"rota-{inicio.strftime('%Y-%m-%d')}"
        else:
            nome = f"rota-{inicio.strftime('%Y-%m-%d')}-a-{fim.strftime('%Y-%m-%d')}"
        return str(Path.home() / f"{nome}.pdf")

    def atrasados_escolhidos(self) -> list[Evento]:
        if self.incluir_atrasados.isHidden() or not self.incluir_atrasados.isChecked():
            return []
        return list(self._atrasados)

    def _salvar(self) -> None:
        inicio, fim, titulo = self._intervalo()
        caminho, _ = QFileDialog.getSaveFileName(
            self, "Salvar PDF", self._sugestao(inicio, fim), "PDF (*.pdf)"
        )
        if not caminho:
            return
        if not caminho.lower().endswith(".pdf"):
            caminho += ".pdf"
        try:
            dias = carregar_dias(inicio, fim)
            formato = (
                FormatoPdf.A4
                if self.campo_formato.valor() is Formato.A4
                else FormatoPdf.CELULAR
            )
            self.caminho = gerar_pdf(
                caminho, titulo, dias, formato, self.atrasados_escolhidos()
            )
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para gerar o PDF")
            return
        _abrir_no_sistema(self.caminho)
        self.accept()


def _abrir_no_sistema(caminho: Path) -> None:
    """Abre o PDF no leitor padrão; se não der, o arquivo continua salvo."""
    import os
    import sys

    try:
        if sys.platform.startswith("win"):
            os.startfile(str(caminho))  # type: ignore[attr-defined]
            return
        subprocess.Popen(
            ["xdg-open", str(caminho)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass
