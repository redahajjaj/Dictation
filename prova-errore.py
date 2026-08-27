#!/usr/bin/env python3
"""Prova che l'errore si ritira da solo, chiamando il _tick VERO.

    ./.venv/bin/python prova-errore.py

Non serve microfono né Groq: si costruisce un'App a metà (senza __init__, che
aprirebbe l'audio) e si zittiscono i tre punti che parlano con macOS —
`title`, `_mostra_icona`, il pannello.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dettatura as D

esiti = []


def controlla(nome, ok, dettaglio=""):
    esiti.append(ok)
    print(f"  {'ok  ' if ok else 'NO  '} {nome}   {dettaglio}")


class PannelloFinto:
    def __init__(self):
        self.aperto = False
        self.aperture = 0
        self.chiusure = 0

    def e_aperto(self):
        return self.aperto

    def apri(self, testo=None):
        self.aperto = True
        self.aperture += 1

    def chiudi(self):
        self.aperto = False
        self.chiusure += 1

    def aggiorna(self, *a):
        pass


class AppFinta(D.App):
    """L'App vera, ma senza __init__ (che apre microfono e Groq) e senza i tre
    punti che parlano con macOS."""

    def __init__(self):
        import queue
        self.cfg = {}
        self.scorciatoia = "<cmd>+s"
        self.tasti = "⌘S"
        self.invito = "premi ⌘S per dettare"
        self.modo = "pulito"
        self.registrando = False
        self._eventi = queue.Queue()
        self._stato = D.PRONTO
        self._etichetta = self.invito
        self._livello = 0.0
        self._fine_attesa = 0.0
        self._etichetta_prima = self.invito
        self._fine_errore = 0.0
        self._errore_n = 0
        self._errore_armato = -1
        self._barra_per_errore = False
        self._icona_agganciata = True
        self._bottone_barra = None
        self._icona_ora = ""
        self.pannello = PannelloFinto()
        self._pannello = self.pannello
        self._testo_fisso = ""

    # i tre punti che toccherebbero macOS
    title = property(lambda s: "", lambda s, v: None)

    def _mostra_icona(self, nome):
        pass

    def _crea_pannello(self):
        return self.pannello


def tick(app, n=1):
    for _ in range(n):
        app._tick(None)


print("\n— l'errore si ritira da solo —")

# 1. errore a barra CHIUSA: si apre, resta ~2 s, si richiude
a = AppFinta()
a.pannello.aperto = False
a._stato, a._etichetta = D.PRONTO, D.ERR_VOCE
tick(a)
controlla("a barra chiusa l'errore la apre", a.pannello.aperto and a.pannello.aperture == 1)
controlla("l'errore è ancora a video subito dopo", a._etichetta == D.ERR_VOCE)

tick(a, 3)
controlla("dopo un attimo è ancora lì", a._etichetta == D.ERR_VOCE)

a._fine_errore = time.time() - 0.01   # sposto le lancette invece di aspettare
tick(a)
controlla("scaduto: torna all'invito", a._etichetta == a.invito, a._etichetta)
controlla("scaduto: la barra si richiude", not a.pannello.aperto and a.pannello.chiusure == 1)

# 2. errore a barra GIA' APERTA: non deve chiudergliela
b = AppFinta()
b.pannello.aperto = True
b._stato, b._etichetta = D.PRONTO, D.ERR_NIENTE
tick(b)
controlla("barra già aperta: non la riapre", b.pannello.aperture == 0)
b._fine_errore = time.time() - 0.01
tick(b)
controlla("barra già aperta: NON gliela chiude", b.pannello.aperto and b.pannello.chiusure == 0)
controlla("ma l'errore sparisce lo stesso", b._etichetta == b.invito)

# 3. IL CASO CHE ROMPEVA: due ⌘S a vuoto di fila danno due volte lo STESSO
#    ERR_CORTO. Se il secondo eredita il timer del primo, resta a video un
#    lampo. Qui si usa la strada vera: _segnala_errore, come fa _ferma().
c = AppFinta()
c._segnala_errore(D.ERR_CORTO)
tick(c)
c._fine_errore = time.time() + 0.05      # il primo sta per scadere...
c._segnala_errore(D.ERR_CORTO)           # ...e ne arriva un altro IDENTICO
tick(c)
resta = c._fine_errore - time.time()
controlla("due errori uguali: il secondo dura i suoi 2 s", resta > 1.5,
          f"gli restano {round(resta, 2)} s")

# lo stesso errore dopo che è passato dell'altro
d = AppFinta()
d._segnala_errore(D.ERR_CORTO)
tick(d)
d._etichetta = "trascrivo…"              # parte una registrazione nuova
tick(d)
controlla("altro messaggio: il timer si spegne", d._fine_errore == 0.0)
d._segnala_errore(D.ERR_CORTO)           # stesso errore, ma è un errore nuovo
tick(d)
controlla("stesso errore dopo: riarma da capo",
          d._fine_errore > time.time() + 1.5,
          f"gli restano {round(d._fine_errore - time.time(), 2)} s")

# 4. un errore diverso mentre il primo è a video: riarma
e = AppFinta()
e._segnala_errore(D.ERR_CORTO)
tick(e)
e._fine_errore = time.time() + 0.05
e._segnala_errore(D.ERR_VOCE)            # errore DIVERSO
tick(e)
controlla("errore diverso: riparte da capo", e._fine_errore > time.time() + 1.5,
          f"gli restano {round(e._fine_errore - time.time(), 2)} s")

# 5. l'errore che arriva dalla CODA (thread di trascrizione) conta anche lui
q = AppFinta()
q._eventi.put((D.PRONTO, D.ERR_NIENTE))
tick(q)
n1 = q._errore_n
q._fine_errore = time.time() + 0.05
q._eventi.put((D.PRONTO, D.ERR_NIENTE))  # identico, dalla coda
tick(q)
controlla("dalla coda: il secondo identico riarma",
          q._errore_n == n1 + 1 and q._fine_errore > time.time() + 1.5,
          f"n={q._errore_n}, restano {round(q._fine_errore - time.time(), 2)} s")

# 6. l'invito normale non deve armare niente
f = AppFinta()
tick(f, 3)
controlla("nessun errore: nessun timer", f._fine_errore == 0.0 and not f.pannello.aperture)

print()
if all(esiti):
    print("✅ tutti i controlli passati")
else:
    print(f"🔴 {esiti.count(False)} controlli falliti")
    sys.exit(1)
