"""
La finestra della dettatura: bottone di registrazione al centro, il testo sotto.
Si apre con un clic sull'icona e resta dove la metti — si trascina da qualsiasi
punto e non sparisce quando lavori altrove, così puoi tenerla di fianco a Warp.

Tutti i colori vengono dal sistema (labelColor, systemRed…), così il pannello
segue da solo il tema chiaro e scuro senza che qui ci sia una sola tinta fissa.
"""
from __future__ import annotations

import objc
from AppKit import (
    NSApp,
    NSBackingStoreBuffered,
    NSFloatingWindowLevel,
    NSPanel,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskFullSizeContentView,
    NSWindowStyleMaskTitled,
    NSWindowStyleMaskUtilityWindow,
    NSWindowTitleHidden,
    NSBezierPath,
    NSButton,
    NSCenterTextAlignment,
    NSColor,
    NSCursor,
    NSFont,
    NSFontWeightMedium,
    NSFontWeightRegular,
    NSFontWeightSemibold,
    NSMakePoint,
    NSMakeRect,
    NSMakeSize,
    NSNoBorder,
    NSScrollView,
    NSTextField,
    NSTextView,
    NSTrackingActiveInActiveApp,
    NSTrackingArea,
    NSTrackingMouseEnteredAndExited,
    NSView,
    NSViewController,
    NSViewWidthSizable,
)
from Foundation import NSObject

# --- misure: tutto il layout discende da queste -----------------------------
LARGO = 320
BORDO = 18
REC = 74            # diametro del bottone di registrazione
ALONE = 30          # spazio attorno al bottone per l'anello del livello
H_TESTA = 40
H_STATO = 18
H_AZIONI = 30
TESTO_MIN = 96
TESTO_MAX = 250

PRONTO, REGISTRA, ELABORA = "pronto", "registra", "elabora"


class BottoneRec(NSView):
    """Il tondo rosso: cerchio pieno quando è fermo, quadrato quando registra.

    Attorno gli gira un anello che respira con la voce — serve a vedere subito
    che il microfono sta prendendo davvero qualcosa.
    """

    @objc.python_method
    def prepara(self, quando_premuto):
        self.quando_premuto = quando_premuto
        self.stato = PRONTO
        self.livello = 0.0
        self.sopra = False
        self.giro = 0.0
        return self

    def acceptsFirstMouse_(self, _e):
        return True

    def hitTest_(self, punto):
        """La view è più grande del cerchio (serve spazio per l'anello del livello):
        fuori dal cerchio i clic devono passare a quello che c'è sotto."""
        dentro = self.convertPoint_fromView_(punto, self.superview())
        b = self.bounds()
        dx = dentro.x - b.size.width / 2
        dy = dentro.y - b.size.height / 2
        return self if (dx * dx + dy * dy) <= (REC / 2 + 3) ** 2 else None

    def updateTrackingAreas(self):
        for a in self.trackingAreas():
            self.removeTrackingArea_(a)
        self.addTrackingArea_(
            NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
                self.bounds(),
                NSTrackingMouseEnteredAndExited | NSTrackingActiveInActiveApp,
                self, None,
            )
        )

    def mouseEntered_(self, _e):
        self.sopra = True
        NSCursor.pointingHandCursor().set()
        self.setNeedsDisplay_(True)

    def mouseExited_(self, _e):
        self.sopra = False
        NSCursor.arrowCursor().set()
        self.setNeedsDisplay_(True)

    def mouseDown_(self, _e):
        self.quando_premuto()

    def drawRect_(self, _rect):
        b = self.bounds()
        cx, cy = b.size.width / 2, b.size.height / 2
        raggio = REC / 2

        # anello del livello: cresce con la voce, resta fuori dal bottone
        if self.stato == REGISTRA and self.livello > 0.01:
            for fattore, alfa in ((1.0, 0.20), (0.60, 0.13)):
                extra = 4 + self.livello * ALONE * fattore
                NSColor.systemRedColor().colorWithAlphaComponent_(alfa).setFill()
                NSBezierPath.bezierPathWithOvalInRect_(
                    NSMakeRect(cx - raggio - extra, cy - raggio - extra,
                               (raggio + extra) * 2, (raggio + extra) * 2)
                ).fill()

        # contorno sempre presente: è il bordo del bottone
        NSColor.tertiaryLabelColor().setStroke()
        contorno = NSBezierPath.bezierPathWithOvalInRect_(
            NSMakeRect(cx - raggio, cy - raggio, raggio * 2, raggio * 2)
        )
        contorno.setLineWidth_(1.5)
        contorno.stroke()

        if self.stato == ELABORA:
            # archetto che ruota: l'attesa deve sembrare viva
            NSColor.secondaryLabelColor().setStroke()
            arco = NSBezierPath.bezierPath()
            arco.appendBezierPathWithArcWithCenter_radius_startAngle_endAngle_(
                NSMakePoint(cx, cy), raggio - 9, self.giro, self.giro + 90
            )
            arco.setLineWidth_(3)
            arco.setLineCapStyle_(1)
            arco.stroke()
            return

        colore = NSColor.systemRedColor()
        if self.sopra:
            colore = colore.blendedColorWithFraction_ofColor_(0.18, NSColor.whiteColor())
        colore.setFill()

        if self.stato == REGISTRA:
            lato = REC * 0.34          # quadrato di stop
            NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                NSMakeRect(cx - lato / 2, cy - lato / 2, lato, lato), 4, 4
            ).fill()
        else:
            interno = raggio - 7        # cerchio pieno
            NSBezierPath.bezierPathWithOvalInRect_(
                NSMakeRect(cx - interno, cy - interno, interno * 2, interno * 2)
            ).fill()


class Pannello(NSObject):
    @objc.python_method
    def inizializza(self, app):
        self.app = app
        self.finestra = None
        self.vista = None
        self.bottone = None
        self.etichetta_stato = None
        self.testo_view = None
        self.scroll = None
        self.b_copia = None
        self.b_svuota = None
        self.titolo = None
        self.menu_btn = None
        self.testo_mostrato = ""
        return self

    # -- misure --------------------------------------------------------------
    @objc.python_method
    def _altezza_testo(self, testo: str) -> int:
        if not testo:
            return 0
        righe = testo.count("\n") + 1 + len(testo) // 46
        return max(TESTO_MIN, min(TESTO_MAX, righe * 16 + 18))

    @objc.python_method
    def _altezza(self, testo: str) -> int:
        alto = self._altezza_testo(testo)
        blocco_testo = (H_AZIONI + 8 + alto + 16) if alto else 10
        return BORDO + blocco_testo + H_STATO + 8 + REC + 16 + H_TESTA

    # -- costruzione ---------------------------------------------------------
    @objc.python_method
    def _costruisci(self):
        vista = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, LARGO, 240))
        self.vista = vista

        self.titolo = NSTextField.labelWithString_("Dettatura")
        self.titolo.setFont_(NSFont.systemFontOfSize_weight_(13, NSFontWeightSemibold))
        self.titolo.setAlignment_(NSCenterTextAlignment)
        vista.addSubview_(self.titolo)

        self.menu_btn = NSButton.buttonWithTitle_target_action_("•••", self, "apriMenu:")
        self.menu_btn.setBordered_(False)
        self.menu_btn.setFont_(NSFont.systemFontOfSize_weight_(11, NSFontWeightRegular))
        vista.addSubview_(self.menu_btn)

        lato = REC + ALONE * 2
        self.bottone = BottoneRec.alloc().initWithFrame_(
            NSMakeRect(0, 0, lato, lato)
        ).prepara(self.app.dal_bottone)
        vista.addSubview_(self.bottone)

        self.etichetta_stato = NSTextField.labelWithString_("")
        self.etichetta_stato.setAlignment_(NSCenterTextAlignment)
        self.etichetta_stato.setFont_(
            NSFont.monospacedDigitSystemFontOfSize_weight_(11, NSFontWeightMedium)
        )
        self.etichetta_stato.setTextColor_(NSColor.secondaryLabelColor())
        vista.addSubview_(self.etichetta_stato)

        self.scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(0, 0, 10, 10))
        self.scroll.setHasVerticalScroller_(True)
        self.scroll.setAutohidesScrollers_(True)
        self.scroll.setBorderType_(NSNoBorder)
        self.scroll.setDrawsBackground_(False)
        self.testo_view = NSTextView.alloc().initWithFrame_(NSMakeRect(0, 0, 10, 10))
        self.testo_view.setEditable_(True)
        self.testo_view.setRichText_(False)
        self.testo_view.setFont_(NSFont.systemFontOfSize_(12.5))
        self.testo_view.setTextColor_(NSColor.labelColor())
        self.testo_view.setDrawsBackground_(False)
        self.testo_view.setAutoresizingMask_(NSViewWidthSizable)
        self.testo_view.textContainer().setWidthTracksTextView_(True)
        self.scroll.setDocumentView_(self.testo_view)
        vista.addSubview_(self.scroll)

        self.b_copia = NSButton.buttonWithTitle_target_action_("Copia", self, "copia:")
        self.b_copia.setKeyEquivalent_("\r")
        vista.addSubview_(self.b_copia)

        self.b_svuota = NSButton.buttonWithTitle_target_action_("Svuota", self, "svuota:")
        vista.addSubview_(self.b_svuota)

        stile = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable
                 | NSWindowStyleMaskUtilityWindow | NSWindowStyleMaskFullSizeContentView)
        self.finestra = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, LARGO, 200), stile, NSBackingStoreBuffered, False
        )
        self.finestra.setTitleVisibility_(NSWindowTitleHidden)
        self.finestra.setTitlebarAppearsTransparent_(True)
        self.finestra.setMovableByWindowBackground_(True)   # si trascina da ovunque
        self.finestra.setLevel_(NSFloatingWindowLevel)      # resta sopra le altre
        self.finestra.setHidesOnDeactivate_(False)
        # senza questo, chiuderla la distrugge e riaprirla fa crashare l'app
        self.finestra.setReleasedWhenClosed_(False)
        self.finestra.setContentView_(vista)

    @objc.python_method
    def _disponi(self, testo: str):
        """L'unico posto dove si decide dove sta ogni cosa."""
        alto_testo = self._altezza_testo(testo)
        H = self._altezza(testo)
        largo = LARGO - 2 * BORDO
        lato = REC + ALONE * 2
        self.vista.setFrame_(NSMakeRect(0, 0, LARGO, H))

        # si dispone dal basso: azioni, testo, etichetta, cerchio, intestazione
        mostra = alto_testo > 0
        for v in (self.scroll, self.b_copia, self.b_svuota):
            v.setHidden_(not mostra)

        if mostra:
            self.b_copia.setFrame_(NSMakeRect(LARGO - BORDO - 88, BORDO, 88, H_AZIONI))
            self.b_svuota.setFrame_(NSMakeRect(BORDO, BORDO, 78, H_AZIONI))
            y_testo = BORDO + H_AZIONI + 8
            self.scroll.setFrame_(NSMakeRect(BORDO, y_testo, largo, alto_testo))
            y = y_testo + alto_testo + 16
        else:
            y = BORDO + 10

        self.etichetta_stato.setFrame_(NSMakeRect(BORDO, y, largo, H_STATO))

        # il cerchio sta sopra l'etichetta; la view è più grande per via dell'anello
        base_cerchio = y + H_STATO + 8
        self.bottone.setFrame_(
            NSMakeRect((LARGO - lato) / 2, base_cerchio - ALONE, lato, lato)
        )

        y_titolo = base_cerchio + REC + 16
        self.titolo.setFrame_(NSMakeRect(BORDO + 40, y_titolo, largo - 80, 18))
        self.menu_btn.setFrame_(NSMakeRect(LARGO - BORDO - 32, y_titolo - 2, 32, 20))

        self.testo_mostrato = testo
        cornice = self.finestra.frameRectForContentRect_(NSMakeRect(0, 0, LARGO, H))
        ora = self.finestra.frame()
        alto = ora.origin.y + ora.size.height          # il bordo superiore non si muove:
        self.finestra.setFrame_display_(                # la finestra cresce verso il basso
            NSMakeRect(ora.origin.x, alto - cornice.size.height,
                       cornice.size.width, cornice.size.height),
            True,
        )

    # -- aggiornamenti dallo stato dell'app -----------------------------------
    @objc.python_method
    def aggiorna(self, stato: str, etichetta: str, livello: float = 0.0):
        if self.finestra is None:
            return
        self.bottone.stato = stato
        self.bottone.livello = livello
        if stato == ELABORA:
            self.bottone.giro = (self.bottone.giro - 26) % 360
        self.bottone.setNeedsDisplay_(True)
        self.etichetta_stato.setStringValue_(etichetta)

    @objc.python_method
    def imposta_testo(self, testo: str):
        if self.finestra is None:
            self._costruisci()
        if testo != self.testo_mostrato:
            self._disponi(testo)
            self.testo_view.setString_(testo)
            if testo:
                self.testo_view.scrollRangeToVisible_((len(testo), 0))

    @objc.python_method
    def testo_corrente(self) -> str:
        return str(self.testo_view.string()) if self.testo_view is not None else ""

    # -- apertura / chiusura --------------------------------------------------
    @objc.python_method
    def e_aperto(self) -> bool:
        return self.finestra is not None and self.finestra.isVisible()

    @objc.python_method
    def _sotto_icona(self):
        """Solo la prima volta: dopo, la finestra resta dove l'hai lasciata."""
        bottone_barra = self.app._nsapp.nsstatusitem.button()
        if bottone_barra is None or bottone_barra.window() is None:
            return
        r = bottone_barra.window().convertRectToScreen_(bottone_barra.frame())
        f = self.finestra.frame()
        self.finestra.setFrameOrigin_(
            NSMakePoint(r.origin.x + r.size.width / 2 - f.size.width / 2,
                        r.origin.y - f.size.height - 6)
        )

    @objc.python_method
    def apri(self, testo: str | None = None):
        prima_volta = self.finestra is None
        if prima_volta:
            self._costruisci()
            self._disponi(testo or "")
        if testo is not None:
            self.imposta_testo(testo)
        if prima_volta and not self.finestra.setFrameUsingName_("finestra-dettatura"):
            self._sotto_icona()
        self.finestra.makeKeyAndOrderFront_(None)
        self.finestra.setFrameAutosaveName_("finestra-dettatura")
        NSApp.activateIgnoringOtherApps_(True)

    @objc.python_method
    def chiudi(self):
        if self.finestra is not None:
            self.finestra.orderOut_(None)

    @objc.python_method
    def alterna(self):
        if self.e_aperto():
            self.chiudi()
        else:
            self.apri()

    # -- azioni (selettori Objective-C) ---------------------------------------
    def copia_(self, _s):
        self.app.copia_dal_pannello()

    def svuota_(self, _s):
        self.app.svuota_pannello()

    def apriMenu_(self, _s):
        self.app.mostra_menu()
