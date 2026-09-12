#!/usr/bin/env python3
"""Il clic fuori chiude la barra, il clic dentro no.

Il Dock sta in basso: si clicca a metà schermo, lontano da lui e dalla barra
(che sta in alto). Un mouseDown+mouseUp senza spostamento non trascina niente.
"""
import subprocess
import sys
import time
from pathlib import Path

import Quartz

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scorciatoia import analizza  # noqa: E402


def premi_scorciatoia():
    tasto, mods = analizza("<cmd>+s")
    flags = Quartz.kCGEventFlagMaskCommand if mods & 0x0100 else 0
    src = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
    for giu in (True, False):
        e = Quartz.CGEventCreateKeyboardEvent(src, tasto, giu)
        Quartz.CGEventSetFlags(e, flags)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, e)
        time.sleep(0.04)


def clic(x, y):
    src = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
    p = Quartz.CGPointMake(x, y)
    for tipo in (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp):
        e = Quartz.CGEventCreateMouseEvent(src, tipo, p, Quartz.kCGMouseButtonLeft)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, e)
        time.sleep(0.05)


def barra():
    for w in Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID):
        if w.get("kCGWindowOwnerName") != "Dettatura":
            continue
        b = w.get("kCGWindowBounds", {})
        if b.get("Height", 0) >= 35 and b.get("Width", 0) >= 150:
            return b
    return None


def main():
    esiti = []
    # apre la barra con ⌘S e la ferma subito: resta a video in riposo
    premi_scorciatoia(); time.sleep(1.0)
    premi_scorciatoia(); time.sleep(2.6)
    b = barra()
    print(f"barra a video: {b}")
    if not b:
        print("🔴 la barra non è a video: non posso provare i clic")
        return 1

    # 1. un clic DENTRO non deve chiuderla
    dentro_x = b["X"] + b["Width"] / 2
    dentro_y = b["Y"] + b["Height"] / 2
    clic(dentro_x, dentro_y)
    time.sleep(0.6)
    resta = barra() is not None
    print(f"  clic dentro ({dentro_x:.0f},{dentro_y:.0f}) → la barra {'resta' if resta else 'È SPARITA'}")
    esiti.append(resta)

    # 2. un clic FUORI la deve far sparire
    clic(700, 830)
    time.sleep(0.6)
    sparita = barra() is None
    print(f"  clic fuori  (700,830)  → la barra {'è sparita' if sparita else 'È ANCORA LÌ'}")
    esiti.append(sparita)

    print("\n✅ il clic fuori funziona" if all(esiti) else "\n🔴 no")
    return 0 if all(esiti) else 1


if __name__ == "__main__":
    sys.exit(main())
