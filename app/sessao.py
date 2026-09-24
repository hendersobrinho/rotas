"""Quem está usando o sistema agora, e o 'continuar conectado' deste computador.

O usuário logado fica em memória durante a execução; o token do 'continuar
conectado' fica num arquivo do próprio usuário do sistema operacional, com
permissão de leitura só para ele.
"""

from __future__ import annotations

import json
import os
import socket
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class UsuarioLogado:
    id: int
    nome: str
    login: str


_atual: UsuarioLogado | None = None


def definir_usuario(usuario: UsuarioLogado | None) -> None:
    global _atual
    _atual = usuario


def usuario_atual() -> UsuarioLogado | None:
    return _atual


def id_atual() -> int | None:
    return _atual.id if _atual else None


def nome_atual() -> str:
    return _atual.nome if _atual else "Sistema"


def nome_da_maquina() -> str:
    try:
        return socket.gethostname()[:120]
    except OSError:
        return "desconhecida"


def caminho_do_arquivo() -> Path:
    """~/.local/share/rotas/sessao.json (ou o equivalente em XDG_DATA_HOME)."""
    base = os.environ.get("ROTAS_DIR_DADOS") or os.environ.get("XDG_DATA_HOME")
    raiz = Path(base) if base else Path.home() / ".local" / "share"
    return raiz / "rotas" / "sessao.json"


def salvar_token(login: str, token: str) -> None:
    """Grava o token só para este usuário do computador (permissão 0600)."""
    arquivo = caminho_do_arquivo()
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(
        json.dumps({"login": login, "token": token}), encoding="utf-8"
    )
    try:
        arquivo.chmod(0o600)
    except OSError:
        pass


def ler_token() -> tuple[str, str] | None:
    arquivo = caminho_do_arquivo()
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        return str(dados["login"]), str(dados["token"])
    except (OSError, ValueError, KeyError):
        return None


def limpar_token() -> None:
    try:
        caminho_do_arquivo().unlink()
    except OSError:
        pass
