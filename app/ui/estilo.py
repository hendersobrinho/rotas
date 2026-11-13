"""Tema do aplicativo: paleta, fontes e folha de estilo.

Direção visual: a identidade do Rotas (rotas-marca/LEIA-ME.md). Moldura em
marinho, fundo névoa, cartões brancos com bordas finas; o âmbar do pino marca
o botão principal e o que está pendente; o ciano do traço aparece em foco e
seleção, nunca como texto. Sora nos títulos e números grandes, Plus Jakarta
Sans na interface, JetBrains Mono em datas, horários e etiquetas.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QWidget

from app.models import Periodo, StatusEvento
from app.ui.marca import (
    ARDOSIA,
    AZUL_MARCA,
    AZUL_MARCA_CLARO,
    AZUL_TINTA,
    CIANO,
    CIANO_CLARO,
    LARANJA,
    LARANJA_CLARO,
    LINHA,
    NEVOA,
)

FONTE_UI = "Plus Jakarta Sans"
FONTE_TITULO = "Sora"
FONTE_DADOS = "JetBrains Mono"

CORES = {
    "canvas": NEVOA,
    "papel": "#FFFFFF",
    "papel_suave": "#F9FAFC",
    "pauta": LINHA,
    "pauta_forte": "#CED6E4",
    "tinta": AZUL_TINTA,
    "tinta_media": ARDOSIA,
    "tinta_fraca": "#8C96AD",
    # "azul" é o acento de interação: o marinho da marca.
    "azul": AZUL_MARCA,
    "azul_escuro": AZUL_TINTA,
    "azul_claro": AZUL_MARCA_CLARO,
    # Âmbar escuro o bastante para ser texto (5,3:1 no branco).
    "carimbo": "#8A5300",
    "carimbo_claro": LARANJA_CLARO,
    "verde": "#15734A",
    "verde_claro": "#E2F4EA",
    "verde_borda": "#BFE3CF",
    "cinza_claro": "#EFF2F7",
    "vermelho": "#B42318",
    "vermelho_claro": "#FDECEA",
    "marca": AZUL_MARCA,
    "marca_clara": AZUL_MARCA_CLARO,
    "ciano": CIANO,
    "ciano_claro": CIANO_CLARO,
    "laranja": LARANJA,
    "laranja_hover": "#F4A23E",
    "laranja_claro": LARANJA_CLARO,
    # Barra lateral
    "lateral": AZUL_MARCA,
    "lateral_texto": "#B9C4DE",
    "lateral_hover": "#2A4174",
    "lateral_ativo": "#30497F",
}

# Paleta oferecida no cadastro de tipos de serviço.
#
# São quatro e não mais: com o validador de paletas do guia de visualização,
# nenhum conjunto de cinco cores escuras o bastante para servir de texto passou
# na separação entre TODOS os pares, inclusive nas simulações de daltonismo.
# Estas quatro passam em tudo (pior par: ΔE 9,3 em protanopia; 15,9 na visão
# normal). Cada uma vem com um glifo de forma diferente, para a cor nunca ser
# a única pista.
#
# Cada entrada é (cor do texto, fundo da pastilha, preenchimento de barra,
# glifo, nome). O texto é mais escuro que a barra: pastilha pede contraste de
# leitura (5,6:1 ou mais aqui), barra pede contraste de mancha.
PALETA_ETIQUETA: dict[str, tuple[str, str, str, str, str]] = {
    "azul": ("#1B4AA0", "#E9EEFC", "#1E56B8", "●", "Azul"),
    "laranja": ("#8F3310", "#FBEDE5", "#C2410C", "▲", "Laranja"),
    "verde": ("#0B6B56", "#E3F3EF", "#0E8A6E", "■", "Verde"),
    "roxo": ("#6425D0", "#F2EDFE", "#7E3AF2", "◆", "Roxo"),
}
ESTILO_PADRAO = "azul"


def _slot(estilo: str | None) -> tuple[str, str, str, str, str]:
    return PALETA_ETIQUETA.get(estilo or "", PALETA_ETIQUETA[ESTILO_PADRAO])


def cores_da_etiqueta(estilo: str | None) -> tuple[str, str]:
    """Cor do texto e do fundo da pastilha de um tipo de serviço."""
    texto, fundo, _, _, _ = _slot(estilo)
    return texto, fundo


def preenchimento_da_etiqueta(estilo: str | None) -> str:
    """Cor de mancha, para as barras do painel."""
    return _slot(estilo)[2]


def glifo_da_etiqueta(estilo: str | None) -> str:
    return _slot(estilo)[3]


def nome_da_etiqueta(estilo: str | None) -> str:
    return _slot(estilo)[4]


COR_STATUS = {
    StatusEvento.PENDENTE: (CORES["carimbo"], CORES["carimbo_claro"]),
    StatusEvento.CONCLUIDO: (CORES["verde"], CORES["verde_claro"]),
    StatusEvento.NAO_REALIZADO: (CORES["vermelho"], CORES["vermelho_claro"]),
    StatusEvento.CANCELADO: (CORES["tinta_fraca"], CORES["cinza_claro"]),
}

# Como cada situação aparece no calendário e na folha do dia. Só o que está
# em aberto fica com a cor do tipo de serviço; o resto ganha a cor da
# situação e um sinal, para bater o olho e saber o que já teve baixa.
GLIFO_STATUS = {
    StatusEvento.CONCLUIDO: "✓",
    StatusEvento.NAO_REALIZADO: "✕",
    StatusEvento.CANCELADO: "–",
}


def cores_no_calendario(evento) -> tuple[str, str, str]:
    """(texto, fundo, glifo) de um serviço no calendário e na folha do dia."""
    status = evento.status
    if status is StatusEvento.PENDENTE:
        cor, fundo = cores_da_etiqueta(evento.tipo_servico.estilo)
        return cor, fundo, glifo_da_etiqueta(evento.tipo_servico.estilo)
    cor, fundo = COR_STATUS[status]
    return cor, fundo, GLIFO_STATUS[status]


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
    p.setColor(QPalette.ColorRole.Link, QColor(CORES["azul"]))
    for grupo in (QPalette.ColorGroup.Disabled,):
        p.setColor(grupo, QPalette.ColorRole.Text, QColor(CORES["tinta_fraca"]))
        p.setColor(grupo, QPalette.ColorRole.ButtonText, QColor(CORES["tinta_fraca"]))
        p.setColor(grupo, QPalette.ColorRole.WindowText, QColor(CORES["tinta_fraca"]))
    return p


QSS = """
QWidget {{
    font-family: "{ui}";
    font-size: 13px;
    font-weight: 500;
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

/* ------------------------------------------------------ barra lateral */
QFrame#barraLateral {{ background: {lateral}; border: none; }}
QFrame#barraLateral QLabel {{ color: {lateral_texto}; background: transparent; }}
QFrame#barraLateral QLabel[papel="lateral_secao"] {{
    font-family: "{dados}";
    font-size: 10px;
    font-weight: 600;
    color: #7F8FB6;
    padding-left: 14px;
}}
QFrame#barraLateral QLabel[papel="lateral_nome"] {{
    color: #FFFFFF;
    font-weight: 600;
}}
QPushButton[nav="true"] {{
    background: transparent;
    border: none;
    border-radius: 10px;
    padding: 9px 12px;
    text-align: left;
    color: {lateral_texto};
    font-size: 13px;
    font-weight: 600;
}}
QPushButton[nav="true"]:hover {{ background: {lateral_hover}; color: #FFFFFF; }}
QPushButton[nav="true"]:checked {{ background: {lateral_ativo}; color: #FFFFFF; }}
QPushButton[variante="lateral"] {{
    background: transparent;
    border: 1px solid #3A5287;
    border-radius: 8px;
    padding: 6px 12px;
    color: {lateral_texto};
    font-weight: 600;
}}
QPushButton[variante="lateral"]:hover {{
    background: {lateral_hover};
    border-color: {ciano};
    color: #FFFFFF;
}}

/* ---------------------------------------------------------------- abas */
QTabWidget::pane {{ border: none; background: {canvas}; }}
QTabBar::tab {{
    background: transparent;
    color: {tinta_media};
    padding: 8px 18px;
    margin-right: 4px;
    border-radius: 8px;
    font-weight: 600;
}}
QTabBar::tab:selected {{ background: {papel}; color: {tinta}; }}
QTabBar::tab:hover:!selected {{ color: {tinta}; }}

/* ------------------------------------------------------------- cartões */
QFrame[cartao="true"] {{
    background: {papel};
    border: 1px solid {pauta};
    border-radius: 14px;
}}
QFrame[cartao="plano"] {{
    background: {papel};
    border: 1px solid {pauta};
    border-radius: 12px;
}}
QFrame[separador="true"] {{ background: {pauta}; border: none; }}

/* -------------------------------------------------------------- textos */
QLabel[papel="titulo"] {{
    font-family: "{titulo}";
    font-size: 21px;
    font-weight: 700;
    color: {tinta};
}}
QLabel[papel="secao"] {{
    font-family: "{titulo}";
    font-size: 14px;
    font-weight: 700;
    color: {tinta};
}}
QLabel[papel="etiqueta"] {{
    font-family: "{dados}";
    font-size: 10px;
    font-weight: 600;
    color: {tinta_fraca};
}}
QLabel[papel="apoio"] {{ color: {tinta_media}; }}
QLabel[papel="fraco"] {{ color: {tinta_media}; font-size: 12px; }}
QLabel[papel="campo"] {{ color: {tinta_media}; font-size: 12px; font-weight: 600; }}
QLabel[papel="numero"] {{ font-family: "{dados}"; font-size: 13px; color: {tinta_media}; }}
QLabel[papel="grande"] {{
    font-family: "{titulo}";
    font-size: 28px;
    font-weight: 800;
    color: {tinta};
}}

/* -------------------------------------------------------------- campos */
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox, QDateEdit, QSpinBox {{
    background: {papel};
    border: 1px solid {pauta_forte};
    border-radius: 9px;
    padding: 6px 10px;
    selection-background-color: {ciano_claro};
    selection-color: {tinta};
}}
QLineEdit:hover, QComboBox:hover, QDateEdit:hover, QPlainTextEdit:hover, QSpinBox:hover {{
    border-color: {tinta_fraca};
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus {{
    border: 1px solid {ciano};
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
QCheckBox {{ spacing: 8px; color: {tinta}; }}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {pauta_forte};
    border-radius: 5px;
    background: {papel};
}}
QCheckBox::indicator:hover {{ border-color: {ciano}; }}
QCheckBox::indicator:checked {{
    background: {marca};
    border-color: {marca};
    image: none;
}}

/* -------------------------------------------------------------- botões */
QPushButton {{
    background: {papel};
    border: 1px solid {pauta_forte};
    border-radius: 9px;
    padding: 7px 14px;
    font-weight: 600;
    color: {tinta};
}}
QPushButton:hover {{ background: {papel_suave}; border-color: {tinta_fraca}; }}
QPushButton:pressed {{ background: {cinza_claro}; }}
QPushButton:disabled {{
    background: {papel_suave};
    color: {tinta_fraca};
    border-color: {pauta};
}}
/* O botão principal é âmbar, com texto em tinta — como manda a marca. */
QPushButton[variante="primario"] {{
    background: {laranja};
    border-color: {laranja};
    color: {tinta};
    font-weight: 700;
}}
QPushButton[variante="primario"]:hover {{
    background: {laranja_hover};
    border-color: {laranja_hover};
}}
QPushButton[variante="primario"]:disabled {{
    background: #FBE0BC;
    border-color: #FBE0BC;
    color: #A89A86;
}}
QPushButton[variante="marinho"] {{
    background: {marca};
    border-color: {marca};
    color: #FFFFFF;
    font-weight: 700;
}}
QPushButton[variante="marinho"]:hover {{ background: {tinta}; border-color: {tinta}; }}
QPushButton[variante="sucesso"] {{
    background: {verde_claro};
    border-color: {verde_borda};
    color: {verde};
    font-weight: 700;
}}
QPushButton[variante="sucesso"]:hover {{
    background: {verde};
    border-color: {verde};
    color: #FFFFFF;
}}
QPushButton[variante="perigo"] {{ color: {vermelho}; }}
QPushButton[variante="perigo"]:hover {{
    background: {vermelho_claro};
    border-color: {vermelho};
}}
QPushButton[variante="alerta"] {{
    background: {carimbo_claro};
    border-color: #F6D3A4;
    color: {carimbo};
    font-weight: 700;
}}
QPushButton[variante="alerta"]:hover {{ background: {laranja}; border-color: {laranja}; color: {tinta}; }}
QPushButton[variante="fantasma"] {{
    background: transparent;
    border: 1px solid transparent;
    color: {tinta_media};
    padding: 6px 10px;
}}
QPushButton[variante="fantasma"]:hover {{ background: {cinza_claro}; color: {tinta}; }}
/* Botão que abre uma escolha, com aparência de campo. */
QPushButton[variante="campo"] {{
    background: {papel};
    border: 1px solid {pauta_forte};
    border-radius: 9px;
    padding: 7px 12px;
    text-align: left;
    font-weight: 500;
    color: {tinta};
}}
QPushButton[variante="campo"]:hover {{ border-color: {ciano}; }}
QPushButton[variante="campo"]:disabled {{
    background: {papel_suave};
    color: {tinta_fraca};
    border-color: {pauta};
}}
QPushButton[variante="segmento"] {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 7px;
    padding: 6px 14px;
    color: {tinta_media};
    font-weight: 600;
}}
QPushButton[variante="segmento"]:hover {{ color: {tinta}; }}
QPushButton[variante="segmento"]:checked {{
    background: {papel};
    border-color: {pauta_forte};
    color: {tinta};
    font-weight: 700;
}}
QPushButton[variante="segmento"]:disabled {{
    background: transparent;
    border-color: transparent;
    color: {tinta_fraca};
}}
QPushButton[variante="segmento"]:checked:disabled {{
    background: {papel};
    border-color: {pauta};
    color: {tinta_media};
    font-weight: 700;
}}
/* Campo só de leitura: sem moldura de digitação, texto ainda selecionável. */
QLineEdit[leitura="true"], QPlainTextEdit[leitura="true"] {{
    background: {papel_suave};
    border-color: {pauta};
    color: {tinta};
}}
QFrame[grupo="segmentado"] {{
    background: {cinza_claro};
    border: 1px solid {pauta};
    border-radius: 10px;
}}

/* ------------------------------------------------------------- tabelas */
QTableWidget, QTableView {{
    background: {papel};
    border: none;
    gridline-color: transparent;
    outline: none;
}}
/* Sem cor fixa aqui: a folha de estilo ganharia de setForeground() e as
   linhas que as telas pintam (vermelho para o que tem problema, cinza para o
   que está desligado) sairiam todas pretas. O padrão vem da paleta, que já
   usa a mesma tinta. */
QTableWidget::item {{ padding: 7px 8px; border-bottom: 1px solid {cinza_claro}; }}
QTableWidget::item:selected {{ background: {azul_claro}; color: {tinta}; }}
QHeaderView::section {{
    background: {papel};
    color: {tinta_fraca};
    border: none;
    border-bottom: 1px solid {pauta};
    padding: 9px 8px;
    font-family: "{dados}";
    font-size: 10px;
    font-weight: 600;
}}

/* --------------------------------------------------- barra de progresso */
QProgressBar {{
    background: {cinza_claro};
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
    color: transparent;
}}
QProgressBar::chunk {{ background: {verde}; border-radius: 4px; }}

/* ------------------------------------------------- rolagem e divisores */
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
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
QStatusBar {{
    background: {papel};
    color: {tinta_fraca};
    border-top: 1px solid {pauta};
    font-size: 11px;
}}
QStatusBar::item {{ border: none; }}
QMessageBox {{ background: {papel}; }}
"""


def carregar_fontes() -> list[str]:
    """Registra as fontes embarcadas — no Windows elas não existem instaladas.

    Devolve as famílias que entraram, para o caso de alguém querer conferir.
    """
    from PySide6.QtGui import QFontDatabase

    from app import caminhos

    familias: list[str] = []
    pasta = caminhos.recurso("fontes")
    if not pasta.is_dir():
        return familias
    for arquivo in sorted(pasta.glob("*.ttf")):
        indice = QFontDatabase.addApplicationFont(str(arquivo))
        if indice >= 0:
            familias.extend(QFontDatabase.applicationFontFamilies(indice))
    return sorted(set(familias))


def folha_de_estilo() -> str:
    return QSS.format(ui=FONTE_UI, titulo=FONTE_TITULO, dados=FONTE_DADOS, **CORES)


def aplicar_tema(app: QApplication) -> None:
    """Deixa o app sempre claro, independente do tema do sistema."""
    from PySide6.QtGui import QFont

    carregar_fontes()
    app.setStyle("Fusion")
    app.setPalette(_palette_clara())
    fonte = QFont(FONTE_UI, 10)
    fonte.setWeight(QFont.Weight.Medium)
    app.setFont(fonte)
    app.setStyleSheet(folha_de_estilo())
