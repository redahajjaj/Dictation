"""
La finestra della dettatura: bottone di registrazione al centro, il testo sotto.

**Dove compare.** Esce da sotto l'icona del microfono, come una finestrella che
scende. Se la trascini di fianco a Warp, quello diventa il suo posto: da lì non
la sposta più nessuno, nemmeno quando la chiudi e la riapri. Per rimandarla a
casa si chiude e si riapre l'app — niente viene scritto su disco.

Si trascina da qualsiasi punto e non sparisce quando lavori altrove.

Tutti i colori vengono dal sistema (labelColor, systemRed…), così il pannello
segue da solo il tema chiaro e scuro senza che qui ci sia una sola tinta fissa.
"""
from __future__ import annotations

import objc
from AppKit import (
    NSApp,
    NSAttributedString,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
    NSBezierPath,
    NSTimer,
    NSBackingStoreBuffered,
    NSFloatingWindowLevel,
    NSPanel,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskFullSizeContentView,
    NSWindowStyleMaskTitled,
    NSWindowStyleMaskUtilityWindow,
    NSWindowTitleHidden,
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
    NSScreen,
    NSScrollView,
    NSTextField,
    NSTextView,
    NSTrackingActiveInActiveApp,
    NSTrackingArea,
    NSTrackingMouseEnteredAndExited,
    NSView,
    NSViewController,
    NSViewWidthSizable,
    NSWindow,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSWindowDidMoveNotification,
)
from Foundation import NSNotificationCenter, NSObject, NSPointInRect

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

STACCO_ICONA = 6      # quanto la finestra sta sotto l'icona del microfono
MARGINE_SCHERMO = 8   # quanto respiro lasciarle dai bordi dello schermo

# La posizione non si salva più su disco: la finestra esce da sotto l'icona a
# ogni comparsa, finché non la trascini tu. Questo nome resta solo per cancellare
# ciò che le versioni vecchie avevano già scritto nel plist (vedi _costruisci).
NOME_SALVATAGGIO_VECCHIO = "finestra-dettatura"

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


class Conferma(NSView):
    """Il lampo blu dopo «Copia»: un bordo e un velo che sfumano in mezzo secondo.

    Non è decorazione: è la risposta alla domanda «l'ha preso davvero?», data
    senza far sparire la finestra e senza scrivere altre parole da leggere.
    """

    @objc.python_method
    def prepara(self):
        self.forza = 0.0
        self.timer = None
        return self

    def hitTest_(self, _punto):
        return None          # trasparente ai clic: sta sopra a tutto

    @objc.python_method
    def lampeggia(self):
        self.forza = 1.0
        self.setHidden_(False)
        self.setNeedsDisplay_(True)
        if self.timer is not None:
            self.timer.invalidate()
        self.timer = NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
            1.0 / 60, True, self._passo
        )

    @objc.python_method
    def _passo(self, timer):
        self.forza -= 0.028
        if self.forza <= 0:
            self.forza = 0.0
            self.setHidden_(True)
            timer.invalidate()
            self.timer = None
        self.setNeedsDisplay_(True)

    def drawRect_(self, _r):
        if self.forza <= 0:
            return
        blu = NSColor.controlAccentColor()
        b = self.bounds()
        cornice = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            NSMakeRect(2, 2, b.size.width - 4, b.size.height - 4), 9, 9
        )
        blu.colorWithAlphaComponent_(self.forza * 0.10).setFill()
        cornice.fill()
        blu.colorWithAlphaComponent_(self.forza * 0.85).setStroke()
        cornice.setLineWidth_(3)
        cornice.stroke()


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
        self.conferma = None
        self.titolo = None
        self.menu_btn = None
        self.testo_mostrato = ""
        # Chi comanda la posizione: finché è False la finestra torna sotto
        # l'icona a ogni comparsa; al primo trascinamento passa a True e da lì
        # in poi decide Reda. Vive in RAM: riavviare l'app la rimanda a casa.
        self._spostata = False
        # L'ultima origine che abbiamo chiesto noi. Serve a non scambiare i
        # nostri spostamenti per un trascinamento (vedi finestraMossa_).
        self._atteso = None
        # Se la barra è già riuscita a mettersi sotto l'icona almeno una volta.
        # Nel primo secondo dopo l'avvio macOS non ha ancora piazzato l'icona
        # (misurato: risponde 0,0 fino a ~1,5 s), e senza questo la finestra
        # resterebbe al ripiego per tutta la giornata: le comparse sono ~1 al dì.
        self._a_casa = False
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

        self.conferma = Conferma.alloc().initWithFrame_(vista.bounds()).prepara()
        self.conferma.setHidden_(True)
        vista.addSubview_(self.conferma)

        stile = (NSWindowStyleMaskTitled | NSWindowStyleMaskClosable
                 | NSWindowStyleMaskUtilityWindow | NSWindowStyleMaskFullSizeContentView)
        self.finestra = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, LARGO, 200), stile, NSBackingStoreBuffered, False
        )
        self.finestra.setTitleVisibility_(NSWindowTitleHidden)
        self.finestra.setTitlebarAppearsTransparent_(True)
        self.finestra.setMovableByWindowBackground_(True)   # si trascina da ovunque
        self.finestra.setLevel_(NSFloatingWindowLevel)      # resta sopra le altre
        # senza questo la finestra sparisce ogni volta che clicchi su Warp:
        # è l'auto-chiusura più frequente possibile. NON TOGLIERE.
        self.finestra.setHidesOnDeactivate_(False)
        # e senza questo non si vede affatto quando Warp è a schermo intero:
        # una finestra flottante non entra da sola nello Space di un'app fullscreen
        self.finestra.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
        )
        # senza questo, chiuderla la distrugge e riaprirla fa crashare l'app
        self.finestra.setReleasedWhenClosed_(False)
        self.finestra.setContentView_(vista)

        # Quando la trascini, macOS ce lo dice: da quel momento il posto lo
        # scegli tu e la finestra smette di tornare sotto l'icona.
        NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(
            self, "finestraMossa:", NSWindowDidMoveNotification, self.finestra
        )

        # Igiene: le versioni vecchie salvavano la posizione per sempre nel plist.
        # Quel valore è ancora lì e punta a un monitor che potresti non avere più
        # (nel plist di Reda c'è x=2764, un secondo schermo scollegato). Nessuno
        # lo rilegge — l'autosave non si aggancia più — ma tenerlo è sporcizia.
        NSWindow.removeFrameUsingName_(NOME_SALVATAGGIO_VECCHIO)

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

        self.conferma.setFrame_(NSMakeRect(0, 0, LARGO, H))
        self.testo_mostrato = testo
        cornice = self.finestra.frameRectForContentRect_(NSMakeRect(0, 0, LARGO, H))
        ora = self.finestra.frame()
        alto = ora.origin.y + ora.size.height          # il bordo superiore non si muove:
        nuovo = NSMakeRect(ora.origin.x, alto - cornice.size.height,
                           cornice.size.width, cornice.size.height)
        # niente clamp qui: la finestra cresce verso il basso e deve poterlo fare
        # anche se sfora, o parcheggiata in basso si alzerebbe da sola mentre parli
        self._atteso = (round(nuovo.origin.x), round(nuovo.origin.y))
        self.finestra.setFrame_display_(nuovo, True)

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
    def _pezzo(self, testo: str, colore):
        return NSAttributedString.alloc().initWithString_attributes_(
            testo,
            {NSForegroundColorAttributeName: colore,
             NSFontAttributeName: NSFont.systemFontOfSize_(12.5)},
        )

    @objc.python_method
    def mostra_anteprima(self, fisso: str, provvisorio: str):
        """Il già acquisito in nero, quello che sta arrivando in grigio.

        Il colore dice da solo cos'è definitivo e cosa verrà riscritto quando
        la registrazione finisce: non serve spiegarlo a parole.
        """
        separatore = "\n\n" if (fisso.strip() and provvisorio) else ""
        intero = fisso + separatore + provvisorio
        if self._altezza(intero) != self._altezza(self.testo_mostrato):
            self._disponi(intero)          # ridimensiona solo se serve davvero
        else:
            self.testo_mostrato = intero

        deposito = self.testo_view.textStorage()
        deposito.beginEditing()
        deposito.setAttributedString_(self._pezzo(fisso, NSColor.labelColor()))
        if provvisorio:
            deposito.appendAttributedString_(
                self._pezzo(separatore + provvisorio, NSColor.secondaryLabelColor())
            )
        deposito.endEditing()
        self.testo_view.scrollRangeToVisible_((len(intero), 0))

    @objc.python_method
    def testo_corrente(self) -> str:
        return str(self.testo_view.string()) if self.testo_view is not None else ""

    # -- apertura / chiusura --------------------------------------------------
    @objc.python_method
    def e_aperto(self) -> bool:
        return self.finestra is not None and self.finestra.isVisible()

    @objc.python_method
    def _ancora_icona(self):
        """Dove sta l'icona del microfono, in coordinate schermo. None se non c'è.

        Può mancare davvero: barra dei menu piena (il notch ne mangia parecchia),
        Bartender o Ice che nascondono le icone, o l'app non ancora avviata del
        tutto — rumps aggancia nsstatusitem solo dentro run().
        """
        nsapp = getattr(self.app, "_nsapp", None)
        statusitem = getattr(nsapp, "nsstatusitem", None)
        bottone = statusitem.button() if statusitem is not None else None
        if bottone is None or bottone.window() is None:
            return None
        r = bottone.window().convertRectToScreen_(bottone.frame())
        # Un'icona della barra dei menu sta in cima allo schermo, sempre. Se le
        # coordinate dicono altro, il sistema non l'ha ancora piazzata (succede
        # prima che rumps abbia finito di avviarsi) e risponde (0,0): fidarsene
        # manderebbe la finestra sotto il bordo inferiore, e il clamp la
        # incollerebbe in basso a sinistra. Meglio dire che l'icona non c'è.
        cima = max(s.frame().origin.y + s.frame().size.height
                   for s in NSScreen.screens())
        if r.origin.y + r.size.height < cima - 50:
            return None
        return r

    @objc.python_method
    def _schermo_di(self, r):
        """Lo schermo che contiene il centro di r — Reda ne ha due."""
        centro = NSMakePoint(r.origin.x + r.size.width / 2,
                             r.origin.y + r.size.height / 2)
        for s in NSScreen.screens():
            if NSPointInRect(centro, s.frame()):
                return s
        return NSScreen.mainScreen()

    @objc.python_method
    def _dentro(self, r):
        """Rientra r nello schermo. Serve sul serio, non è una cintura di sicurezza:
        con l'icona vicino al bordo destro, una finestra centrata sotto di lei
        uscirebbe fuori di centinaia di punti."""
        v = self._schermo_di(r).visibleFrame()
        x, y = r.origin.x, r.origin.y
        # se la finestra è più larga (o più alta) dello schermo il clamp non ha
        # una soluzione: si appoggia all'angolo e tanto basta
        if r.size.width >= v.size.width:
            x = v.origin.x
        else:
            x = max(v.origin.x + MARGINE_SCHERMO, x)
            x = min(v.origin.x + v.size.width - r.size.width - MARGINE_SCHERMO, x)
        if r.size.height >= v.size.height:
            y = v.origin.y
        else:
            y = max(v.origin.y + MARGINE_SCHERMO, y)
            # in alto niente margine: visibleFrame finisce già sotto la barra dei
            # menu, e sommarcene un altro sfaserebbe la finestra rispetto
            # all'icona da cui deve scendere (misurato: 9 punti invece di 6)
            y = min(v.origin.y + v.size.height - r.size.height, y)
        return NSMakeRect(x, y, r.size.width, r.size.height)

    @objc.python_method
    def _muovi(self, r):
        """Sposta la finestra ricordandosi dove l'ha chiesta: così l'avviso di
        spostamento che macOS rimanda indietro non viene scambiato per una
        trascinata di Reda."""
        self._atteso = (round(r.origin.x), round(r.origin.y))
        self.finestra.setFrameOrigin_(r.origin)

    @objc.python_method
    def _casa(self):
        """Sotto l'icona del microfono, centrata. È il posto di casa della finestra.

        Torna True se l'icona c'era davvero: se no si è ripiegato altrove e vale
        la pena riprovare più tardi.
        """
        f = self.finestra.frame()
        icona = self._ancora_icona()
        if icona is None:
            # senza icona non c'è un "sotto": in alto al centro è il ripiego
            # meno sbagliato — nascere a 0,0 la metterebbe in basso a sinistra
            v = NSScreen.mainScreen().visibleFrame()
            x = v.origin.x + (v.size.width - f.size.width) / 2
            y = v.origin.y + v.size.height - f.size.height - STACCO_ICONA
        else:
            x = icona.origin.x + icona.size.width / 2 - f.size.width / 2
            y = icona.origin.y - f.size.height - STACCO_ICONA
        self._muovi(self._dentro(NSMakeRect(x, y, f.size.width, f.size.height)))
        return icona is not None

    @objc.python_method
    def _posa(self, comparsa: bool):
        """Decide se rimettere la finestra a casa. Chi l'ha trascinata comanda.

        Fuori da una comparsa non si tocca niente — se no la barra salterebbe
        sotto l'icona a ogni frase dettata. L'unica eccezione è la finestra che
        non è mai riuscita ad arrivare a casa: quella riprova, e appena ci
        riesce smette (il ripiego è sempre lo stesso punto, quindi finché
        l'icona manca la barra resta ferma lo stesso).
        """
        if self._spostata:
            return
        if comparsa or not self._a_casa:
            self._a_casa = self._casa()

    def finestraMossa_(self, _notifica):
        """L'hai trascinata: da adesso il posto lo scegli tu.

        Filtra i nostri spostamenti confrontando con l'origine che abbiamo
        chiesto, non con un contatore: un contatore si azzererebbe troppo presto
        quando il ridimensionamento diventerà animato (il frame continua a
        cambiare per 0,3 s dopo la chiamata), e ogni fotogramma passerebbe per
        una trascinata.
        """
        o = self.finestra.frame().origin
        if (self._atteso is not None
                and abs(o.x - self._atteso[0]) <= 1
                and abs(o.y - self._atteso[1]) <= 1):
            return
        self._spostata = True

    @objc.python_method
    def apri(self, testo: str | None = None):
        # "Comparsa" è il passaggio da nascosta a visibile, e non coincide con
        # questa chiamata: a fine dettatura apri() viene invocata anche su una
        # finestra già aperta (dettatura.py:523, senza guardia). Riposizionare lì
        # farebbe saltare la barra sotto l'icona a ogni frase dettata.
        comparsa = not self.e_aperto()
        if self.finestra is None:
            self._costruisci()
            # con "" e non con testo: _disponi ricorda ciò che ha disposto, e
            # imposta_testo salta il lavoro se crede che il testo sia già a video
            self._disponi("")
        if testo is not None:
            self.imposta_testo(testo)
        self._posa(comparsa)
        self.finestra.makeKeyAndOrderFront_(None)
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
    @objc.python_method
    def segnala_copia(self):
        """Lampo blu + il bottone che si dichiara, per un secondo e mezzo."""
        self.conferma.lampeggia()
        self.b_copia.setTitle_("✓ Copiato")
        self.b_copia.setBezelColor_(NSColor.controlAccentColor())
        NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
            1.5, False, lambda _t: self._ripristina_copia()
        )

    @objc.python_method
    def _ripristina_copia(self):
        if self.b_copia is not None:
            self.b_copia.setTitle_("Copia")
            self.b_copia.setBezelColor_(None)

    def copia_(self, _s):
        self.app.copia_dal_pannello()

    def svuota_(self, _s):
        self.app.svuota_pannello()

    def apriMenu_(self, _s):
        self.app.mostra_menu()
