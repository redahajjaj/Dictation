#!/usr/bin/env python3
"""Banco di prova della finestra delle impostazioni (impostazioni.py).

    .venv/bin/python prova-impostazioni.py            # i controlli
    .venv/bin/python prova-impostazioni.py scatti     # + una foto per scheda

Niente Groq, niente file veri: un'app finta, uno storico e un vocabolario
finti in una cartella usa e getta (i nomi sono quelli dei .esempio). La
finestra si apre davvero sullo schermo per qualche secondo.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from AppKit import (NSAlertSecondButtonReturn, NSApplication,
                    NSApplicationActivationPolicyAccessory)
from Foundation import NSDate, NSRunLoop

QUI = Path(__file__).resolve().parent
sys.path.insert(0, str(QUI))

import archivio as A  # noqa: E402
import impostazioni as I  # noqa: E402

CARTELLA = Path(tempfile.mkdtemp(prefix="prova-impostazioni-"))
A.COPIE = CARTELLA / "copie"
SCATTI = Path("/private/tmp") / "prova-impostazioni-scatti"
errori = []


def attendi(secondi):
    NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(secondi))


def controlla(nome, condizione, dettaglio=""):
    print(f"  {'ok  ' if condizione else 'NO  '} {nome}   {dettaglio}")
    if not condizione:
        errori.append(nome)


STORICO = """
## 2026-10-10 09:12 · pulito · 12s

Per Acmelux dobbiamo ancora decidere il corriere.

<details><summary>grezzo</summary>

per acme lux dobbiamo ancora decidere il corriere

</details>

## 2026-10-11 18:40 · prompt · 45s

Controlla il deploy sul VPS e poi manda il preventivo a Mario Rossi.

<details><summary>grezzo</summary>

controlla il deploy sul vps e poi manda il preventivo a mario rossi

</details>
"""


class AppFinta:
    """Quello che la finestra chiede all'app, sui file della cartella usa e getta."""

    def __init__(self):
        self.chiave = "gsk_vecchiachiave123456"
        self.esiti = []            # le risposte che darà prova_chiave, in ordine
        self.salvate = []
        self.modello = ""
        self.copiato = []
        self.vocabolario = CARTELLA / "vocabolario.txt"
        self.correzioni = CARTELLA / "correzioni.txt"
        self.storico = CARTELLA / "storico.md"

    def chiave_mascherata(self):
        c = self.chiave
        return f"{c[:4]}…{c[-6:]}" if c else ""

    def prova_chiave(self, chiave):
        if self.esiti:
            return self.esiti.pop(0)
        return True, "funziona · pulisce con openai/gpt-oss-120b", ["openai/gpt-oss-120b",
                                                                   "openai/gpt-oss-20b"]

    def salva_chiave(self, chiave):
        self.salvate.append(chiave)
        self.chiave = chiave

    def modello_scelto(self):
        return self.modello

    def salva_modello(self, nome):
        self.modello = nome

    def trascrizioni(self):
        return A.leggi_storico(self.storico)

    def copia_testo(self, testo):
        self.copiato.append(testo)

    def apri_storico(self, _):
        pass

    def parole(self):
        return A.leggi_parole(self.vocabolario, self.correzioni)

    def salva_parole(self, parole):
        A.scrivi_parole(parole, self.vocabolario, self.correzioni)

    def apri_file_parole(self):
        pass


def scatta(finestra, nome):
    if len(sys.argv) < 2 or sys.argv[1] != "scatti":
        return
    SCATTI.mkdir(parents=True, exist_ok=True)
    attendi(0.6)
    subprocess.run(["screencapture", "-x", "-o", "-l", str(finestra.windowNumber()),
                    str(SCATTI / f"{nome}.png")], check=False)


def main():
    shutil.copy(QUI / "vocabolario.esempio.txt", CARTELLA / "vocabolario.txt")
    shutil.copy(QUI / "correzioni.esempio.txt", CARTELLA / "correzioni.txt")
    (CARTELLA / "storico.md").write_text(STORICO, encoding="utf-8")

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    finta = AppFinta()
    w = I.Impostazioni.alloc().init().inizializza(finta)

    print("\n— la chiave —")
    w.mostra("chiave")
    attendi(0.5)
    controlla("si apre sulla scheda chiesta", w.schede.indexOfTabViewItem_(
        w.schede.selectedTabViewItem()) == 0)
    controlla("la chiave in uso si vede solo mascherata",
              str(w.l_chiave.stringValue()) == "gsk_…123456", str(w.l_chiave.stringValue()))
    controlla("e si sa se funziona", str(w.l_stato.stringValue()).startswith("✓ funziona"),
              str(w.l_stato.stringValue()))
    controlla("i modelli arrivano nel menu",
              w.modelli.numberOfItems() == 3 and w.modelli.titleOfSelectedItem() == I.AUTOMATICO)
    scatta(w.finestra, "1-chiave")

    finta.esiti = [(False, "Groq rifiuta questa chiave", [])]
    w.campo_chiave.setStringValue_("  gsk_sbagliata \n")
    w.salvaChiave_(None)
    attendi(0.5)
    controlla("una chiave rifiutata NON si salva",
              not finta.salvate and "non l'ho salvata" in str(w.l_esito.stringValue()),
              str(w.l_esito.stringValue()))
    finta.esiti = [(True, "funziona · pulisce con openai/gpt-oss-120b", ["openai/gpt-oss-120b"])]
    w.campo_chiave.setStringValue_(" gsk_nuovachiave987654 ")
    w.salvaChiave_(None)
    attendi(0.5)
    controlla("una chiave che funziona si salva, senza spazi",
              finta.salvate == ["gsk_nuovachiave987654"], str(finta.salvate))
    controlla("e si vede subito quella nuova", str(w.l_chiave.stringValue()) == "gsk_…987654"
              and str(w.campo_chiave.stringValue()) == "")
    w.modelli.selectItemWithTitle_("openai/gpt-oss-120b")
    w.sceltoModello_(None)
    controlla("il modello scelto si salva", finta.modello == "openai/gpt-oss-120b")
    w.modelli.selectItemWithTitle_(I.AUTOMATICO)
    w.sceltoModello_(None)
    controlla("e «Automatico» lo toglie", finta.modello == "")

    print("\n— lo storico —")
    w.mostra("storico")
    attendi(0.3)
    controlla("si apre sulla scheda chiesta",
              w.schede.indexOfTabViewItem_(w.schede.selectedTabViewItem()) == 1)
    controlla("tutte le dettature, la più recente in cima",
              w.t_storico.numberOfRows() == 2
              and str(w.testo_storico.string()).startswith("Controlla il deploy"),
              str(w.l_quante.stringValue()))
    w.versione.setSelectedSegment_(1)
    w.cambiaVersione_(None)
    controlla("si vede anche il grezzo", str(w.testo_storico.string()).startswith("controlla il deploy"))
    w.copiaTrascrizione_(None)
    controlla("Copia copia quello che si vede", finta.copiato and finta.copiato[-1].startswith("controlla"))
    w.versione.setSelectedSegment_(0)
    w.cerca_storico.setStringValue_("acmelux")
    w.cercaStorico_(None)
    controlla("la ricerca filtra", w.t_storico.numberOfRows() == 1
              and "Acmelux" in str(w.testo_storico.string()), str(w.l_quante.stringValue()))
    w.cerca_storico.setStringValue_("")
    w.cercaStorico_(None)
    scatta(w.finestra, "2-storico")

    print("\n— le parole speciali —")
    w.mostra("parole")
    attendi(0.3)
    sp = w.sorgente_parole
    n0 = len(sp.parole)
    controlla("vocabolario e correzioni in una lista sola", n0 > 0 and any(p.varianti for p in sp.parole),
              str(w.l_parole.stringValue()))
    controlla("niente da salvare finché non cambi niente", not w.b_salva.isEnabled())
    col = w.t_parole.tableColumnWithIdentifier_("varianti")
    riga = next(i for i, j in enumerate(sp.indici) if sp.parole[j].parola == "Nordvento")
    sp.tableView_setObjectValue_forTableColumn_row_(w.t_parole, "nord vento, nordvent", col, riga)
    controlla("scrivere in una cella la segna da salvare", w.b_salva.isEnabled()
              and "non salvate" in str(w.l_salvate.stringValue()))
    w.aggiungiParola_(None)
    attendi(0.2)
    nuova = len(sp.indici) - 1
    w.finestra.makeFirstResponder_(None)
    for ident, valore in (("parola", "Zettaprova"), ("varianti", "zeta prova"), ("gruppo", "prove")):
        sp.tableView_setObjectValue_forTableColumn_row_(
            w.t_parole, valore, w.t_parole.tableColumnWithIdentifier_(ident), nuova)
    controlla("+ aggiunge una riga", len(sp.parole) == n0 + 1)
    scatta(w.finestra, "3-parole")
    w.salvaParole_(None)
    voc = (CARTELLA / "vocabolario.txt").read_text(encoding="utf-8")
    cor = (CARTELLA / "correzioni.txt").read_text(encoding="utf-8")
    controlla("Salva scrive le due liste",
              "Zettaprova" in voc and "Zettaprova = zeta prova" in cor
              and "Nordvento = nord vento, nordvent" in cor)
    controlla("l'intestazione dei file resta", voc.startswith("#") and cor.startswith("#"))
    controlla("e dopo il salvataggio non c'è più niente in sospeso", not w.b_salva.isEnabled())
    controlla("la versione di prima è nelle copie di sicurezza", len(list(A.COPIE.glob("*"))) == 2)

    riga = next(i for i, j in enumerate(sp.indici) if sp.parole[j].parola == "Zettaprova")
    w.t_parole.selectRowIndexes_byExtendingSelection_(I.NSIndexSet.indexSetWithIndex_(riga), False)
    w.togliParole_(None)
    controlla("− toglie la riga scelta", all(p.parola != "Zettaprova" for p in sp.parole)
              and w.b_salva.isEnabled())

    print("\n— chiudere con le parole non salvate —")
    permessa = w.windowShouldClose_(w.finestra)
    attendi(0.4)
    foglio = w.finestra.attachedSheet()
    controlla("non si chiude: chiede se salvare (in un foglio attaccato)", not permessa and foglio is not None)
    if foglio is not None:
        w.finestra.endSheet_returnCode_(foglio, NSAlertSecondButtonReturn)
        attendi(0.4)
    controlla("«Non salvare» la chiude e torna ai file", not w.e_aperta()
              and any(p.parola == "Zettaprova" for p in sp.parole) and not w.b_salva.isEnabled())

    w.mostra("chiave")
    attendi(0.2)
    controlla("si riapre", w.e_aperta())
    w.finestra.orderOut_(None)
    shutil.rmtree(CARTELLA, ignore_errors=True)

    print()
    if errori:
        print(f"🔴 {len(errori)} controlli falliti: " + ", ".join(errori))
        return 1
    print("✅ tutti i controlli passati" + (f" · scatti in {SCATTI}" if len(sys.argv) > 1 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
