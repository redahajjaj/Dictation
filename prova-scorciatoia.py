#!/usr/bin/env python3
"""Banco di prova della scorciatoia: la combinazione del .env ARRIVA davvero?

Registra la scorciatoia con scorciatoia.py dentro un run loop nudo, poi manda
un ⌘S sintetico e conta quante volte scatta. È la prova che mancava per tre
sessioni: «is_alive()» e «permesso concesso» dicevano sì mentre i tasti non
arrivavano. Qui si verifica l'EFFETTO.

    .venv/bin/python prova-scorciatoia.py          # prova la combinazione del .env
    .venv/bin/python prova-scorciatoia.py '<cmd>+<shift>+d'

Da lanciare con l'app CHIUSA (./ferma.sh): due processi possono registrare la
stessa combinazione, e l'evento andrebbe a uno solo dei due.
Serve che il terminale possa «inviare eventi» (Warp lo può): la pressione
sintetica è un CGEventPost.
"""
import subprocess
import sys
import threading
import time
from pathlib import Path

import Quartz
from AppKit import NSAnyEventMask, NSApplication, NSDefaultRunLoopMode
from Foundation import NSDate

sys.path.insert(0, str(Path(__file__).resolve().parent))
from scorciatoia import Scorciatoie, _TASTI, analizza   # noqa: E402


def _leggi_env() -> str:
    env = Path(__file__).resolve().parent / ".env"
    if env.exists():
        for riga in env.read_text(encoding="utf-8").splitlines():
            if riga.strip().startswith("DETTATURA_HOTKEY="):
                return riga.split("=", 1)[1].strip().strip("\"'")
    return "<cmd>+s"


def _premi(spec: str) -> None:
    """Simula la combinazione: modificatori giù, tasto giù/su, modificatori su."""
    tasto, mods = analizza(spec)
    # Carbon → CGEvent: cmd 0x100→Command, shift 0x200→Shift, alt 0x800→Alternate, ctrl 0x1000→Control
    flags = 0
    if mods & 0x0100:
        flags |= Quartz.kCGEventFlagMaskCommand
    if mods & 0x0200:
        flags |= Quartz.kCGEventFlagMaskShift
    if mods & 0x0800:
        flags |= Quartz.kCGEventFlagMaskAlternate
    if mods & 0x1000:
        flags |= Quartz.kCGEventFlagMaskControl
    src = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)

    def manda(e, f):
        Quartz.CGEventSetFlags(e, f)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, e)
        time.sleep(0.04)

    manda(Quartz.CGEventCreateKeyboardEvent(src, tasto, True), flags)
    manda(Quartz.CGEventCreateKeyboardEvent(src, tasto, False), flags)


def main() -> int:
    spec = sys.argv[1] if len(sys.argv) > 1 else _leggi_env()
    scattata = []
    app = NSApplication.sharedApplication()
    sc = Scorciatoie()
    problema = sc.registra(spec, lambda: scattata.append(round(time.time(), 2)))
    print(f"combinazione : {spec}")
    print(f"registrazione: {'ok' if problema is None else problema}")
    if problema:
        return 1

    def dopo():
        # Finder davanti: se la scorciatoia NON scattasse, il tasto andrebbe a
        # lui, che con ⌘S non fa niente
        subprocess.run(["osascript", "-e", 'tell application "Finder" to activate'], capture_output=True)
        time.sleep(0.8)
        _premi(spec)
        time.sleep(0.8)
        _premi(spec)

    threading.Thread(target=dopo, daemon=True).start()
    fine = time.time() + 3.5
    while time.time() < fine:
        ev = app.nextEventMatchingMask_untilDate_inMode_dequeue_(
            NSAnyEventMask, NSDate.dateWithTimeIntervalSinceNow_(0.1), NSDefaultRunLoopMode, True
        )
        if ev is not None:
            app.sendEvent_(ev)
    subprocess.run(["osascript", "-e", 'tell application "Warp" to activate'], capture_output=True)
    sc.togli_tutte()
    print(f"scattata     : {len(scattata)} volte su 2")
    return 0 if len(scattata) == 2 else 1


if __name__ == "__main__":
    sys.exit(main())
