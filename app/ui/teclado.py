"""Estado do Caps Lock, para avisar antes de o usuário errar a senha.

O Qt não expõe o Caps Lock como modificador, então há dois caminhos:

1. perguntar ao servidor gráfico (XKB, via libX11 — funciona também no Wayland
   por causa do XWayland);
2. deduzir pela tecla digitada, quando o primeiro caminho não está disponível.
"""

from __future__ import annotations

import ctypes
import ctypes.util

_XKB_USE_CORE_KBD = 0x0100
_carregado = False
_x11 = None
_display = None


def _preparar() -> None:
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


def caps_lock_ligado() -> bool | None:
    """True/False quando dá para saber; None quando não há como perguntar."""
    _preparar()
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


def inferir_do_evento(texto: str, com_shift: bool) -> bool | None:
    """Deduz pelo caractere digitado: letra maiúscula sem Shift = Caps ligado."""
    if len(texto) != 1 or not texto.isalpha():
        return None
    if texto.isupper():
        return not com_shift
    if texto.islower():
        return com_shift
    return None
