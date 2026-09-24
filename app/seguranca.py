"""Hash de senha e tokens de sessão, só com a biblioteca padrão."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from base64 import b64decode, b64encode

ALGORITMO = "pbkdf2_sha256"
ITERACOES = 240_000
TAMANHO_SAL = 16


def gerar_hash(senha: str, iteracoes: int = ITERACOES) -> str:
    """Devolve 'pbkdf2_sha256$iterações$sal$hash', tudo em base64."""
    if not senha:
        raise ValueError("A senha não pode ficar em branco.")
    sal = secrets.token_bytes(TAMANHO_SAL)
    derivado = hashlib.pbkdf2_hmac("sha256", senha.encode(), sal, iteracoes)
    return "$".join(
        [ALGORITMO, str(iteracoes), b64encode(sal).decode(), b64encode(derivado).decode()]
    )


def conferir(senha: str, guardado: str) -> bool:
    """Compara em tempo constante, para não vazar a senha pelo relógio."""
    try:
        algoritmo, iteracoes, sal_b64, hash_b64 = guardado.split("$")
        if algoritmo != ALGORITMO:
            return False
        derivado = hashlib.pbkdf2_hmac(
            "sha256", senha.encode(), b64decode(sal_b64), int(iteracoes)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(derivado, b64decode(hash_b64))


def gerar_token() -> str:
    """Token que fica no computador do usuário (o banco guarda só o hash)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
