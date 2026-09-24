"""Estado do Caps Lock, para avisar antes de o usuário errar a senha.

O Qt não expõe o Caps Lock como modificador, então o estado é procurado em
três lugares, nesta ordem:

1. o LED do teclado no sysfs (`/sys/class/leds/*capslock*/brightness`), que o
   próprio kernel mantém pelo gatilho `kbd-capslock` — funciona no Wayland, no
   X11 e no console;
2. o servidor X (XKB), para quem roda em X11;
3. a dedução pela tecla digitada, quando nenhum dos dois responde.

O caminho do X sozinho não basta: rodando como cliente Wayland nativo, ele
consulta o XWayland, cujo estado de teclado só muda quando uma janela X11 tem
o foco — e aí o aviso nunca aparecia.
"""

from __future__ import annotations

import ctypes
import ctypes.util
from pathlib import Path

PADRAO_LEDS = "*capslock*/brightness"
_PASTA_LEDS = Path("/sys/class/leds")

_XKB_USE_CORE_KBD = 0x0100
_carregado = False
_x11 = None
_display = None
_leds: list[Path] | None = None


# --------------------------------------------------------------- pelo kernel
def _procurar_leds() -> list[Path]:
    """Um LED por teclado ligado; qualquer um aceso significa Caps Lock."""
    try:
        return sorted(_PASTA_LEDS.glob(PADRAO_LEDS))
    except OSError:
        return []


def caps_lock_pelo_led() -> bool | None:
    global _leds
    if not _leds:
        _leds = _procurar_leds()
    if not _leds:
        return None

    achou = False
    for led in list(_leds):
        try:
            if led.read_text().strip() not in ("", "0"):
                return True
            achou = True
        except OSError:
            # Teclado desconectado: refaz a lista na próxima chamada.
            _leds = None
    return False if achou else None


# ------------------------------------------------------------------- pelo X
def _preparar_x11() -> None:
    """Abre a conexão com o X uma única vez; se não der, desiste em silêncio."""
    global _carregado, _x11, _display
    if _carregado:
        return
    _carregado = True
    try:
        nome = ctypes.util.find_library("X11")
        if not nome:
            return
        biblioteca = ctypes.cdll.LoadLibrary(nome)
        biblioteca.XOpenDisplay.restype = ctypes.c_void_p
        biblioteca.XOpenDisplay.argtypes = [ctypes.c_char_p]
        display = biblioteca.XOpenDisplay(None)
        if not display:
            return
        _x11, _display = biblioteca, display
    except Exception:
        _x11 = _display = None


def caps_lock_pelo_x11() -> bool | None:
    _preparar_x11()
    if _x11 is None or _display is None:
        return None
    try:
        estado = ctypes.c_uint(0)
        resultado = _x11.XkbGetIndicatorState(
            ctypes.c_void_p(_display), ctypes.c_uint(_XKB_USE_CORE_KBD),
            ctypes.byref(estado),
        )
        if resultado != 0:
            return None
        return bool(estado.value & 1)  # bit 0 do indicador é o Caps Lock
    except Exception:
        return None


# ------------------------------------------------------------------ fachada
def caps_lock_ligado() -> bool | None:
    """True/False quando dá para saber; None quando não há como perguntar."""
    pelo_led = caps_lock_pelo_led()
    if pelo_led is not None:
        return pelo_led
    return caps_lock_pelo_x11()


def fontes() -> dict[str, bool | None]:
    """O que cada caminho respondeu — usado pelo script de diagnóstico."""
    return {"led": caps_lock_pelo_led(), "x11": caps_lock_pelo_x11()}


def inferir_do_evento(texto: str, com_shift: bool) -> bool | None:
    """Deduz pelo caractere digitado: letra maiúscula sem Shift = Caps ligado."""
    if len(texto) != 1 or not texto.isalpha():
        return None
    if texto.isupper():
        return not com_shift
    if texto.islower():
        return com_shift
    return None
