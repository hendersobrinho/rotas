"""Gera os ícones do programa a partir de `app/recursos/icone.svg`.

    python scripts/gerar_icones.py

Sai daqui:
  * `app/recursos/rotas.ico` — usado pelo PyInstaller e pelo Inno Setup, com
    todos os tamanhos que o Windows pede (do 16 da barra ao 256 da área de
    trabalho em telas grandes).
  * `app/recursos/icones/rotas-<lado>.png` — os mesmos tamanhos soltos, que o
    Linux instala em ~/.local/share/icons (ver instalar_atalho_linux.py).
  * `app/recursos/icones/rotas.svg` — o mesmo desenho num quadrado, para a
    pasta `scalable` do tema de ícones, que espera ícones quadrados.
  * `instalador/icone.ico` — o ícone do **instalador**, que é outro desenho e
    não tem nada a ver com o do programa: quem clica nele está instalando, não
    abrindo a agenda. Fica em `instalador/`, e não em `app/recursos/`, porque
    não é recurso de execução — não tem por que viajar dentro do .exe.

Quem desenha é `app.ui.marca.imagem_icone()` — o mesmo desenho que o programa
usa na janela, para o atalho e a barra de tarefas nunca saírem diferentes.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")  # roda sem tela aberta

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.ui import marca  # noqa: E402

RAIZ = Path(__file__).resolve().parents[1]
RECURSOS = RAIZ / "app" / "recursos"
PASTA_PNG = RECURSOS / "icones"

# O Windows escolhe entre estes; sem o tamanho certo ele estica outro e borra.
TAMANHOS_ICO = (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)
# O Linux guarda um por pasta do hicolor; 512 cobre as telas de alta densidade.
TAMANHOS_PNG = (16, 22, 24, 32, 48, 64, 128, 256, 512)

# O ícone do instalador vem de um PNG de 96 px, e não de um vetor: daí o teto.
# Passar disso seria ampliar, e o Windows amplia igual sozinho quando não acha
# o tamanho — com a vantagem de não inchar o arquivo com borrão.
INSTALADOR_PNG = RAIZ / "instalador" / "icone.png"
TAMANHOS_INSTALADOR = (16, 20, 24, 32, 40, 48, 64, 96)


def svg_quadrado() -> str:
    """O desenho deitado centralizado num quadrado, sem mexer no traçado.

    O tema de ícones do Linux guarda um vetorial em `scalable`, e espera que
    ele seja quadrado; entregar o deitado direto deixaria o ambiente livre para
    esticá-lo. Aqui o conteúdo é só deslocado dentro de uma moldura quadrada.
    """
    original = (RECURSOS / "icone.svg").read_text(encoding="utf-8")
    abertura = re.match(r"<svg\b[^>]*>", original)
    if abertura is None:
        raise SystemExit("não reconheci o <svg> de icone.svg")

    largura = float(re.search(r'width="([\d.]+)"', abertura.group(0)).group(1))
    altura = float(re.search(r'height="([\d.]+)"', abertura.group(0)).group(1))
    lado = max(largura, altura)
    dx = (lado - largura) / 2
    dy = (lado - altura) / 2

    miolo = original[abertura.end():].rsplit("</svg>", 1)[0]
    return (
        f'<svg width="{lado:g}" height="{lado:g}" viewBox="0 0 {lado:g} {lado:g}"'
        ' fill="none" xmlns="http://www.w3.org/2000/svg"'
        ' xmlns:xlink="http://www.w3.org/1999/xlink">\n'
        f'<g transform="translate({dx:g} {dy:g})">{miolo}</g>\n</svg>\n'
    )


def icone_do_instalador() -> Path:
    """O .ico do instalador, montado a partir de `instalador.png`.

    Cada tamanho é reduzido do original com Lanczos, que é o que mantém os
    contornos limpos nos pequenos; nenhum é ampliado.
    """
    original = Image.open(INSTALADOR_PNG).convert("RGBA")
    if original.width != original.height:
        raise SystemExit(f"{INSTALADOR_PNG.name} precisa ser quadrado")

    uteis = [lado for lado in TAMANHOS_INSTALADOR if lado <= original.width]
    quadros = [
        original if lado == original.width
        else original.resize((lado, lado), Image.LANCZOS)
        for lado in uteis
    ]
    destino = INSTALADOR_PNG.with_suffix(".ico")
    quadros[-1].save(
        destino, format="ICO",
        sizes=[(lado, lado) for lado in uteis],
        append_images=quadros[:-1],
    )
    return destino


def main() -> int:
    QApplication(sys.argv)  # o QImage/QPainter precisam da aplicação de pé

    PASTA_PNG.mkdir(parents=True, exist_ok=True)
    caminhos: dict[int, Path] = {}
    for lado in sorted(set(TAMANHOS_ICO) | set(TAMANHOS_PNG)):
        destino = PASTA_PNG / f"rotas-{lado}.png"
        marca.imagem_icone(lado).save(str(destino))
        caminhos[lado] = destino
        print(f"  {destino.relative_to(RAIZ)}")

    # O .ico é montado com cada tamanho já desenhado, e não reduzido de um só,
    # para nenhum deles sair borrado.
    quadros = [Image.open(caminhos[lado]).convert("RGBA") for lado in TAMANHOS_ICO]
    maior = quadros[-1]  # o Pillow parte do maior e pega os outros de append_images
    destino_ico = RECURSOS / "rotas.ico"
    maior.save(
        destino_ico,
        format="ICO",
        sizes=[(lado, lado) for lado in TAMANHOS_ICO],
        append_images=quadros[:-1],
    )
    print(f"  {destino_ico.relative_to(RAIZ)}")

    destino_svg = PASTA_PNG / "rotas.svg"
    destino_svg.write_text(svg_quadrado(), encoding="utf-8")
    print(f"  {destino_svg.relative_to(RAIZ)}")

    print(f"  {icone_do_instalador().relative_to(RAIZ)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
