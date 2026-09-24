"""Tema claro do aplicativo: paleta, fontes e folha de estilo.

Direção visual: papel de agenda de escritório — fundo branco, pautas finas
em cinza, azul-caneta como acento e laranja-carimbo para as retiradas.
Inter no texto; JetBrains Mono só nos números e nas etiquetas, para dar o ar
de agenda sem virar enfeite.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QWidget

from app.models import Periodo, StatusEvento, TipoServico

FONTE_UI = "Inter"
FONTE_DADOS = "JetBrains Mono"

CORES = {
    "canvas": "#F4F5F7",
    "papel": "#FFFFFF",
    "papel_suave": "#FAFBFC",
    "pauta": "#E7E9EE",
    "pauta_forte": "#D6DAE1",
    "tinta": "#171A20",
    "tinta_media": "#5C6472",
    "tinta_fraca": "#98A0AE",
    "azul": "#2B50C8",
    "azul_escuro": "#23429F",
    "azul_claro": "#E9EEFC",
    "carimbo": "#B4511E",
    "carimbo_claro": "#FBEDE5",
    "verde": "#17714B",
    "verde_claro": "#E6F3EC",
    "cinza_claro": "#F1F2F5",
    "vermelho": "#B42318",
    "vermelho_claro": "#FEECEB",
}

# Coleta é azul-caneta; retirada é laranja-carimbo.
COR_SERVICO = {
    TipoServico.COLETA: (CORES["azul"], CORES["azul_claro"]),
    TipoServico.RETIRADA: (CORES["carimbo"], CORES["carimbo_claro"]),
}

COR_STATUS = {
    StatusEvento.PENDENTE: (CORES["tinta_media"], CORES["cinza_claro"]),
    StatusEvento.CONCLUIDO: (CORES["verde"], CORES["verde_claro"]),
    StatusEvento.CANCELADO: (CORES["tinta_fraca"], CORES["cinza_claro"]),
}

ROTULO_PERIODO = {Periodo.MANHA: "MANHÃ", Periodo.TARDE: "TARDE"}


def marcar(widget: QWidget, **propriedades: object) -> QWidget:
    """Define propriedades dinâmicas usadas pelos seletores da folha de estilo."""
    for nome, valor in propriedades.items():
        widget.setProperty(nome, valor)
    estilo = widget.style()
    estilo.unpolish(widget)
    estilo.polish(widget)
    return widget


def _palette_clara() -> QPalette:
    """Paleta clara fixa: o app não acompanha o tema escuro do sistema."""
    p = QPalette()
    p.setColor(QPalette.ColorRole.Window, QColor(CORES["canvas"]))
    p.setColor(QPalette.ColorRole.WindowText, QColor(CORES["tinta"]))
    p.setColor(QPalette.ColorRole.Base, QColor(CORES["papel"]))
    p.setColor(QPalette.ColorRole.AlternateBase, QColor(CORES["papel_suave"]))
    p.setColor(QPalette.ColorRole.Text, QColor(CORES["tinta"]))
    p.setColor(QPalette.ColorRole.Button, QColor(CORES["papel"]))
    p.setColor(QPalette.ColorRole.ButtonText, QColor(CORES["tinta"]))
    p.setColor(QPalette.ColorRole.Highlight, QColor(CORES["azul"]))
    p.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    p.setColor(QPalette.ColorRole.ToolTipBase, QColor(CORES["tinta"]))
    p.setColor(QPalette.ColorRole.ToolTipText, QColor("#FFFFFF"))
    p.setColor(QPalette.ColorRole.PlaceholderText, QColor(CORES["tinta_fraca"]))
    for grupo in (QPalette.ColorGroup.Disabled,):
        p.setColor(grupo, QPalette.ColorRole.Text, QColor(CORES["tinta_fraca"]))
        p.setColor(grupo, QPalette.ColorRole.ButtonText, QColor(CORES["tinta_fraca"]))
        p.setColor(grupo, QPalette.ColorRole.WindowText, QColor(CORES["tinta_fraca"]))
    return p


QSS = """
QWidget {{
    font-family: "{ui}";
    font-size: 13px;
    color: {tinta};
}}
QMainWindow, QDialog {{ background: {canvas}; }}
QToolTip {{
    background: {tinta};
    color: #FFFFFF;
    border: none;
    border-radius: 6px;
    padding: 5px 8px;
}}

/* ---------------------------------------------------------------- abas */
QTabWidget::pane {{ border: none; background: {canvas}; }}
QTabBar::tab {{
    background: transparent;
    color: {tinta_media};
    padding: 8px 18px;
    margin-right: 4px;
    border-radius: 8px;
    font-weight: 500;
}}
QTabBar::tab:selected {{ background: {papel}; color: {tinta}; }}
QTabBar::tab:hover:!selected {{ color: {tinta}; }}

/* ------------------------------------------------------------- cartões */
QFrame[cartao="true"] {{
    background: {papel};
    border: 1px solid {pauta};
    border-radius: 12px;
}}
QFrame[cartao="plano"] {{
    background: {papel};
    border: 1px solid {pauta};
    border-radius: 10px;
}}
QFrame[separador="true"] {{ background: {pauta}; border: none; }}

/* -------------------------------------------------------------- textos */
QLabel[papel="titulo"] {{ font-size: 19px; font-weight: 600; color: {tinta}; }}
QLabel[papel="secao"] {{ font-size: 14px; font-weight: 600; color: {tinta}; }}
QLabel[papel="etiqueta"] {{
    font-family: "{dados}";
    font-size: 10px;
    font-weight: 600;
    color: {tinta_fraca};
}}
QLabel[papel="apoio"] {{ color: {tinta_media}; }}
QLabel[papel="fraco"] {{ color: {tinta_fraca}; font-size: 12px; }}
QLabel[papel="campo"] {{ color: {tinta_media}; font-size: 12px; font-weight: 500; }}
QLabel[papel="numero"] {{ font-family: "{dados}"; font-size: 13px; color: {tinta_media}; }}

/* -------------------------------------------------------------- campos */
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QDateEdit, QSpinBox {{
    background: {papel};
    border: 1px solid {pauta_forte};
    border-radius: 8px;
    padding: 6px 10px;
    selection-background-color: {azul_claro};
    selection-color: {tinta};
}}
QLineEdit:hover, QComboBox:hover, QDateEdit:hover, QPlainTextEdit:hover {{
    border-color: {tinta_fraca};
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QDateEdit:focus {{
    border-color: {azul};
}}
QLineEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled, QDateEdit:disabled {{
    background: {papel_suave};
    color: {tinta_fraca};
    border-color: {pauta};
}}
/* espaço à direita para a seta que o Fusion desenha */
QComboBox, QDateEdit {{ padding-right: 24px; }}
QComboBox QAbstractItemView {{
    background: {papel};
    border: 1px solid {pauta_forte};
    border-radius: 8px;
    padding: 4px;
    selection-background-color: {azul_claro};
    selection-color: {tinta};
    outline: none;
}}

/* -------------------------------------------------------------- botões */
QPushButton {{
    background: {papel};
    border: 1px solid {pauta_forte};
    border-radius: 8px;
    padding: 7px 14px;
    font-weight: 500;
    color: {tinta};
}}
QPushButton:hover {{ background: {papel_suave}; border-color: {tinta_fraca}; }}
QPushButton:pressed {{ background: {cinza_claro}; }}
QPushButton:disabled {{
    background: {papel_suave};
    color: {tinta_fraca};
    border-color: {pauta};
}}
QPushButton[variante="primario"] {{
    background: {azul};
    border-color: {azul};
    color: #FFFFFF;
    font-weight: 600;
}}
QPushButton[variante="primario"]:hover {{ background: {azul_escuro}; border-color: {azul_escuro}; }}
QPushButton[variante="primario"]:disabled {{
    background: #B3C0E9;
    border-color: #B3C0E9;
    color: #F3F6FD;
}}
QPushButton[variante="perigo"] {{ color: {vermelho}; }}
QPushButton[variante="perigo"]:hover {{
    background: {vermelho_claro};
    border-color: {vermelho};
}}
QPushButton[variante="fantasma"] {{
    background: transparent;
    border: 1px solid transparent;
    color: {tinta_media};
    padding: 6px 10px;
}}
QPushButton[variante="fantasma"]:hover {{ background: {cinza_claro}; color: {tinta}; }}
QPushButton[variante="segmento"] {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 7px;
    padding: 6px 14px;
    color: {tinta_media};
    font-weight: 500;
}}
QPushButton[variante="segmento"]:hover {{ color: {tinta}; }}
QPushButton[variante="segmento"]:checked {{
    background: {papel};
    border-color: {pauta_forte};
    color: {tinta};
    font-weight: 600;
}}
QFrame[grupo="segmentado"] {{
    background: {cinza_claro};
    border: 1px solid {pauta};
    border-radius: 9px;
}}

/* ------------------------------------------------------------- tabelas */
QTableWidget, QTableView {{
    background: {papel};
    border: none;
    gridline-color: transparent;
    outline: none;
}}
QTableWidget::item {{ padding: 7px 8px; color: {tinta}; }}
QTableWidget::item:selected {{ background: {azul_claro}; color: {tinta}; }}
QHeaderView::section {{
    background: {papel};
    color: {tinta_fraca};
    border: none;
    border-bottom: 1px solid {pauta};
    padding: 8px;
    font-family: "{dados}";
    font-size: 10px;
    font-weight: 600;
}}

/* ------------------------------------------------- rolagem e divisores */
QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{
    background: {pauta_forte};
    border-radius: 4px;
    min-height: 28px;
}}
QScrollBar::handle:vertical:hover {{ background: {tinta_fraca}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{
    background: {pauta_forte};
    border-radius: 4px;
    min-width: 28px;
}}
QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
QSplitter::handle {{ background: transparent; }}
QStatusBar {{ background: {canvas}; color: {tinta_fraca}; }}
QStatusBar::item {{ border: none; }}
"""


def aplicar_tema(app: QApplication) -> None:
    """Deixa o app sempre claro, independente do tema do sistema."""
    app.setStyle("Fusion")
    app.setPalette(_palette_clara())
    app.setStyleSheet(
        QSS.format(ui=FONTE_UI, dados=FONTE_DADOS, **CORES)
    )
