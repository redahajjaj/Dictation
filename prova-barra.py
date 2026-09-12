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

# 🔴 Le misure si leggono subito dopo `aggiorna()`: con le transizioni accese
# `frame()` torna il valore INTERPOLATO, cioè la barra a metà strada. Spente,
# ogni controllo misura la destinazione. Le transizioni hanno controlli propri,
# in fondo al file, che le riaccendono per il tempo che serve.
P.ANIMA = False

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
    # L'onda vive di suo, a 60 fotogrammi al secondo: `aggiorna` le dice solo
    # quanto forte stai parlando. Per fotografarla al culmine bisogna darle il
    # volume e poi lasciar girare il run loop, o si scatta l'onda a riposo.
    p.aggiorna(P.REGISTRA, "0:14   ·   premi di nuovo per fermare", 0.85)
    attendi(0.35)
    L, A = misure()
    controlla("02 registra: 248x44", (L, A) == (P.NOCC_REGISTRA_L, P.NOCC_A), f"{L}x{A}")
    controlla("02 registra: cronometro", str(p.crono.stringValue()) == "0:14",
              str(p.crono.stringValue()))
    controlla("02 registra: onda a video", not p.onda.isHidden() and not p.crono.isHidden())
    controlla("02 registra: l'onda è salita", p.onda._liv > 0.6, f"{p.onda._liv:.2f}")
    controlla("02 registra: il motorino gira", p._t_onda is not None)
    controlla("02 registra: niente parole", p.messaggio.isHidden() and p.scroll.isHidden())
    scatta("02-registra")

    # 03 silenzio
    p.aggiorna(P.REGISTRA, "0:03   ·   premi di nuovo per fermare", 0.0)
    attendi(0.6)
    # non va a zero e non deve: a silenzio l'onda resta a respirare, o sembra
    # che il microfono si sia spento
    controlla("03 silenzio: l'onda si è calmata", p.onda._liv <= 0.06, f"{p.onda._liv:.3f}")
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
    # niente più ✕: l'errore si ritira da solo dopo due secondi, e un clic
    # fuori dalla barra la manda via prima
    controlla("09 errore: nocciola", A == P.NOCC_A, f"{L}x{A}")
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

    # Il colore non deve cambiare quando clicchi sulla barra. La tinta di
    # NSGlassEffectView macOS la butta via quando la finestra non è key: con
    # setTintColor_ la capsula saltava di 74 livelli di grigio al primo clic
    # (misurato a pixel), e il contrasto del testo scendeva sotto il minimo.
    # Se qualcuno rimette quella riga, questi tre controlli lo dicono subito.
    if P.NSGlassEffectView is not None:
        controlla("il colore non lo decide macOS", p.vetro.tintColor() is None,
                  "niente setTintColor_")
    controlla("la tinta la dipinge il contenuto",
              isinstance(p.contenuto, P.VistaVetro))
    controlla("il filo non si mangia i clic",
              p.contenuto.subviews()[-1] is p.filo
              and p.filo.hitTest_(P.NSMakePoint(10, 10)) is None,
              "ultimo subview, hitTest → None")

    # l'anello di «copiato» sta sopra i bottoni ma sotto il filo
    controlla("l'anello sta sotto il filo",
              p.contenuto.subviews()[-2] is p.alone,
              "penultimo subview")

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

    # lo scorrimento non deve andare oltre la fine del testo.
    #
    # Il testo entra nel campo PRIMA che _applica gli dia la sua larghezza: se
    # il campo è ancora quello appena nato, il testo va a capo ogni due
    # caratteri, la vista si gonfia e con TextKit 2 non si sgonfia più.
    # Restavano migliaia di punti di scorrimento sopra il vetro vuoto.
    #
    # Due accortezze, o il controllo non vede niente:
    #  - un pannello NUOVO: il difetto vive solo al primo testo di una barra
    #    appena costruita, e il controllo qui sopra ha già chiamato
    #    layoutManager() su `p`, che lo ripara;
    #  - leggere il frame PRIMA di layoutManager(): chiamarlo tira la vista
    #    fuori da TextKit 2 e corregge l'altezza sotto il naso di chi misura.
    ELENCO = ("Sistema la barra fluttuante.\n- transizioni animate\n"
              "- anteprima visibile\n- contrasto 4,5 a 1\n- niente scroll a vuoto")
    p51 = P.Pannello.alloc().init().inizializza(AppFinta())
    p51.apri(ELENCO)
    p51.aggiorna(P.PRONTO, "20 parole")
    attendi(0.4)
    alta_testo = p51.testo_view.frame().size.height
    alta_finestrella = p51.scroll.contentView().bounds().size.height
    vuoto = alta_testo - alta_finestrella
    controlla("lo scorrimento non va oltre il testo", vuoto <= 2,
              f"scorribile {round(vuoto)} punti (campo {round(alta_testo)}, "
              f"finestrella {round(alta_finestrella)})")
    p51.chiudi()

    # --- l'anello di «copiato» ------------------------------------------------
    # Serve la barra distesa: a nocciola il bottone Copia non c'è, e l'anello
    # giustamente non parte.
    p.imposta_testo(MEDIO)
    p.aggiorna(P.PRONTO, "7 parole")
    attendi(0.2)
    f_copia = p.b_copia.frame()
    # come il filo, l'anello sta SOPRA il bottone: se gli rubasse il clic, Copia
    # smetterebbe di funzionare senza un errore che lo dica
    controlla("l'anello non si mangia il clic su Copia",
              p.alone.hitTest_(P.NSMakePoint(5, 5)) is None
              and p.contenuto.hitTest_(
                  P.NSMakePoint(f_copia.origin.x + 14,
                                f_copia.origin.y + 14)) is p.b_copia)

    # copiare due volte di fila: la spunta della seconda non deve essere spenta
    # dal timer della prima (era il caso — spariva dopo un attimo invece di 1,2 s)
    p.segnala_copia()
    primo = p._t_spunta
    attendi(0.2)
    p.segnala_copia()
    controlla("due copie di fila: il timer vecchio è stato spento",
              p._t_spunta is not primo and not primo.isValid())
    attendi(0.3)
    controlla("due copie di fila: la spunta della seconda è ancora lì", p._copiato)
    controlla("due copie di fila: un anello solo, ripartito da zero",
              p._t_alone is not None and p.alone._q < 1.0,
              f"q={round(p.alone._q, 2)}")
    attendi(0.5)
    controlla("l'anello si spegne da solo",
              p._t_alone is None and p.alone.isHidden())
    # e l'anello segue Copia quando la barra cambia larghezza
    p.imposta_testo(LUNGO)
    p.aggiorna(P.PRONTO, "34 parole")
    attendi(0.2)
    fc, fa = p.b_copia.frame(), p.alone.frame()
    controlla("l'anello resta centrato su Copia",
              abs((fa.origin.x + fa.size.width / 2)
                  - (fc.origin.x + fc.size.width / 2)) <= 0.5,
              f"copia {round(fc.origin.x)} · anello {round(fa.origin.x)}")
    p._ripristina_copia()

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

    # cambiando forma cambia il raggio (nocciola 22, distesa 32): tinta e filo
    # non lo ereditano da nessuno. Se non li si riaggiorna, agli angoli
    # spuntano quattro quadrati di tinta e il filo taglia dritto.
    atteso = min(f2.size.height / 2.0, P.RAGGIO_MAX)
    controlla("tinta e filo seguono il raggio",
              p.contenuto._raggio == atteso and p.filo._raggio == atteso
              and round(p.filo.frame().size.width) == round(f2.size.width),
              f"raggio {atteso}")

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

    # --- le transizioni, con l'animazione ACCESA ------------------------------
    # Tutto il resto del file misura a destinazione (P.ANIMA = False in cima).
    # Qui si riaccende apposta: sono gli unici controlli che guardano il volo.
    print("\n— le transizioni —")
    P.ANIMA = True
    # i controlli qui sopra hanno trascinato la barra apposta: si riparte da
    # «mai spostata», o il controllo 4 leggerebbe quel trascinamento finto
    p._spostata = False
    try:
        p.imposta_testo("")
        p.aggiorna(P.PRONTO, "premi ⌘S per dettare")
        attendi(0.5)
        largo_prima = p.finestra.frame().size.width

        # 1. durante il volo la barra è a metà strada, non già arrivata
        p.imposta_testo(LUNGO)
        p.aggiorna(P.PRONTO, "34 parole")
        attendi(0.12)
        in_volo = p.finestra.frame().size.width
        controlla("in volo la barra è a metà strada",
                  largo_prima < in_volo < P.DIST_MAX,
                  f"{round(largo_prima)} → {round(in_volo)} → …")
        controlla("in volo il cancello è chiuso", p._animazioni > 0,
                  f"{p._animazioni} in volo")

        # 🔴 2. in volo il contenuto che ENTRA deve essere invisibile. Se compare
        #    subito prende il frame di destinazione a istante zero, mentre la
        #    capsula è ancora piccola: lo si vede scritto fuori dalla barra, sul
        #    desktop. Visto negli scatti, non dedotto.
        controlla("in volo il testo che entra non si vede",
                  p.scroll.alphaValue() < 0.01,
                  f"alpha {round(p.scroll.alphaValue(), 2)}")

        # 3. e arriva a destinazione
        attendi(0.6)
        controlla("arrivata, il testo si vede", p.scroll.alphaValue() > 0.99,
                  f"alpha {round(p.scroll.alphaValue(), 2)}")
        arrivata = p.finestra.frame().size.width
        controlla("arriva a destinazione", arrivata > in_volo + 10,
                  f"→ {round(arrivata)}")
        controlla("a volo finito il cancello si riapre", p._animazioni == 0)

        # 3. 🔴 il bordo alto non si muove NEMMENO durante il volo: è la cosa
        #    che fa sembrare la barra ancorata sotto l'icona invece che elastica
        p.imposta_testo("")
        p.aggiorna(P.PRONTO, "premi ⌘S per dettare")
        attendi(0.5)
        f = p.finestra.frame()
        alto_prima = round(f.origin.y + f.size.height)
        p.imposta_testo(LUNGO)
        p.aggiorna(P.PRONTO, "34 parole")
        alti = []
        for _ in range(8):
            attendi(0.04)
            g = p.finestra.frame()
            alti.append(round(g.origin.y + g.size.height))
        attendi(0.5)
        controlla("in volo il bordo alto resta fermo",
                  all(abs(a - alto_prima) <= 1 for a in alti),
                  f"{alto_prima} · fotogrammi {sorted(set(alti))}")

        # 4. una transizione non deve far credere alla barra di essere trascinata
        controlla("il volo non conta come trascinamento", not p._spostata)

        # --- la dissolvenza sul posto ----------------------------------------
        # 🔴 Fino al 12/9 la barra si richiudeva risucchiandosi in una goccia
        # sul proprio bordo alto, cioè verso la cima dello schermo. Adesso
        # svanisce dov'è: questi controlli guardano che NON si muova e NON si
        # stringa mentre se ne va.
        p.imposta_testo(LUNGO)
        p.aggiorna(P.PRONTO, "34 parole")
        attendi(0.5)
        controlla("niente bottoni di chiusura nella distesa",
                  not hasattr(p, "b_riduci") and not hasattr(p, "b_chiudi"))

        pieno = p.finestra.frame()
        p.chiudi()
        attendi(0.08)
        # 🔴 in volo la barra è ancora a video, ma per il resto del mondo è già
        # chiusa: senza questo il battito a 10 Hz le rifà il layout addosso e la
        # fa atterrare visibile invece di sparire
        controlla("in dissolvenza la barra si dichiara chiusa", not p.e_aperto())
        controlla("in dissolvenza sta svanendo",
                  0.0 < p.finestra.alphaValue() < 0.95,
                  f"opacità {p.finestra.alphaValue():.2f}")
        mezzo = p.finestra.frame()
        controlla("in dissolvenza non si muove e non si stringe",
                  abs(mezzo.origin.x - pieno.origin.x) <= 1
                  and abs(mezzo.origin.y - pieno.origin.y) <= 1
                  and abs(mezzo.size.width - pieno.size.width) <= 1,
                  f"{round(pieno.size.width)}x{round(pieno.size.height)} "
                  f"→ {round(mezzo.size.width)}x{round(mezzo.size.height)}")
        attendi(0.5)
        controlla("finita la dissolvenza la barra è sparita",
                  not p.finestra.isVisible() and p._volo is None)
        controlla("e torna opaca, pronta a riaprirsi",
                  p.finestra.alphaValue() == 1.0, f"{p.finestra.alphaValue()}")
        dopo = p.finestra.frame()
        controlla("il frame torna identico, senza derive",
                  (round(dopo.origin.x), round(dopo.size.width))
                  == (round(pieno.origin.x), round(pieno.size.width)),
                  f"x {round(pieno.origin.x)} → {round(dopo.origin.x)}")

        # riaprire a metà volo taglia la dissolvenza: la barra resta, e opaca
        p.apri()
        attendi(0.4)
        p.chiudi()
        attendi(0.08)
        p.apri()
        attendi(0.5)
        controlla("riaprire a metà dissolvenza la salva",
                  p.finestra.isVisible() and p._volo is None
                  and p.finestra.alphaValue() == 1.0
                  and p.finestra.frame().size.width > 200,
                  f"larga {round(p.finestra.frame().size.width)} "
                  f"· opacità {p.finestra.alphaValue()}")

        # 5. spegnendo l'animazione si torna al salto secco, senza volo
        P.ANIMA = False
        p.imposta_testo("")
        p.aggiorna(P.PRONTO, "premi ⌘S per dettare")
        attendi(0.4)
        p.imposta_testo(LUNGO)
        p.aggiorna(P.PRONTO, "34 parole")
        controlla("spenta, arriva subito", p._animazioni == 0
                  and p.finestra.frame().size.width > 400,
                  f"{round(p.finestra.frame().size.width)} senza attendere")
    finally:
        P.ANIMA = False

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
