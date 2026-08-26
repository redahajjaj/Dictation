#!/usr/bin/env python3
"""
Prova la barra sull'app VERA: avvia Dettatura, aspetta che macOS pianti l'icona
nella barra dei menu, apre la barra e controlla che esca davvero da sotto
l'icona. Niente microfono, niente Groq: si guarda solo la finestra.

    ./.venv/bin/python prova-viva.py

Perché serve, oltre a `prova-barra.py`: lì l'icona non esiste e la barra si
piazza al ripiego. Qui l'ancora è quella vera — e macOS la piazza fra 0,5 e 1,6
secondi dopo l'avvio, non subito.
"""
import os
import subprocess
import sys
from pathlib import Path

from AppKit import NSScreen, NSTimer

import pannello as P
from dettatura import App

SCATTI = Path(__file__).resolve().parent / ".scratch" / "barra-liquid-glass" / "prototipo" / "barra-vera"
MEDIO = "Per Acmelux dobbiamo ancora decidere il corriere"

errori = []
passi = []


def controlla(nome, condizione, dettaglio=""):
    if condizione:
        print(f"  ok   {nome}   {dettaglio}")
    else:
        print(f"  NO   {nome}   {dettaglio}")
        errori.append(nome)


def scatta(nome, r):
    """La regione attorno alla barra, in coordinate Quartz (origine in alto)."""
    sf = NSScreen.screens()[0].frame()
    x = int(r.origin.x) - 60
    y = int(sf.size.height - (r.origin.y + r.size.height)) - 60
    SCATTI.mkdir(parents=True, exist_ok=True)
    subprocess.run(["screencapture", "-x", "-R",
                    f"{x},{y},{int(r.size.width) + 120},{int(r.size.height) + 120}",
                    str(SCATTI / f"{nome}.png")], check=True)


def prova(app):
    p = app._crea_pannello()
    icona = p._ancora_icona()
    controlla("l'icona è al suo posto", icona is not None,
              "" if icona is None else f"x={round(icona.origin.x)}")
    if icona is None:
        return

    app.alterna_pannello()
    yield 0.8                      # un giro di run loop: se no la foto è vuota

    f = p.finestra.frame()
    controlla("la barra è aperta", p.e_aperto(), f"{round(f.size.width)}x{round(f.size.height)}")
    controlla("centrata sotto l'icona",
              abs((f.origin.x + f.size.width / 2)
                  - (icona.origin.x + icona.size.width / 2)) <= 2,
              f"barra {round(f.origin.x + f.size.width / 2)} · "
              f"icona {round(icona.origin.x + icona.size.width / 2)}")
    controlla("staccata di 6 punti",
              abs((icona.origin.y - (f.origin.y + f.size.height)) - P.STACCO_ICONA) <= 1,
              f"{round(icona.origin.y - (f.origin.y + f.size.height))}")
    scatta("viva-1-nocciola", f)

    # arriva il testo: la barra si distende, ma il bordo alto non si muove
    alto_prima = f.origin.y + f.size.height
    p.apri(MEDIO)
    yield 0.8
    f2 = p.finestra.frame()
    controlla("col testo si distende",
              round(f2.size.height) == P.DIST_A and round(f2.size.width) > round(f.size.width),
              f"{round(f2.size.width)}x{round(f2.size.height)}")
    controlla("distendendosi il bordo alto non si muove",
              abs((f2.origin.y + f2.size.height) - alto_prima) <= 1,
              f"{round(alto_prima)} → {round(f2.origin.y + f2.size.height)}")
    scatta("viva-2-distesa", f2)

    # chiusa e riaperta senza averla trascinata: torna sotto l'icona
    p.chiudi()
    yield 0.4
    controlla("chiusa", not p.e_aperto())
    app.alterna_pannello()
    yield 0.8
    f3 = p.finestra.frame()
    controlla("riaperta: di nuovo sotto l'icona",
              abs((f3.origin.x + f3.size.width / 2)
                  - (icona.origin.x + icona.size.width / 2)) <= 2,
              f"{round(f3.origin.x + f3.size.width / 2)}")
    scatta("viva-3-riaperta", f3)


def main():
    app = App()
    passo = {"gen": None, "attesa": 1.8}

    def battito(_t):
        if passo["attesa"] > 0:
            passo["attesa"] -= 0.2
            return
        if passo["gen"] is None:
            print("\n— la barra sull'app vera —")
            passo["gen"] = prova(app)
        try:
            passo["attesa"] = next(passo["gen"])
        except StopIteration:
            print()
            if errori:
                print(f"🔴 {len(errori)} controlli falliti: " + ", ".join(errori))
            else:
                print(f"✅ tutti i controlli passati · scatti in {SCATTI}")
            sys.stdout.flush()      # os._exit non passa dai buffer di Python
            os._exit(1 if errori else 0)

    NSTimer.scheduledTimerWithTimeInterval_repeats_block_(0.2, True, battito)
    app.run()


if __name__ == "__main__":
    sys.exit(main())
