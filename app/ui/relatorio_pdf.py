"""Emissão do PDF da agenda — para imprimir ou para ler no celular."""

from __future__ import annotations

import enum
import subprocess
from urllib.parse import quote_plus
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import QMarginsF, QSizeF, QUrl
from PySide6.QtGui import QFont, QPageLayout, QPageSize, QPdfWriter, QTextDocument
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
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
from app.ui.estilo import (
    COR_STATUS,
    CORES,
    ROTULO_PERIODO,
    cores_da_etiqueta,
    glifo_da_etiqueta,
    marcar,
)
from app.ui.mensagens import mostrar_erro
from app.ui.seletor_data import SeletorDeData
from app.ui.widgets import Segmentado, rotulo

# Duas páginas possíveis: A4 para imprimir e uma estreita que enche a tela do
# celular sem precisar dar zoom.
FORMATOS = {
    "A4": dict(
        tamanho=QPageSize(QPageSize.PageSizeId.A4),
        deitada=True,          # a folha do computador sai na horizontal
        margem=12.0,
        base=9.5,
        modo="tabela",
    ),
    "Celular": dict(
        tamanho=QPageSize(QSizeF(95.0, 170.0), QPageSize.Unit.Millimeter),
        deitada=False,
        margem=6.5,
        base=7.0,
        modo="lista",
    ),
}

# O desenho é feito numa grade de 300 dpi em vez dos 72 dpi de um ponto. Não é
# o texto que muda — ele é vetorial dos dois jeitos —, são os fios: "1px" a
# 72 dpi vira um traço de 0,34 mm, grosso; a 300 dpi vira fio de 0,085 mm.
URL_LOGO = "marca-rotas"
URL_FIO = "fio-marca"
RESOLUCAO = 300
ESCALA = RESOLUCAO / 72.0


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
    return f"{evento.endereco.tipo.value}: {evento.endereco.resumo()}"


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


def _pastilha(texto: str, cor: str, fundo: str, corpo: float) -> str:
    """Etiqueta com fundo — o Qt não arredonda cantos em texto rico, então
    o efeito vem do fundo colorido com respiro nas laterais."""
    return (
        f'<span style="background:{fundo}; color:{cor}; font-size:{corpo:.2f}pt;'
        f' font-weight:600;">&nbsp;{texto}&nbsp;</span>'
    )


def _cabecalho(
    titulo: str,
    contagem: dict[str, tuple[str, int]],
    b: float,
    largura: int,
    empilhado: bool = False,
) -> str:
    """Faixa de abertura: logotipo, período e o resumo por tipo de serviço.

    Na folha estreita tudo vai empilhado — lado a lado, o título quebraria em
    três linhas e as pastilhas ficariam picadas.
    """
    chips = "&nbsp;&nbsp;".join(
        _pastilha(f"{glifo} {nome} {total}", cor, fundo, b * 0.8)
        for nome, (estilo, total) in contagem.items()
        for cor, fundo in [cores_da_etiqueta(estilo)]
        for glifo in [glifo_da_etiqueta(estilo)]
    )
    altura_logo = round(b * (2.0 if empilhado else 2.4))
    largura_logo = round(altura_logo * 273 / 110)
    fio = max(2, round(ESCALA * 1.2))
    recheio = round((5 if empilhado else 7) * ESCALA)
    logotipo = f'<img src="{URL_LOGO}" width="{largura_logo}" height="{altura_logo}">'
    texto = (
        f'<div style="font-size:{b * 1.25:.2f}pt; font-weight:600;'
        f' color:{CORES["marca"]};">Agenda do motoboy</div>'
        f'<div style="font-size:{b * 0.95:.2f}pt; color:{CORES["tinta_media"]};">'
        f"{_escapar(titulo)}</div>"
    )

    if empilhado:
        corpo = (
            f'<tr><td style="background:{CORES["marca_clara"]};">'
            f'<div style="margin-bottom:{round(b * 0.4)}px;">{logotipo}</div>'
            f"{texto}"
            + (f'<div style="margin-top:{round(b * 0.45)}px;">{chips}</div>'
               if chips else "")
            + "</td></tr>"
        )
    else:
        corpo = (
            f'<tr><td width="1%" valign="middle"'
            f' style="background:{CORES["marca_clara"]};">{logotipo}</td>'
            f'<td valign="middle" style="background:{CORES["marca_clara"]};'
            f' padding-left:{round(10 * ESCALA)}px;">{texto}</td>'
            f'<td align="right" valign="middle"'
            f' style="background:{CORES["marca_clara"]};">{chips}</td></tr>'
        )

    return (
        f'<table width="100%" cellspacing="0" cellpadding="{recheio}">'
        + corpo
        + "</table>"
        # O fio tricolor vai como imagem: tabela aninhada não estica até a
        # borda no texto rico do Qt.
        f'<img src="{URL_FIO}" width="{largura}" height="{fio}">'
    )


def _titulo_do_dia(dia: date, quantos: int, b: float) -> str:
    """Número do dia em destaque, seguido do nome por extenso.

    Sem tabela de propósito: a coluna estreita de uma tabela do Qt aperta o
    número e quebra "24" em duas linhas. Um trecho com fundo resolve.
    """
    nome_dia = DIAS_POR_EXTENSO[dia.weekday()].split("-")[0]
    return (
        f'<div style="margin-top:{round(b * 1.2)}px;">'
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


def _faixa_periodo(periodo: Periodo, b: float) -> str:
    glifo = "☀" if periodo is Periodo.MANHA else "☾"
    fundo = CORES["laranja_claro"] if periodo is Periodo.MANHA else CORES["ciano_claro"]
    cor = CORES["carimbo"] if periodo is Periodo.MANHA else CORES["marca"]
    return (
        f'<div style="font-size:{b * 0.78:.2f}pt; font-weight:600;'
        f' color:{cor}; background:{fundo};'
        f' margin-top:{round(b * 0.7)}px;">'
        f"&nbsp;{glifo}&nbsp; {ROTULO_PERIODO[periodo]}&nbsp;</div>"
    )


def _bloco_servico(evento: Evento, b: float, fio: str) -> str:
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
        f'<span style="font-size:{b * 1.12:.2f}pt; font-weight:600;'
        f' color:{CORES["tinta"]}; {risco}">'
        f"&nbsp;&nbsp;{_escapar(cliente.nome)}</span></div>"
    ]

    if cliente.apelido and cliente.apelido.strip() != cliente.nome.strip():
        linhas.append(
            f'<div style="font-size:{b * 0.85:.2f}pt; color:{CORES["tinta_media"]};">'
            f"Tratar por <b>{_escapar(cliente.apelido)}</b></div>"
        )

    if evento.endereco is not None:
        endereco = _escapar(f"{evento.endereco.tipo.value}: {evento.endereco.resumo()}")
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
    if cliente.telefone:
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
        ("", "3%"), ("Serviço", "11%"), ("Cliente", "24%"),
        ("Endereço", "34%"), ("Quem pediu", "14%"), ("Situação", "14%"),
    )
    celulas = "".join(
        f'<td width="{largura}" style="font-size:{b * 0.72:.2f}pt;'
        f' font-weight:600; color:{CORES["tinta_fraca"]};'
        f' border-bottom:{fio} solid {CORES["pauta_forte"]};">{nome.upper()}</td>'
        for nome, largura in colunas
    )
    return f"<tr>{celulas}</tr>"


def _linha_tabela(evento: Evento, b: float, fio: str) -> str:
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
    telefone = (
        f'<div style="font-size:{b * 0.78:.2f}pt; color:{CORES["tinta_fraca"]};">'
        f"{_escapar(cliente.telefone)}</div>"
        if cliente.telefone
        else ""
    )

    if evento.endereco is not None:
        texto_endereco = _escapar(
            f"{evento.endereco.tipo.value}: {evento.endereco.resumo()}"
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


def montar_html(
    titulo: str,
    dias: list[tuple[date, list[Evento]]],
    base: float,
    modo: str = "lista",
    largura: int = 2000,
) -> str:
    """Monta o documento. O mesmo HTML serve aos dois formatos, em corpos diferentes."""
    b = base * ESCALA
    fio = f"{max(1, round(ESCALA * 0.35))}px"
    espaco = round(b * 0.9)

    # Resumo por tipo, para as pastilhas do cabeçalho.
    contagem: dict[str, tuple[str, int]] = {}
    for _dia, eventos in dias:
        for evento in eventos:
            nome = evento.tipo_servico.nome
            estilo, total = contagem.get(nome, (evento.tipo_servico.estilo, 0))
            contagem[nome] = (estilo, total + 1)

    partes = [
        "<html><body>",
        _cabecalho(titulo, contagem, b, largura, empilhado=modo != "tabela"),
    ]

    total = 0
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
                    f' margin-top:{round(espaco * 0.4)}px;">'
                    "&nbsp;Nenhum serviço marcado.&nbsp;</div>"
                )
            continue

        if not um_dia_so:
            partes.append(_titulo_do_dia(dia, len(eventos), b))

        for periodo in Periodo:
            do_periodo = [e for e in eventos if e.periodo is periodo]
            if not do_periodo:
                continue
            partes.append(_faixa_periodo(periodo, b))
            partes.append(
                f'<table cellspacing="0" cellpadding="{round(6 * ESCALA)}"'
                ' width="100%">'
            )
            if modo == "tabela":
                partes.append(_cabecalho_tabela(b, fio))
            for evento in do_periodo:
                total += 1
                partes.append(
                    _linha_tabela(evento, b, fio)
                    if modo == "tabela"
                    else _bloco_servico(evento, b, fio)
                )
            partes.append("</table>")

    emitido = date.today().strftime("%d/%m/%Y")
    partes.append(
        f'<div style="margin-top:{espaco}px; border-top:{fio} solid'
        f' {CORES["pauta_forte"]};"></div>'
        f'<div style="font-size:{b * 0.78:.2f}pt; color:{CORES["tinta_fraca"]};">'
        f"{total} serviço(s) · emitido em {emitido}</div>"
        "</body></html>"
    )
    return "".join(partes)


def _telefone(evento: Evento) -> str:
    return f" · {evento.cliente.telefone}" if evento.cliente.telefone else ""


def gerar_pdf(caminho: str | Path, titulo: str, dias, formato: str) -> Path:
    """Desenha o documento num PDF vetorial — nítido em qualquer ampliação.

    O desenho acontece numa grade de 300 dpi, e os corpos de texto já vêm
    multiplicados por essa escala (ver ESCALA). O ganho está nos fios das
    réguas e no posicionamento das letras: o texto em si é vetorial e não
    rasteriza em nenhuma resolução.
    """
    ajustes = FORMATOS[formato]
    destino = Path(caminho)

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
    escritor.setTitle(titulo)

    documento = QTextDocument()
    documento.setDefaultFont(QFont("Inter", round(ajustes["base"] * ESCALA)))
    # O logotipo entra como recurso do documento, desenhado no tamanho exato
    # em que vai aparecer — nada é reamostrado na hora de imprimir.
    altura_logo = round(ajustes["base"] * ESCALA * 2.4)
    documento.addResource(
        QTextDocument.ResourceType.ImageResource,
        QUrl(URL_LOGO),
        marca.imagem(altura_logo),
    )
    largura = escritor.width()
    altura_fio = max(2, round(ESCALA * 1.2))
    documento.addResource(
        QTextDocument.ResourceType.ImageResource,
        QUrl(URL_FIO),
        marca.fio_imagem(largura, altura_fio),
    )
    documento.setHtml(
        montar_html(titulo, dias, ajustes["base"], ajustes["modo"], largura)
    )
    documento.setPageSize(QSizeF(escritor.width(), escritor.height()))
    documento.print_(escritor)
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


class RelatorioDialog(QDialog):
    """Escolhe o que sai no PDF e em qual formato."""

    def __init__(self, parent: QWidget | None, dia: date | None = None) -> None:
        super().__init__(parent)
        self._dia = dia or date.today()
        self.caminho: Path | None = None

        self.setWindowTitle("Emitir PDF")
        self.setMinimumWidth(430)
        self.setStyleSheet(f"QDialog {{ background: {CORES['papel']}; }}")

        self.campo_abrangencia = Segmentado(Abrangencia)
        self.campo_abrangencia.definir_valor(Abrangencia.DIA)
        self.campo_abrangencia.mudou.connect(self._trocar_abrangencia)
        self.campo_formato = Segmentado(Formato)
        self.campo_formato.definir_valor(Formato.A4)

        self.calendario = SeletorDeData(self)
        self.calendario.definir_data(self._dia)
        self.calendario.escolhida.connect(lambda _d: self._atualizar_resumo())

        self.resumo = rotulo("", "secao")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(10)
        layout.addWidget(rotulo("Emitir PDF", "titulo"))
        layout.addWidget(
            rotulo("A lista dos serviços, com cliente, endereço e tipo.", "fraco")
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
        fechar = QPushButton("Descartar")
        fechar.clicked.connect(self.reject)
        rodape = QHBoxLayout()
        rodape.addStretch(1)
        rodape.addWidget(fechar)
        rodape.addWidget(salvar)
        layout.addLayout(rodape)

        self._atualizar_resumo()

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
        _inicio, _fim, titulo = self._intervalo()
        self.resumo.setText(titulo)

    def _sugestao(self, inicio: date, fim: date) -> str:
        if inicio == fim:
            nome = f"agenda-{inicio.strftime('%Y-%m-%d')}"
        else:
            nome = f"agenda-{inicio.strftime('%Y-%m-%d')}-a-{fim.strftime('%Y-%m-%d')}"
        return str(Path.home() / f"{nome}.pdf")

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
            self.caminho = gerar_pdf(caminho, titulo, dias, formato)
        except Exception as erro:
            mostrar_erro(self, erro, "Não deu para gerar o PDF")
            return
        _abrir_no_sistema(self.caminho)
        self.accept()


def _abrir_no_sistema(caminho: Path) -> None:
    """Abre o PDF no leitor padrão; se não der, o arquivo continua salvo."""
    try:
        subprocess.Popen(
            ["xdg-open", str(caminho)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError:
        pass
