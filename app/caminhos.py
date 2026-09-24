"""Onde ficam os arquivos, tanto rodando do código quanto empacotado.

Dentro de um executável o programa é só leitura e vive numa pasta temporária,
então configuração e sessão precisam morar na pasta do usuário do sistema.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP = "Rotas"
RAIZ = Path(__file__).resolve().parents[1]


def empacotado() -> bool:
    """True quando rodando a partir do executável gerado pelo PyInstaller."""
    return bool(getattr(sys, "frozen", False))


def _base_recursos() -> Path:
    """No executável, os arquivos ficam na pasta que o PyInstaller monta."""
    interno = getattr(sys, "_MEIPASS", None)
    return Path(interno) if interno else RAIZ


def recurso(*partes: str) -> Path:
    """Caminho de um arquivo embarcado, como o logotipo e as fontes."""
    return _base_recursos().joinpath("app", "recursos", *partes)


def _pasta(variavel: str, windows: str, xdg: str, padrao: str) -> Path:
    escolhida = os.environ.get(variavel)
    if escolhida:
        return Path(escolhida)
    if sys.platform.startswith("win"):
        base = os.environ.get(windows) or Path.home() / "AppData" / "Roaming"
        return Path(base) / APP
    base = os.environ.get(xdg) or Path.home() / padrao
    return Path(base) / APP.lower()


def pasta_config() -> Path:
    """Onde a conexão com o banco é guardada.

    Rodando do código com um .env ao lado, ele continua valendo — é o que
    permite desenvolver sem mexer na configuração do sistema.
    """
    if not empacotado() and (RAIZ / ".env").exists():
        return RAIZ
    return _pasta("ROTAS_DIR_CONFIG", "APPDATA", "XDG_CONFIG_HOME", ".config")


def pasta_dados() -> Path:
    """Onde fica o 'continuar conectado' deste computador."""
    return _pasta("ROTAS_DIR_DADOS", "LOCALAPPDATA", "XDG_DATA_HOME", ".local/share")


def garantir(pasta: Path) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta
