#!/usr/bin/env python3
"""Banco di prova del microfono in un processo a parte (microfono.py).

    .venv/bin/python prova-microfono.py

Usa il microfono VERO per pochi secondi (niente viene salvato né inviato):
serve che il terminale abbia il permesso Microfono. Prova le cose che il
diario del 22-26/9 ha mostrato rompersi:

1. dieci dettature di fila: ognuna si apre, consegna, e il figlio sparisce
2. il figlio che muore a metà dettatura: si riprende da solo, l'audio continua
3. un figlio che non apre mai (impiccato): si riprova, poi si dice «fallito»
4. il padre che muore di colpo: nessun figlio resta in vita col microfono
5. `elenca`: i microfoni come li vede un figlio appena nato
6. il microfono scelto dal menu: scollegato si ripiega, cambiato a metà si riapre
"""
import os
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI))

import microfono as M  # noqa: E402

COMANDO = M.comando_figlio(QUI / "dettatura.py")
esiti = []


def controlla(nome, ok, dettaglio=""):
    esiti.append(ok)
    print(f"  {'ok  ' if ok else 'NO  '} {nome}   {dettaglio}")


def figli_vivi():
    r = subprocess.run(["pgrep", "-f", "dettatura.py --microfono"], capture_output=True, text=True)
    return [int(x) for x in r.stdout.split()]


class Dettatura:
    """Quello che fa l'app: raccoglie l'audio e aspetta finito/fallito."""

    def __init__(self, mic):
        self.byte = 0
        self.aperture = []
        self.esito = None
        self.fatto = threading.Event()
        mic.accendi(self.su_audio, self.aperto, self.fallito, self.finito)

    def su_audio(self, dati):
        self.byte += len(dati)

    def aperto(self, nome, di_nuovo):
        self.aperture.append((time.monotonic(), nome, di_nuovo))

    def fallito(self, motivo, aveva_aperto):
        self.esito = ("fallito", motivo, aveva_aperto)
        self.fatto.set()

    def finito(self):
        self.esito = ("finito",)
        self.fatto.set()

    @property
    def secondi(self):
        return self.byte / 2 / M.FREQUENZA


def diario(riga):
    print(f"      · {riga}")


def main():
    for pid in figli_vivi():          # residui di prove precedenti
        os.kill(pid, signal.SIGKILL)

    print("\n— 5. elenca —")
    mic = M.Microfono(COMANDO, diario)
    t0 = time.monotonic()
    elenco = mic.elenca()
    controlla("elenca risponde", bool(elenco.get("predefinito")),
              f"{elenco.get('predefinito')} · {len(elenco.get('tutti', []))} microfoni · "
              f"{time.monotonic() - t0:.2f}s")

    print("\n— 1. dieci dettature di fila —")
    time.sleep(1.0)                   # il figlio caldo fa in tempo a nascere
    aperture_ok = 0
    for i in range(10):
        t0 = time.monotonic()
        d = Dettatura(mic)
        time.sleep(1.0)
        mic.spegni()
        d.fatto.wait(4)
        apre = d.aperture[0][0] - t0 if d.aperture else None
        # l'audio parte quando lo stream è partito: ~1 s meno l'apertura,
        # più la coda raccolta dopo «basta»
        ok = (d.esito == ("finito",) and d.aperture and apre < 0.45
              and 0.6 < d.secondi < 1.3)
        aperture_ok += bool(ok)
        print(f"   {i + 1:2d}: esito {d.esito} · audio {d.secondi:.2f}s · "
              f"aperto dopo {apre if apre is None else round(apre, 3)}s")
        time.sleep(0.25)
    controlla("dieci su dieci", aperture_ok == 10, f"{aperture_ok}/10")
    time.sleep(1.0)
    vivi = figli_vivi()
    controlla("resta solo il figlio caldo", len(vivi) <= 1, f"figli vivi: {len(vivi)}")

    print("\n— 2. il figlio muore a metà dettatura —")
    d = Dettatura(mic)
    time.sleep(1.2)
    with mic._lucchetto:
        vittima = mic._presa.figlio.proc.pid
    os.kill(vittima, signal.SIGKILL)
    time.sleep(2.0)
    mic.spegni()
    d.fatto.wait(4)
    ripreso = any(di_nuovo for _, _, di_nuovo in d.aperture)
    controlla("si è ripreso da solo", ripreso and d.esito == ("finito",),
              f"aperture {len(d.aperture)} · esito {d.esito}")
    controlla("l'audio ha continuato ad arrivare", d.secondi > 2.0, f"{d.secondi:.2f}s di audio su ~3.2")

    print("\n— 6. il microfono scelto dal menu —")
    elenco = mic.aggiorna_elenco(1.0)
    controlla("l'elenco per il menu arriva dal figlio caldo", bool(elenco.get("tutti")),
              f"{elenco.get('predefinito')} · {elenco.get('tutti')}")
    mic.cambia("Microfono che non esiste")
    d = Dettatura(mic)
    time.sleep(1.0)
    mic.spegni()
    d.fatto.wait(4)
    controlla("scelto ma scollegato: registra dal predefinito invece di fallire",
              d.esito == ("finito",) and d.aperture and d.aperture[0][1] == elenco["predefinito"],
              f"{d.aperture[0][1] if d.aperture else None}")
    mic.cambia("")
    d = Dettatura(mic)
    time.sleep(1.0)
    mic.cambia(elenco["predefinito"])          # cambiato a dettatura in corso
    time.sleep(1.5)
    mic.spegni()
    d.fatto.wait(4)
    controlla("cambiato a metà: riapre, e l'audio continua",
              d.esito == ("finito",) and len(d.aperture) == 2 and d.aperture[1][2] is True
              and d.secondi > 1.8, f"aperture {len(d.aperture)} · {d.secondi:.2f}s")
    mic.cambia("")

    print("\n— 3. un figlio che non apre mai —")
    finto = [sys.executable, "-c",
             "import sys,time\nfor r in sys.stdin: time.sleep(60)"]
    mic_finto = M.Microfono(finto, diario)
    t0 = time.monotonic()
    d = Dettatura(mic_finto)
    d.fatto.wait(10)
    dopo = time.monotonic() - t0
    controlla("dice «fallito» dopo i tentativi", d.esito is not None and d.esito[0] == "fallito"
              and d.esito[2] is False, f"{d.esito} dopo {dopo:.1f}s")
    controlla("e non ci mette una vita", dopo < 8, f"{dopo:.1f}s")
    mic_finto.chiudi_tutto()

    print("\n— 4. il padre muore di colpo —")
    codice = (
        "import sys,time; sys.path.insert(0, %r)\n"
        "import microfono as M\n"
        "m = M.Microfono(M.comando_figlio(%r))\n"
        "time.sleep(1.0)\n"
        "m.accendi(lambda d: None, lambda n, r: None, lambda m, a: None, lambda: None)\n"
        "time.sleep(60)\n" % (str(QUI), str(QUI / "dettatura.py")))
    padre = subprocess.Popen([sys.executable, "-c", codice])
    time.sleep(2.5)
    # i figli di QUEL padre, non quelli del nostro Microfono (il caldo è vivo)
    r = subprocess.run(["pgrep", "-P", str(padre.pid)], capture_output=True, text=True)
    prima = [int(x) for x in r.stdout.split()]
    padre.kill()
    padre.wait()
    time.sleep(1.5)
    dopo_morte = [p for p in figli_vivi() if p in prima]
    controlla("col padre morto i suoi figli spariscono", prima and not dopo_morte,
              f"prima {len(prima)} · dopo {len(dopo_morte)}")

    mic.chiudi_tutto()
    time.sleep(0.5)
    for pid in figli_vivi():
        os.kill(pid, signal.SIGKILL)

    print()
    if all(esiti):
        print("✅ tutti i controlli passati")
        return 0
    print(f"🔴 {esiti.count(False)} controlli falliti")
    return 1


if __name__ == "__main__":
    sys.exit(main())
