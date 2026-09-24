"""Leitura e gravação das configurações de conexão, no arquivo .env."""

from __future__ import annotations

import os
from pathlib import Path

ARQUIVO = Path(__file__).resolve().parents[1] / ".env"

CAMPOS = {
    "host": ("ROTAS_DB_HOST", "localhost"),
    "porta": ("ROTAS_DB_PORT", "5432"),
    "banco": ("ROTAS_DB_NAME", "rotas"),
    "usuario": ("ROTAS_DB_USER", "postgres"),
    "senha": ("ROTAS_DB_PASSWORD", ""),
}
CHAVE_URL = "ROTAS_DATABASE_URL"


def carregar_env() -> None:
    """Põe o .env no ambiente, sem passar por cima do que já está definido."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ARQUIVO)


def ler() -> dict[str, str]:
    """O que está valendo agora: ambiente, depois o .env, depois o padrão."""
    carregar_env()
    return {
        nome: os.environ.get(chave, padrao)
        for nome, (chave, padrao) in CAMPOS.items()
    }


def url_completa() -> str | None:
    """Se alguém definiu a URL inteira, ela manda em tudo."""
    return os.environ.get(CHAVE_URL) or None


def _linhas_existentes() -> list[str]:
    try:
        return ARQUIVO.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []


def salvar(dados: dict[str, str]) -> Path:
    """Grava no .env preservando o que não é conexão, e aplica no processo."""
    valores = {CAMPOS[nome][0]: (dados.get(nome) or "").strip() for nome in CAMPOS}

    guardadas = set()
    saida: list[str] = []
    for linha in _linhas_existentes():
        nua = linha.strip()
        if not nua or nua.startswith("#") or "=" not in nua:
            saida.append(linha)
            continue
        chave = nua.split("=", 1)[0].strip()
        if chave == CHAVE_URL:
            # A URL inteira tem precedência: guardada como comentário para não
            # anular silenciosamente o que a tela acabou de gravar.
            saida.append(f"# {linha}")
            continue
        if chave in valores:
            saida.append(f"{chave}={valores[chave]}")
            guardadas.add(chave)
        else:
            saida.append(linha)

    faltando = [c for c in valores if c not in guardadas]
    if faltando:
        if saida and saida[-1].strip():
            saida.append("")
        saida.append("# Conexão com o PostgreSQL")
        saida.extend(f"{chave}={valores[chave]}" for chave in faltando)

    ARQUIVO.parent.mkdir(parents=True, exist_ok=True)
    ARQUIVO.write_text("\n".join(saida).rstrip() + "\n", encoding="utf-8")
    try:
        ARQUIVO.chmod(0o600)
    except OSError:
        pass

    os.environ.pop(CHAVE_URL, None)
    for chave, valor in valores.items():
        os.environ[chave] = valor
    return ARQUIVO


def testar(dados: dict[str, str]) -> str:
    """Tenta conectar e devolve a versão do servidor; levanta se não der."""
    from urllib.parse import quote_plus

    from sqlalchemy import create_engine, text

    usuario = quote_plus((dados.get("usuario") or "").strip())
    senha = quote_plus(dados.get("senha") or "")
    credenciais = usuario if not senha else f"{usuario}:{senha}"
    url = (
        f"postgresql+psycopg://{credenciais}@{dados.get('host') or 'localhost'}"
        f":{dados.get('porta') or '5432'}/{dados.get('banco') or 'rotas'}"
    )
    motor = create_engine(url, connect_args={"connect_timeout": 5})
    try:
        with motor.connect() as conexao:
            versao = conexao.execute(text("select version()")).scalar() or ""
    finally:
        motor.dispose()
    return versao.split(" on ")[0]
