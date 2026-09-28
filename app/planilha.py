"""Leitura e escrita de planilhas, em .xlsx e em .csv.

O escritório trabalha em Excel, então o formato natural é o .xlsx — que
depende do openpyxl. O .csv não depende de nada e fica como alternativa: é
gravado com ponto e vírgula e com BOM porque é assim que o Excel em português
abre o arquivo sem embaralhar as colunas nem os acentos.

Aqui só se lê e escreve tabela crua (listas de texto). Quem sabe o que cada
coluna significa é `app/importacao_clientes.py`.
"""

from __future__ import annotations

import csv
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

try:  # o .xlsx é opcional: sem openpyxl o programa ainda importa/exporta .csv
    import openpyxl
except ImportError:  # pragma: no cover - depende do ambiente
    openpyxl = None

TEM_XLSX = openpyxl is not None

FILTRO_LEITURA = (
    "Planilhas (*.xlsx *.xlsm *.csv);;Excel (*.xlsx *.xlsm);;CSV (*.csv)"
    if TEM_XLSX
    else "CSV (*.csv)"
)
FILTRO_ESCRITA = "Excel (*.xlsx);;CSV (*.csv)" if TEM_XLSX else "CSV (*.csv)"
EXTENSAO_PADRAO = ".xlsx" if TEM_XLSX else ".csv"


def texto_da_celula(valor: object) -> str:
    """O que a célula tem, como texto, sem as sobras que o Excel costuma pôr.

    Número inteiro digitado num campo de texto (um CEP, um telefone) chega
    aqui como float: `30140002.0` vira "30140002", e não "30140002.0".
    """
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "Sim" if valor else "Não"
    if isinstance(valor, float) and valor.is_integer():
        return str(int(valor))
    if isinstance(valor, Decimal):
        return texto_da_celula(float(valor))
    if isinstance(valor, datetime):
        return valor.strftime("%d/%m/%Y")
    if isinstance(valor, date):
        return valor.strftime("%d/%m/%Y")
    return str(valor).strip()


def ler(caminho: str | Path) -> list[list[str]]:
    """Lê a primeira aba (ou o arquivo inteiro, no csv) como linhas de texto."""
    caminho = Path(caminho)
    if caminho.suffix.lower() == ".csv":
        return _ler_csv(caminho)
    if not TEM_XLSX:
        raise ValueError(
            "Este computador não tem a biblioteca de Excel instalada. "
            "Salve a planilha como .csv e tente de novo."
        )
    return _ler_xlsx(caminho)


def _ler_xlsx(caminho: Path) -> list[list[str]]:
    livro = openpyxl.load_workbook(caminho, data_only=True, read_only=True)
    try:
        aba = livro.worksheets[0]
        return [
            [texto_da_celula(celula) for celula in linha]
            for linha in aba.iter_rows(values_only=True)
        ]
    finally:
        livro.close()


def _ler_csv(caminho: Path) -> list[list[str]]:
    # utf-8-sig engole o BOM que o Excel grava; latin-1 é o plano B de quem
    # salvou como "CSV (separado por vírgulas)" no Windows.
    for codificacao in ("utf-8-sig", "latin-1"):
        try:
            bruto = caminho.read_text(encoding=codificacao)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover - latin-1 aceita qualquer byte
        raise ValueError("Não consegui ler o arquivo: codificação desconhecida.")

    amostra = bruto[:4096]
    separador = ";" if amostra.count(";") >= amostra.count(",") else ","
    leitor = csv.reader(bruto.splitlines(), delimiter=separador)
    return [[celula.strip() for celula in linha] for linha in leitor]


def escrever_csv(caminho: str | Path, linhas: list[list[str]]) -> None:
    """Grava do jeito que o Excel em português abre com um duplo clique."""
    with open(caminho, "w", encoding="utf-8-sig", newline="") as arquivo:
        csv.writer(arquivo, delimiter=";").writerows(linhas)
