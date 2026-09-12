#!/usr/bin/env python3
"""Prova l'app INSTALLATA: quanto ci mette la barra a comparire dopo ⌘S, e
regge otto registrazioni di fila senza piantarsi?

    .venv/bin/python prova-bundle.py      # ad app APERTA (è lei che si prova)

Non guarda il codice: guarda le finestre vere sullo schermo (CGWindowList) e il
diario. Se il thread principale si blocca, la finestra non compare e si vede.
È il banco che ha smascherato le due cose del 12/9: la barra che arrivava dieci
secondi dopo ⌘S, e il deadlock di PortAudio («registro…» nel diario senza
nessun «microfono aperto» dietro). Riferimento: 243 ms alla prima comparsa,
8 aperture su 8.
"""
import subprocess
import sys
import time
from pathlib import Path

import Quartz

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scorciatoia import analizza  # noqa: E402

LOG = Path(__file__).resolve().parent / "dettatura.log"


def premi(spec="<cmd>+s"):
    tasto, mods = analizza(spec)
    flags = Quartz.kCGEventFlagMaskCommand if mods & 0x0100 else 0
    src = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
    for giu in (True, False):
        e = Quartz.CGEventCreateKeyboardEvent(src, tasto, giu)
        Quartz.CGEventSetFlags(e, flags)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, e)
        time.sleep(0.04)


def barra_a_video():
    """La capsula è sullo schermo? (lo status item è alto 24: si esclude)"""
    for w in Quartz.CGWindowListCopyWindowInfo(
            Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID):
        if w.get("kCGWindowOwnerName") != "Dettatura":
            continue
        b = w.get("kCGWindowBounds", {})
        if b.get("Height", 0) >= 35 and b.get("Width", 0) >= 150:
            return (round(b["X"]), round(b["Y"]), round(b["Width"]), round(b["Height"]))
    return None


def attendi_barra(limite=6.0):
    t0 = time.time()
    while time.time() - t0 < limite:
        b = barra_a_video()
        if b:
            return time.time() - t0, b
        time.sleep(0.02)
    return None, None


def main():
    if not subprocess.run(["pgrep", "-f", "Dettatura.app/Contents/MacOS"],
                          capture_output=True).stdout.strip():
        print("🔴 l'app non gira")
        return 1
    righe_prima = len(LOG.read_text(encoding="utf-8").splitlines())
    esito = []

    for giro in range(1, 9):
        print(f"\n— registrazione {giro} —")
        premi()
        t, b = attendi_barra()
        if t is None:
            print("  🔴 la barra NON è comparsa entro 6 s: thread principale bloccato?")
            esito.append(False)
            break
        print(f"  ok  barra a video dopo {t * 1000:.0f} ms   {b}")
        esito.append(t < 1.0)
        if giro == 1:
            time.sleep(0.7)
            subprocess.run(["screencapture", "-x", "/tmp/dettatura-registra.png"])
        time.sleep(1.6)
        premi()                      # ferma
        time.sleep(2.2)              # lascia finire l'avviso «non ho sentito»

    print("\n— il diario —")
    righe = LOG.read_text(encoding="utf-8").splitlines()[righe_prima:]
    for r in righe:
        print("   ", r)

    apri = sum("microfono aperto" in r for r in righe)
    print(f"\n  aperture del microfono riuscite: {apri} su 8")
    ok = all(esito) and len(esito) == 8 and apri == 8
    print("\n✅ regge" if ok else "\n🔴 qualcosa non torna")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
