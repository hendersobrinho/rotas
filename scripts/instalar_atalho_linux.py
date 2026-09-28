"""Coloca o programa no menu e na área de trabalho do Linux.

    python scripts/instalar_atalho_linux.py
    python scripts/instalar_atalho_linux.py --remover

Instala os ícones no tema do sistema (~/.local/share/icons/hicolor), em todos
os tamanhos, mais o vetorial em `scalable` — assim o ambiente sempre acha uma
versão nítida, por maior que seja o ícone que ele queira desenhar.

No Windows quem faz esse papel é o instalador (ver instalador/rotas.iss); aqui
o atalho aponta para o Python do .venv e para o main.py deste diretório.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
RECURSOS = RAIZ / "app" / "recursos"
PASTA_PNG = RECURSOS / "icones"

NOME_ICONE = "rotas"          # o mesmo nome vai no Icon= do .desktop
ARQUIVO = "rotas.desktop"
# Curto, que é o que cabe embaixo de um ícone; o nome por extenso fica no
# Comment, que é o que o ambiente mostra ao passar o mouse.
TITULO = "MRotas"
DESCRICAO = "Agenda do motoboy — coletas e retiradas"

DADOS = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
ATALHOS = DADOS / "applications"
HICOLOR = DADOS / "icons" / "hicolor"


def _interpretador() -> Path:
    """O Python do ambiente virtual do projeto, com o do sistema como reserva."""
    for candidato in (RAIZ / ".venv" / "bin" / "python", Path(sys.executable)):
        if candidato.exists():
            return candidato
    return Path("python3")


def _area_de_trabalho() -> Path | None:
    """Onde fica a Área de Trabalho deste usuário, se ela existir."""
    try:
        saida = subprocess.run(
            ["xdg-user-dir", "DESKTOP"], capture_output=True, text=True, check=True
        ).stdout.strip()
        if saida:
            pasta = Path(saida)
            if pasta.is_dir() and pasta != Path.home():
                return pasta
    except (OSError, subprocess.CalledProcessError):
        pass
    for nome in ("Área de trabalho", "Área de Trabalho", "Desktop"):
        pasta = Path.home() / nome
        if pasta.is_dir():
            return pasta
    return None


def _texto_do_atalho() -> str:
    return "\n".join([
        "[Desktop Entry]",
        "Type=Application",
        "Version=1.0",
        f"Name={TITULO}",
        f"Comment={DESCRICAO}",
        f"Exec={_interpretador()} {RAIZ / 'main.py'}",
        f"Path={RAIZ}",
        f"Icon={NOME_ICONE}",
        "Terminal=false",
        "Categories=Office;",
        # Amarra a janela ao atalho: sem isso a barra de tarefas mostra um
        # ícone genérico ao lado do lançador. Casa com setDesktopFileName().
        "StartupWMClass=rotas",
        "StartupNotify=true",
        "",
    ])


def instalar() -> int:
    if not PASTA_PNG.is_dir():
        raise SystemExit("rode antes: python scripts/gerar_icones.py")

    for origem in sorted(PASTA_PNG.glob("rotas-*.png")):
        lado = origem.stem.split("-")[-1]
        destino = HICOLOR / f"{lado}x{lado}" / "apps"
        destino.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origem, destino / f"{NOME_ICONE}.png")

    # Em `scalable` vai a versão quadrada: o tema de ícones espera quadrado, e
    # o desenho original é deitado.
    vetorial = HICOLOR / "scalable" / "apps"
    vetorial.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(PASTA_PNG / "rotas.svg", vetorial / f"{NOME_ICONE}.svg")

    ATALHOS.mkdir(parents=True, exist_ok=True)
    atalho = ATALHOS / ARQUIVO
    atalho.write_text(_texto_do_atalho(), encoding="utf-8")
    atalho.chmod(0o755)
    print(f"atalho: {atalho}")

    mesa = _area_de_trabalho()
    if mesa is not None:
        copia = mesa / ARQUIVO
        shutil.copyfile(atalho, copia)
        copia.chmod(0o755)
        # O GNOME só abre o atalho da mesa depois de marcado como confiável.
        subprocess.run(
            ["gio", "set", str(copia), "metadata::trusted", "true"], check=False
        )
        print(f"área de trabalho: {copia}")

    _avisar_o_sistema()
    return 0


def remover() -> int:
    for caminho in (ATALHOS / ARQUIVO, (_area_de_trabalho() or Path("/dev/null")) / ARQUIVO):
        if caminho.is_file():
            caminho.unlink()
            print(f"removido: {caminho}")
    for icone in HICOLOR.glob(f"*/apps/{NOME_ICONE}.*"):
        icone.unlink()
        print(f"removido: {icone}")
    _avisar_o_sistema()
    return 0


def _avisar_o_sistema() -> None:
    """Pede para o ambiente reler o menu e o tema de ícones."""
    subprocess.run(["update-desktop-database", str(ATALHOS)], check=False,
                   capture_output=True)
    subprocess.run(["gtk-update-icon-cache", "-f", "-t", str(HICOLOR)], check=False,
                   capture_output=True)


def main() -> int:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument("--remover", action="store_true",
                            help="tira o atalho e os ícones instalados")
    argumentos = analisador.parse_args()
    return remover() if argumentos.remover else instalar()


if __name__ == "__main__":
    raise SystemExit(main())
