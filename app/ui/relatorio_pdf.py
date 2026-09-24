"""Emissão do PDF da agenda — para imprimir ou para ler no celular."""

from __future__ import annotations

import enum
import subprocess
from urllib.parse import quote_plus
from datetime import date, timedelta
from pathlib import Path

from PySide6.QtCore import QMarginsF, QSizeF
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
from app.ui.datas import (
    Agrupamento,
    data_por_extenso,
    inicio_da_semana,
    rotulo_do_periodo,
)
from app.ui.estilo import CORES, ROTULO_PERIODO, cores_da_etiqueta, marcar
from app.ui.mensagens import mostrar_erro
from app.ui.widgets import Segmentado, rotulo

# Duas páginas possíveis: A4 para imprimir e uma estreita que enche a tela do
# celular sem precisar dar zoom.
FORMATOS = {
    "A4": dict(tamanho=QPageSize(QPageSize.PageSizeId.A4), margem=15.0, base=11.5),
    "Celular": dict(
        tamanho=QPageSize(QSizeF(95.0, 170.0), QPageSize.Unit.Millimeter),
        margem=7.0,
        base=9.5,
    ),
}

# O desenho é feito numa grade de 300 dpi em vez dos 72 dpi de um ponto. Não é
# o texto que muda — ele é vetorial dos dois jeitos —, são os fios: "1px" a
# 72 dpi vira um traço de 0,34 mm, grosso; a 300 dpi vira fio de 0,085 mm.
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


def _bloco_servico(evento: Evento, b: float, fio: str) -> str:
    """Um serviço: quem é, onde, como tratar e o que foi combinado."""
    cor, _ = cores_da_etiqueta(evento.tipo_servico.estilo)
    cancelado = evento.status is StatusEvento.CANCELADO
    risco = "text-decoration: line-through;" if cancelado else "text-decoration: none;"
    cliente = evento.cliente

    linhas = [
        f'<span style="font-size:{b * 0.95:.2f}pt; font-weight:600; color:{cor};'
        f' {risco}">{_escapar(evento.tipo_servico.nome)}</span>'
        f'<span style="font-size:{b * 1.1:.2f}pt; font-weight:600;'
        f' color:{CORES["tinta"]}; {risco}">'
        f"&nbsp;&nbsp;{_escapar(cliente.nome)}</span>"
    ]

    if cliente.apelido and cliente.apelido.strip() != cliente.nome.strip():
        linhas.append(
            f'<div style="font-size:{b * 0.85:.2f}pt; color:{CORES["tinta_media"]};">'
            f"Tratar por <b>{_escapar(cliente.apelido)}</b></div>"
        )

    if evento.endereco is not None:
        endereco = _escapar(
            f"{evento.endereco.tipo.value}: {evento.endereco.resumo()}"
        )
        mapa = _mapa(evento)
        if mapa:
            linhas.append(
                f'<div style="font-size:{b * 0.88:.2f}pt;">'
                f'<a href="{mapa}" style="color:{CORES["azul"]};'
                f' text-decoration: none;">{endereco}</a>'
                f'<span style="color:{CORES["azul"]}; font-size:{b * 0.8:.2f}pt;">'
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
            f' background:{CORES["cinza_claro"]};">'
            f"&nbsp;Obs.: {_escapar(texto)}&nbsp;</div>"
        )

    return (
        f'<tr><td width="{int(22 * ESCALA)}" valign="top"'
        f' style="font-size:{b * 1.25:.2f}pt; color:{CORES["tinta_fraca"]};">'
        "&#9744;</td>"
        f'<td valign="top" style="border-bottom:{fio} solid {CORES["pauta"]};">'
        + "".join(linhas)
        + "</td></tr>"
    )


def montar_html(titulo: str, dias: list[tuple[date, list[Evento]]], base: float) -> str:
    """Monta o documento. O mesmo HTML serve aos dois formatos, em corpos diferentes."""
    b = base * ESCALA
    fio = f"{max(1, round(ESCALA * 0.35))}px"
    fio_forte = f"{max(1, round(ESCALA * 0.5))}px"
    espaco = round(b * 0.9)

    partes = [
        f"""<html><body>
        <div style="font-size:{b * 1.55:.2f}pt; font-weight:600;
                    color:{CORES['tinta']};">Agenda do motoboy</div>
        <div style="font-size:{b * 1.05:.2f}pt; color:{CORES['tinta_media']};
                    margin-bottom:{espaco}px;">{_escapar(titulo)}</div>
        """
    ]

    total = 0
    # Num PDF de um dia só, o subtítulo já diz a data: não repetir.
    repetir_data = len(dias) > 1
    for dia, eventos in dias:
        if repetir_data:
            partes.append(
                f'<div style="font-size:{b * 1.15:.2f}pt; font-weight:600;'
                f' color:{CORES["tinta"]}; margin-top:{espaco}px;">'
                f"{_escapar(data_por_extenso(dia).capitalize())}</div>"
            )
        partes.append(
            f'<hr style="border:0; border-top:{fio_forte} solid'
            f' {CORES["pauta_forte"]};">'
        )
        if not eventos:
            partes.append(
                f'<div style="font-size:{b:.2f}pt; color:{CORES["tinta_fraca"]};">'
                "Nenhum serviço marcado.</div>"
            )
            continue

        for periodo in Periodo:
            do_periodo = [e for e in eventos if e.periodo is periodo]
            if not do_periodo:
                continue
            partes.append(
                f'<div style="font-size:{b * 0.78:.2f}pt; font-weight:600;'
                f' color:{CORES["tinta_fraca"]}; margin-top:{round(espaco * 0.7)}px;">'
                f"{ROTULO_PERIODO[periodo]}</div>"
            )
            partes.append(
                f'<table cellspacing="0" cellpadding="{round(5 * ESCALA)}"'
                ' width="100%">'
            )
            for evento in do_periodo:
                total += 1
                partes.append(_bloco_servico(evento, b, fio))
            partes.append("</table>")

    emitido = date.today().strftime("%d/%m/%Y")
    partes.append(
        f'<div style="font-size:{b * 0.78:.2f}pt; color:{CORES["tinta_fraca"]};'
        f' margin-top:{espaco}px;">{total} serviço(s) · emitido em {emitido}</div>'
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
    escritor.setPageOrientation(QPageLayout.Orientation.Portrait)
    escritor.setPageMargins(
        QMarginsF(*([ajustes["margem"]] * 4)), QPageLayout.Unit.Millimeter
    )
    escritor.setResolution(RESOLUCAO)
    escritor.setTitle(titulo)

    documento = QTextDocument()
    documento.setDefaultFont(QFont("Inter", round(ajustes["base"] * ESCALA)))
    documento.setHtml(montar_html(titulo, dias, ajustes["base"]))
    documento.setPageSize(
        QSizeF(escritor.width(), escritor.height())
    )
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
        self.setMinimumWidth(460)
        self.setStyleSheet(f"QDialog {{ background: {CORES['papel']}; }}")

        self.campo_abrangencia = Segmentado(Abrangencia)
        self.campo_abrangencia.definir_valor(Abrangencia.DIA)
        self.campo_abrangencia.mudou.connect(lambda _v: self._atualizar_resumo())
        self.campo_formato = Segmentado(Formato)
        self.campo_formato.definir_valor(Formato.A4)

        self.resumo = rotulo("", "fraco")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(10)
        layout.addWidget(rotulo("Emitir PDF", "titulo"))
        layout.addWidget(
            rotulo("A lista dos serviços, com cliente, endereço e tipo.", "fraco")
        )
        layout.addSpacing(8)
        layout.addWidget(rotulo("O que sai", "campo"))
        layout.addWidget(self.campo_abrangencia)
        layout.addSpacing(6)
        layout.addWidget(rotulo("Formato da página", "campo"))
        layout.addWidget(self.campo_formato)
        layout.addWidget(
            rotulo("A4 imprime; Celular é estreito e lê sem zoom.", "fraco")
        )
        layout.addSpacing(6)
        layout.addWidget(self.resumo)
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

    def _intervalo(self) -> tuple[date, date, str]:
        if self.campo_abrangencia.valor() is Abrangencia.SEMANA:
            inicio = inicio_da_semana(self._dia)
            fim = inicio + timedelta(days=6)
            return inicio, fim, rotulo_do_periodo(inicio, Agrupamento.SEMANA)
        return self._dia, self._dia, data_por_extenso(self._dia).capitalize()

    def _atualizar_resumo(self) -> None:
        inicio, fim, titulo = self._intervalo()
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
