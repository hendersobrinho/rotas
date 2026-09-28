"""A tela de Conexão vem antes de tentar o banco quando ninguém o apontou.

Também cobre o limite de espera: sem ele, um servidor que não responde prende
o programa antes da primeira janela — o processo abre e nada aparece.
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from comum import RAIZ, preparar_ambiente

preparar_ambiente()

from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

app = QApplication([])

from app import configuracao  # noqa: E402
from app.db import ESPERA_CONEXAO, get_engine, reiniciar  # noqa: E402
from app.ui.conexao_dialog import ConexaoDialog  # noqa: E402
from app.ui.estilo import CORES, aplicar_tema  # noqa: E402

aplicar_tema(app)

VARIAVEIS = (
    "ROTAS_DATABASE_URL", "ROTAS_DB_HOST", "ROTAS_DB_PORT",
    "ROTAS_DB_NAME", "ROTAS_DB_USER", "ROTAS_DB_PASSWORD",
)
SAIDA = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "testes" / ".saida"
SAIDA.mkdir(parents=True, exist_ok=True)


class MaquinaVirgem:
    """Computador onde o programa nunca rodou: nada no ambiente, nada gravado."""

    def __enter__(self):
        self._ambiente = {nome: os.environ.pop(nome, None) for nome in VARIAVEIS}
        self._arquivo = configuracao.ARQUIVO
        pasta = SAIDA / "config-virgem"
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / ".env").unlink(missing_ok=True)
        configuracao.ARQUIVO = pasta / ".env"
        return configuracao.ARQUIVO

    def __exit__(self, *_erro):
        configuracao.ARQUIVO = self._arquivo
        for nome in VARIAVEIS:
            os.environ.pop(nome, None)
        for nome, valor in self._ambiente.items():
            if valor is not None:
                os.environ[nome] = valor
        reiniciar()
        return False


def tarjas(dialogo: ConexaoDialog) -> dict[str, int]:
    """Quantas tarjas de cada cor a tela está mostrando."""
    contagem = {"vermelha": 0, "azul": 0}
    for etiqueta in dialogo.findChildren(QLabel):
        estilo = etiqueta.styleSheet()
        if CORES["vermelho_claro"] in estilo:
            contagem["vermelha"] += 1
        elif CORES["azul_claro"] in estilo:
            contagem["azul"] += 1
    return contagem


# ---- máquina virgem ------------------------------------------------------
with MaquinaVirgem() as arquivo:
    assert not arquivo.exists(), arquivo
    assert not configuracao.esta_configurado(), (
        "sem nada apontado, o programa acharia que está configurado e tentaria"
        " o postgres@localhost do padrão antes de mostrar qualquer tela"
    )
    print("ok máquina virgem: a tela de Conexão vem antes de tentar o banco")

    # a tarja é de orientação, não de erro: ninguém errou nada ainda
    dialogo = ConexaoDialog(None, orientacao="Primeiro acesso neste computador.")
    assert tarjas(dialogo) == {"vermelha": 0, "azul": 1}, tarjas(dialogo)
    dialogo.grab().save(str(SAIDA / "conexao_primeiro_acesso.png"))

    # e a de falha continua vermelha
    dialogo = ConexaoDialog(None, aviso="Não deu para falar com o banco.")
    assert tarjas(dialogo) == {"vermelha": 1, "azul": 0}, tarjas(dialogo)
    print("ok primeiro acesso mostra orientação; falha continua em vermelho")

    # depois de salvar, o programa passa a abrir direto
    configuracao.salvar({
        "host": "localhost", "porta": "5432",
        "banco": os.environ.get("ROTAS_BANCO_TESTE", "rotas_teste"),
        "usuario": os.environ.get("USER", "postgres"), "senha": "",
    })
    assert arquivo.exists(), arquivo
    assert configuracao.esta_configurado()
    print("ok depois de salvar, não pergunta mais")

# ---- máquina já configurada ---------------------------------------------
assert configuracao.esta_configurado(), "com o .env do projeto, tem de estar pronto"
print("ok máquina configurada: abre direto")

# ---- o limite de espera --------------------------------------------------
assert ESPERA_CONEXAO >= 2, ESPERA_CONEXAO  # o libpq recusa menos que isso
guardado = os.environ.get("ROTAS_DATABASE_URL")
os.environ["ROTAS_DATABASE_URL"] = (
    "postgresql+psycopg://u:s@10.255.255.1:5432/rotas"   # engole o pacote
)
reiniciar()
inicio = time.perf_counter()
try:
    get_engine().connect()
    raise AssertionError("conectou num endereço que não existe")
except AssertionError:
    raise
except Exception:
    decorrido = time.perf_counter() - inicio
assert decorrido < ESPERA_CONEXAO + 5, f"esperou {decorrido:.0f}s, demais"
print(f"ok servidor mudo desiste em {decorrido:.0f}s, e não prende o arranque")

if guardado is None:
    os.environ.pop("ROTAS_DATABASE_URL", None)
else:
    os.environ["ROTAS_DATABASE_URL"] = guardado
reiniciar()

print("TESTE CONEXAO OK")
