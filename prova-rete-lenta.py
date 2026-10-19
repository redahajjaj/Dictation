#!/usr/bin/env python3
"""Banco di prova della rete lenta: un finto Groq su questo Mac che riceve
l'audio a 100 KB/s, come un Wi-Fi debole in salita, e uno che smette di
riceverlo del tutto.

    .venv/bin/python prova-rete-lenta.py      # ~45 s, niente microfono né Groq vero

Il guasto del 16/10: due dettature da 148 s e 166 s fallite con «The write
operation timed out» mentre quelle corte passavano. Con `files=` requests
spediva tutto il modulo in un'unica scrittura TLS, e urllib3 le dava il tempo
della connessione (10 s): l'audio doveva arrivare tutto in 10 secondi. Qui la
connessione ha 5 s, e l'audio ne vuole ~15 per arrivare.

🔴 Perché 5 s e non meno: macOS non lascia scrivere un blocco appena si libera
posto, ma A SCATTI — qui ~280 KB ogni 2,7 s (misurato il 19/10). Con un limite
più corto di uno scatto fallisce anche il modo nuovo, e la prova mentirebbe.
Nell'app il limite è 10 s: con scatti così il modo nuovo si arrende solo
sotto ~30 KB/s (0,2 Mbit/s: una stima, gli scatti di una rete vera non si
sono misurati), cioè una rete praticamente ferma.

Prova tre cose: che il banco riproduca davvero il guasto (il vecchio modo
fallisce), che `Groq.trascrivi` ora ce la faccia, e che su una rete FERMA si
arrenda comunque invece di restare appesa per sempre.
"""
import socket
import ssl
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import requests
import urllib3

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dettatura as D  # noqa: E402

urllib3.disable_warnings()   # il certificato del finto Groq è fatto qui, al volo

VELOCITA = 100_000           # byte al secondo che il finto Groq accetta
CONNESSIONE = 5.0            # nell'app sono 10 s: qui 5, per fare prima (vedi sopra)
AUDIO = bytes(range(256)) * (1_500_000 // 256)   # ~1,5 MB: ~75 s di FLAC

esiti = []


def controlla(nome, ok, dettaglio=""):
    esiti.append(ok)
    print(f"{'✅' if ok else '❌'} {nome}" + (f"  ({dettaglio})" if dettaglio else ""))


def certificato(cartella: Path) -> ssl.SSLContext:
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                    "-keyout", cartella / "k.pem", "-out", cartella / "c.pem",
                    "-days", "1", "-subj", "/CN=localhost"],
                   check=True, capture_output=True)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(cartella / "c.pem", cartella / "k.pem")
    return ctx


def finto_groq(ctx, servi) -> int:
    """Un server TLS con una memoria di ricezione piccola: quello che non
    legge resta nella rete, come su un Wi-Fi lento. Torna la porta."""
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 16384)
    s.bind(("127.0.0.1", 0))
    s.listen(8)

    def accetta():
        while True:
            c, _ = s.accept()
            try:
                c = ctx.wrap_socket(c, server_side=True)
            except (ssl.SSLError, OSError):
                c.close()
                continue
            threading.Thread(target=servi, args=(c,), daemon=True).start()

    threading.Thread(target=accetta, daemon=True).start()
    return s.getsockname()[1]


def intestazioni(c) -> tuple[int, int]:
    """(lunghezza del corpo, byte del corpo già arrivati con le intestazioni)."""
    dati = b""
    while b"\r\n\r\n" not in dati:
        pezzo = c.recv(4096)
        if not pezzo:
            raise ConnectionError
        dati += pezzo
    testa, resto = dati.split(b"\r\n\r\n", 1)
    for riga in testa.split(b"\r\n"):
        if riga.lower().startswith(b"content-length:"):
            return int(riga.split(b":")[1]), len(resto)
    raise ValueError("senza Content-Length")


def lento(c):
    try:
        lunghezza, letti = intestazioni(c)
        while letti < lunghezza:
            pezzo = c.recv(min(8192, lunghezza - letti))
            if not pezzo:
                return
            letti += len(pezzo)
            time.sleep(len(pezzo) / VELOCITA)
        testo = b"testo trascritto"
        c.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: %d\r\n"
                  b"Connection: close\r\n\r\n%s" % (len(testo), testo))
    except Exception:
        pass
    finally:
        c.close()


def fermo(c):
    """Prende le intestazioni e poi più niente: una rete appesa."""
    try:
        intestazioni(c)
        time.sleep(120)
    except Exception:
        pass
    finally:
        c.close()


if __name__ == "__main__":
    ctx = certificato(Path(tempfile.mkdtemp(prefix="prova-rete-lenta-")))
    porta_lenta = finto_groq(ctx, lento)
    porta_ferma = finto_groq(ctx, fermo)
    D.CONNESSIONE = CONNESSIONE
    D.PAUSE = (0.2, 0.2, 0.2)

    print("— il banco riproduce il guasto del 16/10 —")
    t = time.monotonic()
    try:
        requests.post(f"https://127.0.0.1:{porta_lenta}/audio/transcriptions",
                      files={"file": ("dettatura.flac", AUDIO, "audio/flac")},
                      data={"model": "whisper"}, timeout=(CONNESSIONE, 30), verify=False)
        controlla("il vecchio modo (`files=`) fallisce su questa rete", False,
                  "è passato: il banco non è abbastanza lento, la prova sotto non vale")
    except requests.ConnectionError as e:
        controlla("il vecchio modo (`files=`) fallisce su questa rete",
                  "write operation timed out" in str(e),
                  f"dopo {time.monotonic() - t:.1f}s: {str(e)[:70]}")

    print("\n— l'app di adesso —")
    D.API = f"https://127.0.0.1:{porta_lenta}"
    g = D.Groq("chiave-finta", "modello-finto")
    g.s.verify = False
    detti = []
    t = time.monotonic()
    try:
        testo = g.trascrivi(AUDIO, "p", secondi=75, avanzamento=detti.append)
        durata = time.monotonic() - t
        controlla("rete lenta: l'audio arriva tutto e si trascrive", testo == "testo trascritto",
                  f"in {durata:.1f}s, dove prima si arrendeva a {CONNESSIONE:.0f}s")
        controlla("ed è arrivato al primo colpo, senza tentativi",
                  not any("riprovo" in d for d in detti))
        controlla("la barra ha visto l'invio avanzare",
                  "invio l'audio… 50%" in detti and detti[-1] == "trascrivo…", detti[-2:])
    except D.GroqIrraggiungibile as e:
        controlla("rete lenta: l'audio arriva tutto e si trascrive", False, str(e)[:100])

    D.API = f"https://127.0.0.1:{porta_ferma}"
    t = time.monotonic()
    try:
        g.trascrivi(AUDIO, "p", secondi=75)
        controlla("rete ferma: si arrende (e la dettatura va da parte)", False, "ha risposto?")
    except D.GroqIrraggiungibile as e:
        durata = time.monotonic() - t
        controlla("rete ferma: si arrende (e la dettatura va da parte)", durata < 45,
                  f"in {durata:.1f}s: {str(e)[:60]}")

    print(f"\n{sum(esiti)}/{len(esiti)} ok")
    sys.exit(0 if all(esiti) else 1)
