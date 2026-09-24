"""Verifica o PDF: logotipo, cores da marca, folha deitada e versão celular."""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

from comum import RAIZ, preparar_ambiente, semear

preparar_ambiente()

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication([])

from app.ui.datas import inicio_da_semana  # noqa: E402
from app.ui.relatorio_pdf import (  # noqa: E402
    FORMATOS,
    FormatoPdf,
    carregar_dias,
    gerar_pdf,
    montar_html,
)

SAIDA = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "testes" / ".saida"
SAIDA.mkdir(parents=True, exist_ok=True)

dados = semear()
hoje = dados["hoje"]
dia = carregar_dias(hoje, hoje)
inicio = inicio_da_semana(hoje)
semana = carregar_dias(inicio, inicio + timedelta(days=6))

# ---- conteúdo ------------------------------------------------------------
html_tabela = montar_html("Teste", dia, 9.5, "tabela")
html_lista = montar_html("Teste", dia, 8.0, "lista")
assert 'src="marca-rotas"' in html_tabela and 'src="marca-rotas"' in html_lista
assert 'src="fio-marca"' in html_tabela, "fio tricolor no cabeçalho"
assert "#203461" in html_tabela, "azul da marca no cabeçalho"

# o fio é imagem: confere as três cores direto nos pixels
from app.ui import marca  # noqa: E402

fio = marca.fio_imagem(1000, 6)
cores = {fio.pixelColor(x, 3).name().upper() for x in (100, 600, 900)}
assert cores == {"#203461", "#4BBDCD", "#F9B259"}, cores
print("ok fio tricolor:", ", ".join(sorted(cores)))

logotipo = marca.imagem(120)
assert logotipo.width() > logotipo.height(), "logotipo deitado, proporção mantida"
assert marca.imagem(64, simbolo=True).width() < logotipo.width()
assert "Panificadora Estrela do Oriente LTDA" in html_tabela
assert "Tratar por <b>Padaria da Ana</b>" in html_tabela
assert "Obs.: Falar com a Ana" in html_tabela
assert "maps/search" in html_tabela and "↗ mapa" in html_tabela
assert "QUEM PEDIU" in html_tabela, "cabeçalho de colunas só no modo tabela"
assert "QUEM PEDIU" not in html_lista
print("ok html: logotipo, cores da marca, colunas e vínculos")

# ---- páginas -------------------------------------------------------------
assert FORMATOS["A4"]["deitada"] is True and FORMATOS["A4"]["modo"] == "tabela"
assert FORMATOS["Celular"]["deitada"] is False
assert FORMATOS["Celular"]["base"] < FORMATOS["A4"]["base"], "celular com corpo menor"
print("ok formatos: A4 deitado em tabela, celular em pé e com letra menor")

for nome, conteudo, formato in (
    ("dia_a4", dia, FormatoPdf.A4),
    ("semana_a4", semana, FormatoPdf.A4),
    ("dia_celular", dia, FormatoPdf.CELULAR),
    ("semana_celular", semana, FormatoPdf.CELULAR),
):
    destino = gerar_pdf(SAIDA / f"{nome}.pdf", "Agenda do motoboy", conteudo, formato)
    bruto = destino.read_bytes()
    assert b"/URI" in bruto and b"/Link" in bruto, f"{nome}: link do mapa"
    assert b"/Image" in bruto, f"{nome}: logotipo embutido"
    print(f"ok pdf {nome:<16} {len(bruto)/1024:6.1f} KB")

print("TESTE PDF OK")
