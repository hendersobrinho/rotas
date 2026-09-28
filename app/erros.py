"""Relato de falhas: o que quebra vai para um arquivo e aparece na tela.

Empacotado para Windows o programa roda sem console (`console=False` no
rotas.spec), e aí não existe para onde escrever: um erro antes da primeira
janela faz o processo abrir e sumir, sem nada na tela e sem nada no terminal.
Quem está do outro lado só vê "abriu e não apareceu".

Então todo erro não tratado passa a virar um bloco no `erro.log`, na mesma
pasta do "continuar conectado" (ver app/caminhos.py), e — quando o Qt já está
de pé — uma caixa dizendo o que houve e onde está o arquivo.
"""

from __future__ import annotations

import os
import platform
import sys
import traceback
from datetime import datetime
from pathlib import Path

from app import __version__, caminhos

ARQUIVO = "erro.log"
LIMITE_BYTES = 512 * 1024   # o arquivo não cresce sem fim


def caminho_do_log() -> Path:
    return caminhos.pasta_dados() / ARQUIVO


def saida_segura() -> None:
    """Dá a `print()` para onde escrever quando não há console.

    Sem console, `sys.stdout` e `sys.stderr` vêm como None e qualquer `print()`
    estoura um AttributeError — bem longe de onde está o problema de verdade.
    """
    for nome in ("stdout", "stderr"):
        if getattr(sys, nome, None) is None:
            setattr(sys, nome, open(os.devnull, "w", encoding="utf-8"))


def _cabecalho() -> str:
    try:
        from app.db import url_mascarada

        banco = url_mascarada()
    except Exception:
        banco = "(não deu para ler a configuração de conexão)"
    return (
        f"{datetime.now():%d/%m/%Y %H:%M:%S} · Rotas {__version__}\n"
        f"{platform.platform()} · Python {sys.version.split()[0]}"
        f" · {'empacotado' if caminhos.empacotado() else 'do código'}\n"
        f"banco: {banco}\n"
    )


def registrar(erro: BaseException, contexto: str = "") -> Path | None:
    """Anota a falha no arquivo. Devolve onde gravou, ou None se nem isso deu."""
    try:
        destino = caminho_do_log()
        caminhos.garantir(destino.parent)
        if destino.exists() and destino.stat().st_size > LIMITE_BYTES:
            destino.replace(destino.with_suffix(".log.anterior"))

        with open(destino, "a", encoding="utf-8") as arquivo:
            arquivo.write("\n" + "=" * 72 + "\n")
            arquivo.write(_cabecalho())
            if contexto:
                arquivo.write(f"{contexto}\n")
            arquivo.write("-" * 72 + "\n")
            traceback.print_exception(
                type(erro), erro, erro.__traceback__, file=arquivo
            )
        return destino
    except Exception:
        return None  # falhar ao relatar a falha não pode derrubar mais nada


def mostrar(erro: BaseException, destino: Path | None) -> None:
    """Avisa na tela, se houver tela. Fora isso, não faz nada."""
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        if QApplication.instance() is None:
            return
        onde = f"\n\nOs detalhes estão em:\n{destino}" if destino else ""
        QMessageBox.critical(
            None,
            "A Agenda do motoboy parou",
            f"{type(erro).__name__}: {erro}{onde}",
        )
    except Exception:
        pass


def relatar(erro: BaseException, contexto: str = "") -> None:
    mostrar(erro, registrar(erro, contexto))


def instalar() -> None:
    """Liga o relato para o que escapar de todo o resto."""
    saida_segura()

    anterior = sys.excepthook

    def gancho(tipo, valor, tracinho):
        relatar(valor, "erro não tratado")
        anterior(tipo, valor, tracinho)

    sys.excepthook = gancho
