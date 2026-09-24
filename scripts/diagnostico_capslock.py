"""Mostra o que cada caminho de leitura do Caps Lock está respondendo.

Rode, aperte a tecla Caps Lock algumas vezes e veja as colunas mudarem:

    .venv/bin/python scripts/diagnostico_capslock.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ui.teclado import PADRAO_LEDS, caps_lock_ligado, fontes  # noqa: E402


def rotulo(valor: bool | None) -> str:
    if valor is None:
        return "não responde"
    return "LIGADO " if valor else "desligado"


def main() -> int:
    leds = sorted(Path("/sys/class/leds").glob(PADRAO_LEDS))
    print("LEDs de Caps Lock encontrados:", len(leds))
    for led in leds:
        print("  ", led)
    print("\nAperte Caps Lock algumas vezes. Ctrl+C encerra.\n")
    print(f"{'kernel (LED)':<16}{'servidor X':<16}{'resultado':<16}")
    print("-" * 48)

    anterior = None
    try:
        while True:
            atual = fontes()
            linha = (
                f"{rotulo(atual['led']):<16}"
                f"{rotulo(atual['x11']):<16}"
                f"{rotulo(caps_lock_ligado()):<16}"
            )
            if linha != anterior:
                print(linha, flush=True)
                anterior = linha
            time.sleep(0.2)
    except KeyboardInterrupt:
        print("\nfim")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
