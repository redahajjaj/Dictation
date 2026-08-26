#!/usr/bin/env python3
"""
Prova la barra senza microfono e senza Groq: costruisce il pannello vero, lo
porta nei 10 stati e misura quello che viene fuori. Poi, se glielo chiedi,
fotografa ogni stato sopra un fondo.

    ./.venv/bin/python prova-barra.py            # solo le misure
    ./.venv/bin/python prova-barra.py scatti     # misure + 10 screenshot

Le foto si fanno con `screencapture -R` a schermo intero: `-l <windowNumber>`
su una finestra di vetro rende un grigio piatto (la isola dallo sfondo).
"""
import subprocess
import sys
from pathlib import Path

from AppKit import (NSApplication, NSApplicationActivationPolicyAccessory,
                    NSBackingStoreBuffered, NSBezierPath, NSColor,
                    NSFloatingWindowLevel, NSImage, NSMakeRect, NSScreen, NSView,
                    NSWindow, NSWindowStyleMaskBorderless,
                    NSCompositingOperationSourceOver)
from Foundation import NSDate, NSRunLoop

import pannello as P

SCATTI = Path(__file__).resolve().parent / ".scratch" / "barra-liquid-glass" / "prototipo" / "barra-vera"
FOTO = "/System/Library/Desktop Pictures/Sonoma.heic"

CORTO = "Ricordami di chiamare Giulia"
MEDIO = "Per Acmelux dobbiamo ancora decidere il corriere"
LUNGO = ("Per Acmelux dobbiamo ancora decidere il corriere, e poi bisogna chiedere a Mario "
         "le misure delle scatole imballate, non del prodotto nudo, perche' i corrieri "
         "fatturano il maggiore fra il peso reale e quello volumetrico.")

errori = []


def attendi(secondi):
    NSRunLoop.currentRunLoop().runUntilDate_(
        NSDate.dateWithTimeIntervalSinceNow_(secondi))


def controlla(nome, condizione, dettaglio=""):
    if condizione:
        print(f"  ok   {nome}   {dettaglio}")
    else:
        print(f"  NO   {nome}   {dettaglio}")
        errori.append(nome)


class AppFinta:
    """Quello che il pannello si aspetta dall'app, e niente di più."""

    def __init__(self):
        self.premuto = 0
        self.copiato = 0
        self.svuotato = 0

    def dal_bottone(self):
        self.premuto += 1

    def copia_dal_pannello(self):
        self.copiato += 1

    def svuota_pannello(self):
        self.svuotato += 1

    def mostra_menu(self):
        pass


class VistaFondo(NSView):
    def impostaTipo_(self, tipo):
        self._tipo = tipo
        self._foto = NSImage.alloc().initWithContentsOfFile_(FOTO) if tipo == "foto" else None
        return self

    def drawRect_(self, _r):
        if self._tipo == "foto" and self._foto is not None:
            self._foto.drawInRect_fromRect_operation_fraction_(
                self.bounds(), NSMakeRect(0, 0, 0, 0), NSCompositingOperationSourceOver, 1.0)
            return
        (NSColor.whiteColor() if self._tipo == "bianco"
         else NSColor.colorWithWhite_alpha_(0.06, 1.0)).setFill()
        NSBezierPath.fillRect_(self.bounds())


def main():
    fai_scatti = len(sys.argv) > 1 and sys.argv[1] == "scatti"
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    finta = AppFinta()
    p = P.Pannello.alloc().init().inizializza(finta)
    p.apri("")
    attendi(0.4)

    # il fondo su cui fotografare, e la barra parcheggiata al centro
    sf = NSScreen.screens()[0].frame()
    REG_L, REG_A = 980, 300
    rx = sf.origin.x + (sf.size.width - REG_L) / 2.0
    ry = sf.origin.y + (sf.size.height - REG_A) / 2.0
    qx, qy = int(rx), int(sf.size.height - (ry + REG_A))
    fondo = None
    if fai_scatti:
        SCATTI.mkdir(parents=True, exist_ok=True)
        fondo = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(rx, ry, REG_L, REG_A), NSWindowStyleMaskBorderless,
            NSBackingStoreBuffered, False)
        fondo.setLevel_(NSFloatingWindowLevel - 1)   # un gradino sotto il vetro
        fondo.setHasShadow_(False)
        fondo.setIgnoresMouseEvents_(True)
        fondo.setContentView_(VistaFondo.alloc().initWithFrame_(
            NSMakeRect(0, 0, REG_L, REG_A)).impostaTipo_("foto"))
        fondo.orderFront_(None)
        attendi(0.5)

    def piazza():
        """Al centro della regione fotografata, senza far scattare _spostata."""
        f = p.finestra.frame()
        p._muovi(P.NSMakeRect(rx + (REG_L - f.size.width) / 2.0,
                              ry + (REG_A - f.size.height) / 2.0,
                              f.size.width, f.size.height))

    def scatta(nome):
        if not fai_scatti:
            return
        piazza()
        # uno scatto nello stesso giro di run loop coglie la finestra prima che
        # macOS l'abbia composta: coordinate giuste, immagine vuota
        attendi(0.7)
        out = SCATTI / f"{nome}.png"
        subprocess.run(["screencapture", "-x", "-R",
                        f"{qx},{qy},{REG_L},{REG_A}", str(out)], check=True)

    def misure():
        f = p.finestra.frame()
        return round(f.size.width), round(f.size.height)

    print("\n— i 10 stati —")

    # 01 riposo
    p.imposta_testo("")
    p.aggiorna(P.PRONTO, "premi ⌘S per dettare")
    L, A = misure()
    controlla("01 riposo: nocciola", A == P.NOCC_A and L >= P.NOCC_MIN, f"{L}x{A}")
    controlla("01 riposo: mic attivo", p._azione_attiva)
    controlla("01 riposo: niente testo", p.scroll.isHidden() and p.menu_btn.isHidden())
    scatta("01-riposo")

    # 02 registra
    for i in range(30):
        p.aggiorna(P.REGISTRA, "0:14   ·   premi di nuovo per fermare",
                   0.2 + 0.7 * abs((i % 9) - 4) / 4.0)
    L, A = misure()
    controlla("02 registra: 248x44", (L, A) == (P.NOCC_REGISTRA_L, P.NOCC_A), f"{L}x{A}")
    controlla("02 registra: cronometro", str(p.crono.stringValue()) == "0:14",
              str(p.crono.stringValue()))
    controlla("02 registra: onda a video", not p.onda.isHidden() and not p.crono.isHidden())
    controlla("02 registra: niente parole", p.messaggio.isHidden() and p.scroll.isHidden())
    scatta("02-registra")

    # 03 silenzio
    for _ in range(30):
        p.aggiorna(P.REGISTRA, "0:03   ·   premi di nuovo per fermare", 0.0)
    controlla("03 silenzio: onda piatta", max(p.onda._liv) <= P.SILENZIO_ONDA)
    controlla("03 silenzio: stessa larghezza", misure() == (P.NOCC_REGISTRA_L, P.NOCC_A))
    scatta("03-silenzio")

    # 04 elabora
    p.aggiorna(P.ELABORA, "trascrivo…")
    L, A = misure()
    controlla("04 elabora: nocciola", A == P.NOCC_A, f"{L}x{A}")
    controlla("04 elabora: messaggio", str(p.messaggio.stringValue()) == "Trascrivo…")
    controlla("04 elabora: mic inerte", not p._azione_attiva)
    scatta("04-elabora")

    # 05 risultato
    p.imposta_testo(MEDIO)
    p.aggiorna(P.PRONTO, "7 parole · negli appunti")
    L, A = misure()
    controlla("05 risultato: distesa 64", A == P.DIST_A, f"{L}x{A}")
    controlla("05 risultato: larghezza in gamma", P.DIST_MIN <= L <= P.DIST_MAX, f"L={L}")
    controlla("05 risultato: conteggio", str(p.conteggio.stringValue()) == "7 parole",
              str(p.conteggio.stringValue()))
    controlla("05 risultato: icone a video",
              not p.b_svuota.isHidden() and not p.b_copia.isHidden()
              and not p.menu_btn.isHidden())
    controlla("05 risultato: testo nel campo", str(p.testo_view.string()) == MEDIO)
    scatta("05-risultato")

    # 05b la mediana dello storico: 27 caratteri
    p.imposta_testo(CORTO)
    p.aggiorna(P.PRONTO, "4 parole · negli appunti")
    L, A = misure()
    controlla("05b corto: ~472 come il prototipo", 450 <= L <= 500, f"L={L}")
    controlla("05b corto: una riga", A == P.DIST_A, f"{L}x{A}")
    scatta("05b-corto")

    # 05c il massimo dello storico: 237 caratteri
    p.imposta_testo(LUNGO)
    p.aggiorna(P.PRONTO, "37 parole · negli appunti")
    L, A = misure()
    controlla("05c lungo: al tetto 720", L == P.DIST_MAX, f"L={L}")
    # il ticket 09 diceva «due righe dentro 64» (il prototipo troncava con «…»).
    # La correzione del 26/8 vale anche per una dettatura sola: meglio una barra
    # più alta che una frase mangiata da un «…» mentre Copia la copia intera.
    controlla("05c lungo: cresce invece di troncare",
              P.DIST_A < A <= P.TESTO_ALTO_MAX + P.ARIA_DISTESA, f"{L}x{A}")
    scatta("05c-lungo")

    # 06 copiato
    p.imposta_testo(MEDIO)
    p.aggiorna(P.PRONTO, "copiato negli appunti")
    prima = misure()
    p.segnala_copia()
    controlla("06 copiato: conteggio", str(p.conteggio.stringValue()) == "copiato",
              str(p.conteggio.stringValue()))
    controlla("06 copiato: la barra non si muove", misure() == prima, f"{misure()}")
    scatta("06-copiato")
    attendi(1.5)
    controlla("06 copiato: torna da sola", str(p.conteggio.stringValue()) == "7 parole",
              str(p.conteggio.stringValue()))

    # 07 due dettature in coda
    p.imposta_testo(MEDIO + "\n\n" + CORTO)
    p.aggiorna(P.PRONTO, "12 parole · aggiunte in coda · negli appunti")
    L, A = misure()
    controlla("07 coda: la nota lo dice",
              str(p.nota.stringValue()) == "2 dettature in coda", str(p.nota.stringValue()))
    controlla("07 coda: la barra è cresciuta", A > P.DIST_A, f"{L}x{A}")
    controlla("07 coda: il testo c'è tutto",
              str(p.testo_view.string()) == MEDIO + "\n\n" + CORTO)
    scatta("07-coda")

    # 09 errore (l'8, l'auto-stop, l'app non lo dice ancora: vedi handoff)
    p.imposta_testo("")
    p.aggiorna(P.PRONTO, P.ERR_VOCE)
    L, A = misure()
    controlla("09 errore: nocciola con la x", A == P.NOCC_A and not p.b_chiudi.isHidden(),
              f"{L}x{A}")
    controlla("09 errore: arancione",
              p.b_azione.contentTintColor() == NSColor.systemOrangeColor())
    controlla("09 errore: messaggio", str(p.messaggio.stringValue()) == "Non ho sentito la voce",
              str(p.messaggio.stringValue()))
    scatta("09-errore")

    # 09b l'errore vince sul testo già a video: se no sparirebbe prima di leggerlo
    p.imposta_testo(MEDIO)
    p.aggiorna(P.PRONTO, P.ERR_GENERICO)
    controlla("09b errore: vince sul testo", misure()[1] == P.NOCC_A, f"{misure()}")

    # 10 premuto mentre elabora
    p.imposta_testo("")
    p.aggiorna(P.ELABORA, P.ATTESA)
    L, A = misure()
    controlla("10 occupato: nocciola", A == P.NOCC_A, f"{L}x{A}")
    controlla("10 occupato: lo dice",
              str(p.messaggio.stringValue()) == "Aspetta: sto ancora trascrivendo")
    scatta("10-occupato")

    print("\n— quello che non si vede negli scatti —")

    # il cursore di scorrimento non deve rubare larghezza al testo: se lo fa, la
    # frase va a capo, e andando a capo il cursore serve davvero — per sempre
    p.imposta_testo(MEDIO)
    p.aggiorna(P.PRONTO, "7 parole · negli appunti")
    largo_scroll = round(p.scroll.frame().size.width)
    largo_clip = round(p.scroll.contentView().frame().size.width)
    usato = p.testo_view.layoutManager().usedRectForTextContainer_(
        p.testo_view.textContainer())
    controlla("il cursore non ruba larghezza", largo_scroll == largo_clip,
              f"{largo_scroll} → {largo_clip}")
    controlla("una frase da una riga sta su una riga", usato.size.height <= P.RIGA,
              f"alta {round(usato.size.height)}")

    # il layout non si rifà se non è cambiato niente
    p.imposta_testo(MEDIO)
    p.aggiorna(P.PRONTO, "7 parole · negli appunti")
    firma = p._firma
    for _ in range(10):
        p.aggiorna(P.PRONTO, "7 parole · negli appunti")
    controlla("battito: il layout non si rifà a vuoto", p._firma is firma)

    # le correzioni a mano non vengono cancellate dal battito
    p.testo_view.setString_("corretto a mano")
    for _ in range(5):
        p.aggiorna(P.PRONTO, "7 parole · negli appunti")
    controlla("il battito non cancella le correzioni",
              str(p.testo_view.string()) == "corretto a mano")
    controlla("testo_corrente legge il campo", p.testo_corrente() == "corretto a mano")

    # crescendo, il bordo alto e il centro restano fermi
    p.imposta_testo(CORTO)
    p.aggiorna(P.PRONTO, "4 parole")
    f1 = p.finestra.frame()
    p.imposta_testo(LUNGO)
    p.aggiorna(P.PRONTO, "37 parole")
    f2 = p.finestra.frame()
    controlla("crescendo: il bordo alto non si muove",
              abs((f1.origin.y + f1.size.height) - (f2.origin.y + f2.size.height)) <= 1,
              f"{round(f1.origin.y + f1.size.height)} → {round(f2.origin.y + f2.size.height)}")
    controlla("crescendo: il centro resta fermo",
              abs((f1.origin.x + f1.size.width / 2) - (f2.origin.x + f2.size.width / 2)) <= 1)

    # l'anteprima mentre parli non scrive testo (ticket 02)
    p.imposta_testo("")
    p.aggiorna(P.REGISTRA, "0:05   ·   premi di nuovo per fermare", 0.5)
    p.mostra_anteprima("", "parole che stanno arrivando")
    controlla("anteprima: non scrive niente", str(p.testo_view.string()) == ""
              and misure() == (P.NOCC_REGISTRA_L, P.NOCC_A))

    # i bottoni chiamano l'app
    p.imposta_testo(MEDIO)
    p.aggiorna(P.PRONTO, "8 parole")
    p.copia_(None)
    p.svuota_(None)
    p.premi_(None)
    controlla("i bottoni parlano con l'app",
              (finta.copiato, finta.svuotato, finta.premuto) == (1, 1, 1),
              str((finta.copiato, finta.svuotato, finta.premuto)))
    p.aggiorna(P.ELABORA, "trascrivo…")
    p.premi_(None)
    controlla("mentre trascrive il mic è inerte", finta.premuto == 1)

    # la posizione: resta dove la metti, torna a casa solo se non l'hai toccata
    controlla("finché non la sposti, comanda la casa", not p._spostata)
    p.finestra.setFrameOrigin_(P.NSMakePoint(120, 400))
    p.finestraMossa_(None)
    controlla("trascinata: da lì comanda Reda", p._spostata)
    p.chiudi()
    p.apri(MEDIO)
    controlla("riaperta: resta dove l'hai messa",
              round(p.finestra.frame().origin.x) == 120,
              str(round(p.finestra.frame().origin.x)))

    if fondo is not None:
        fondo.orderOut_(None)
    p.chiudi()

    print()
    if errori:
        print(f"🔴 {len(errori)} controlli falliti: " + ", ".join(errori))
        return 1
    print("✅ tutti i controlli passati")
    if fai_scatti:
        print(f"   scatti in {SCATTI}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
