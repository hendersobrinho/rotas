"""Emissão do PDF da agenda — para imprimir ou para ler no celular."""

from __future__ import annotations

import enum
import subprocess
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
    "A4": dict(tamanho=QPageSize(QPageSize.PageSizeId.A4), margem=14.0, base=10.5),
    "Celular": dict(
        tamanho=QPageSize(QSizeF(95.0, 170.0), QPageSize.Unit.Millimeter),
        margem=7.0,
        base=9.0,
    ),
}


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


def montar_html(titulo: str, dias: list[tuple[date, list[Evento]]], base: float) -> str:
    """Monta o documento. O mesmo HTML serve aos dois formatos, em corpos diferentes."""
    partes = [
        f"""<html><body>
        <div style="font-size:{base * 1.5:.1f}pt; font-weight:600;
                    color:{CORES['tinta']};">Agenda do motoboy</div>
        <div style="font-size:{base * 1.05:.1f}pt; color:{CORES['tinta_media']};
                    margin-bottom:{base * 0.9:.0f}px;">{_escapar(titulo)}</div>
        """
    ]

    total = 0
    # Num PDF de um dia só, o subtítulo já diz a data: não repetir.
    repetir_data = len(dias) > 1
    for dia, eventos in dias:
        if repetir_data:
            partes.append(
                f'<div style="font-size:{base * 1.1:.1f}pt; font-weight:600;'
                f' color:{CORES["tinta"]}; margin-top:{base:.0f}px;">'
                f"{_escapar(data_por_extenso(dia).capitalize())}</div>"
                f'<hr style="border:0; border-top:1px solid {CORES["pauta_forte"]};">'
            )
        else:
            partes.append(
                f'<hr style="border:0; border-top:1px solid {CORES["pauta_forte"]};">'
            )
        if not eventos:
            partes.append(
                f'<div style="font-size:{base:.1f}pt; color:{CORES["tinta_fraca"]};">'
                "Nenhum serviço marcado.</div>"
            )
            continue

        for periodo in Periodo:
            do_periodo = [e for e in eventos if e.periodo is periodo]
            if not do_periodo:
                continue
            partes.append(
                f'<div style="font-size:{base * 0.8:.1f}pt; font-weight:600;'
                f' color:{CORES["tinta_fraca"]}; margin-top:{base * 0.6:.0f}px;">'
                f"{ROTULO_PERIODO[periodo]}</div>"
            )
            partes.append('<table cellspacing="0" cellpadding="4" width="100%">')
            for evento in do_periodo:
                total += 1
                cor, _ = cores_da_etiqueta(evento.tipo_servico.estilo)
                # "none" explícito: sem ele o Qt sublinha o trecho colorido.
                risco = (
                    "text-decoration: line-through;"
                    if evento.status is StatusEvento.CANCELADO
                    else "text-decoration: none;"
                )
                solicitante = (
                    f" · Pedido por {_escapar(evento.solicitante.nome_exibicao)}"
                    if evento.solicitante
                    else ""
                )
                partes.append(
                    f'<tr><td width="18" valign="top" style="font-size:{base * 1.2:.1f}pt;'
                    f' color:{CORES["tinta_fraca"]};">&#9744;</td>'
                    f'<td valign="top" style="border-bottom:1px solid {CORES["pauta"]};">'
                    f'<span style="font-size:{base:.1f}pt; font-weight:600;'
                    f' color:{cor}; {risco}">{_escapar(evento.tipo_servico.nome)}</span>'
                    f'<span style="font-size:{base:.1f}pt; color:{CORES["tinta"]};'
                    f' {risco}"> &nbsp;{_escapar(evento.cliente.nome_exibicao)}</span>'
                    f'<div style="font-size:{base * 0.85:.1f}pt;'
                    f' color:{CORES["tinta_media"]};">{_escapar(_endereco(evento))}</div>'
                    f'<div style="font-size:{base * 0.85:.1f}pt;'
                    f' color:{CORES["tinta_fraca"]};">'
                    f"{_escapar(evento.status.value)}{solicitante}"
                    f"{_escapar(_telefone(evento))}</div></td></tr>"
                )
            partes.append("</table>")

    emitido = date.today().strftime("%d/%m/%Y")
    partes.append(
        f'<div style="font-size:{base * 0.8:.1f}pt; color:{CORES["tinta_fraca"]};'
        f' margin-top:{base * 1.2:.0f}px;">{total} serviço(s) · emitido em {emitido}</div>'
        "</body></html>"
    )
    return "".join(partes)


def _telefone(evento: Evento) -> str:
    return f" · {evento.cliente.telefone}" if evento.cliente.telefone else ""


def gerar_pdf(caminho: str | Path, titulo: str, dias, formato: str) -> Path:
    """Desenha o documento num PDF vetorial — nítido em qualquer ampliação.

    A resolução fica em 72 dpi de propósito: é o que faz 1 ponto do HTML valer
    1 unidade da página, e o texto sair no corpo certo. Não é qualidade de
    imagem — o PDF é vetorial, o texto não rasteriza.
    """
    ajustes = FORMATOS[formato]
    destino = Path(caminho)

    escritor = QPdfWriter(str(destino))
    escritor.setPageSize(ajustes["tamanho"])
    escritor.setPageOrientation(QPageLayout.Orientation.Portrait)
    escritor.setPageMargins(
        QMarginsF(*([ajustes["margem"]] * 4)), QPageLayout.Unit.Millimeter
    )
    escritor.setResolution(72)
    escritor.setTitle(titulo)

    documento = QTextDocument()
    documento.setDefaultFont(QFont("Inter", int(ajustes["base"])))
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
