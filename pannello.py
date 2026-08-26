"""La barra della dettatura: una capsula di vetro che scende da sotto l'icona.

**Due forme, come la Dynamic Island.**

- **Nocciola** (alta 44): quando non c'è niente da leggere — riposo, mentre
  registri, mentre trascrive, quando qualcosa è andato storto. Mentre parli si
  vedono solo l'onda e il cronometro: il testo arriva tutto insieme alla fine.
- **Distesa** (alta 64, larga 420-720): quando c'è testo. La larghezza segue la
  riga più lunga, l'altezza segue le dettature che si accodano.

**Dove compare.** Esce da sotto l'icona del microfono. Se la trascini di fianco a
Warp, quello diventa il suo posto: da lì non la sposta più nessuno, nemmeno
quando la chiudi e la riapri. Per rimandarla a casa si chiude e si riapre l'app —
niente viene scritto su disco.

Si trascina da qualsiasi punto (tranne il testo e le icone) e non sparisce quando
lavori altrove.

Il vetro è quello vero di macOS 26 (`NSGlassEffectView`, tinta grigia bianco 0,88
@80%): **si adatta al fondo**, quindi sopra un'app scura diventa scuro. Per questo
i colori vengono tutti dal sistema (`labelColor` e compagnia fanno il flip da
soli): l'unica tinta scritta a mano è il rosso del REC.
"""
from __future__ import annotations

import math
import re

import objc
from AppKit import (
    NSApp,
    NSAppearance,
    NSAppearanceNameVibrantLight,
    NSAttributedString,
    NSBackingStoreBuffered,
    NSBezierPath,
    NSButton,
    NSColor,
    NSFloatingWindowLevel,
    NSFont,
    NSFontAttributeName,
    NSFontWeightMedium,
    NSFontWeightRegular,
    NSImage,
    NSImageOnly,
    NSImageScaleProportionallyDown,
    NSImageSymbolConfiguration,
    NSImageSymbolScaleMedium,
    NSLineBreakByTruncatingTail,
    NSMakePoint,
    NSMakeRect,
    NSMakeSize,
    NSNoBorder,
    NSPanel,
    NSScreen,
    NSScrollView,
    NSScrollerStyleOverlay,
    NSStringDrawingUsesLineFragmentOrigin,
    NSTextField,
    NSTextView,
    NSTimer,
    NSView,
    NSViewWidthSizable,
    NSVisualEffectView,
    NSWindow,
    NSWindowCollectionBehaviorCanJoinAllSpaces,
    NSWindowCollectionBehaviorFullScreenAuxiliary,
    NSWindowDidMoveNotification,
    NSWindowStyleMaskNonactivatingPanel,
)
from Foundation import NSNotificationCenter, NSObject, NSPointInRect

# --- gli stati che l'app ci manda -------------------------------------------
PRONTO, REGISTRA, ELABORA = "pronto", "registra", "elabora"

# Le etichette che valgono un errore. Stanno qui e non in dettatura.py perché è
# la barra a doverle riconoscere per diventare arancione: tenerle scritte due
# volte significherebbe che al primo ritocco l'errore torna a sembrare un
# messaggio qualsiasi.
ERR_CORTO = "troppo corto: riprova"
ERR_VOCE = "non ho sentito la voce"
ERR_NIENTE = "non ho sentito niente"
ERR_GENERICO = "errore: guarda il Terminale"
ERRORI = frozenset({ERR_CORTO, ERR_VOCE, ERR_NIENTE, ERR_GENERICO})

# Quando premi la scorciatoia mentre sta ancora trascrivendo: non parte una
# seconda registrazione, e la barra lo dice invece di sembrare rotta.
ATTESA = "aspetta: sto ancora trascrivendo"

# --- le forme della barra ----------------------------------------------------
RIPOSO, ERRORE, OCCUPATO, DISTESA = "riposo", "errore", "occupato", "distesa"

# --- misure: tutto il layout discende da queste ------------------------------
NOCC_A = 44                  # l'altezza della nocciola
DIST_A = 64                  # l'altezza della distesa con una o due righe
DIST_MIN, DIST_MAX = 420, 720
RAGGIO_MAX = 32              # capsula: raggio = altezza/2, ma non oltre la distesa

X_ICONA = 12                 # l'icona di sinistra, casella fissa 28x28
LATO_ICONA = 28
X_MSG = 46                   # dove attacca il messaggio dentro la nocciola
CODA_MSG = 14                # aria dopo il messaggio
NOCC_MIN = 200               # sotto questa larghezza la nocciola sembra un errore

X_TESTO, FISSO = 58, 284     # 58 a sinistra (mic + gap) + 226 a destra
MARGINE_CELL = 10            # il rendering è più largo di quanto misura la stringa
PASSO_ICONE = 36             # caselle fisse: le SF Symbols hanno misure tutte diverse
RIGA = 20                    # l'altezza di una riga di testo
H_NOTA = 18
TESTO_ALTO_MAX = 200         # oltre, il testo scorre invece di far crescere la barra
ARIA_DISTESA = 26            # sopra + sotto il blocco di testo

STACCO_ICONA = 6             # quanto la barra sta sotto l'icona del microfono
MARGINE_SCHERMO = 8          # quanto respiro lasciarle dai bordi dello schermo

# l'onda: 25 barrette da 3 punti con 2 di gap = 123 punti esatti
BARRE, LARGA_BARRA, GAP_BARRA = 25, 3.0, 2.0
ONDA_L = BARRE * LARGA_BARRA + (BARRE - 1) * GAP_BARRA
ONDA_A = 22
X_ONDA, X_CRONO, L_CRONO = 48, 182, 44
NOCC_REGISTRA_L = 248        # misurata sul prototipo, approvata il 24/8

TINTA_VETRO = (0.88, 0.80)   # variante B del ticket 01: si stacca da ogni fondo
SILENZIO_ONDA = 0.02

FONT_TESTO = NSFont.systemFontOfSize_weight_(13.5, NSFontWeightRegular)
FONT_MSG = NSFont.systemFontOfSize_weight_(12.5, NSFontWeightRegular)
FONT_NOTA = NSFont.systemFontOfSize_weight_(11.0, NSFontWeightRegular)
FONT_CRONO = NSFont.monospacedDigitSystemFontOfSize_weight_(12.0, NSFontWeightRegular)
FONT_CONTA = NSFont.monospacedDigitSystemFontOfSize_weight_(11.5, NSFontWeightMedium)

# La posizione non si salva più su disco: la barra esce da sotto l'icona a ogni
# comparsa, finché non la trascini tu. Questo nome resta solo per cancellare ciò
# che le versioni vecchie avevano già scritto nel plist (vedi _costruisci).
NOME_SALVATAGGIO_VECCHIO = "finestra-dettatura"

try:
    NSGlassEffectView = objc.lookUpClass("NSGlassEffectView")
except Exception:      # macOS più vecchio di 26: si ripiega sul vetro di prima
    NSGlassEffectView = None


def _maiuscola(s: str) -> str:
    return (s[:1].upper() + s[1:]) if s else s


def _simbolo(nome: str, punti: float):
    """Un'icona di sistema, pronta per essere tinta da chi la ospita."""
    im = NSImage.imageWithSystemSymbolName_accessibilityDescription_(nome, None)
    if im is None:
        return None
    cfg = NSImageSymbolConfiguration.configurationWithPointSize_weight_scale_(
        punti, NSFontWeightRegular, NSImageSymbolScaleMedium
    )
    im = im.imageWithSymbolConfiguration_(cfg)
    im.setTemplate_(True)      # template = si lascia colorare, e segue chiaro/scuro
    return im


def _larghezza(testo: str, font) -> float:
    a = NSAttributedString.alloc().initWithString_attributes_(
        testo, {NSFontAttributeName: font}
    )
    return a.size().width


class BarraPanel(NSPanel):
    """Un NSPanel senza titlebar torna False a canBecomeKeyWindow e non prende
    MAI la tastiera — senza un errore che te lo dica. Senza questa sottoclasse il
    testo non si potrebbe correggere a mano e Invio non copierebbe."""

    def canBecomeKeyWindow(self):
        return True

    def canBecomeMainWindow(self):
        return False

    def cancelOperation_(self, _s):
        self.orderOut_(None)      # Esc chiude la barra


class VistaTrascina(NSView):
    """La superficie da cui si trascina la barra.

    `setMovableByWindowBackground_` da solo non basta: il fondo della finestra è
    trasparente e sopra ci sta il vetro, che intercetta il clic. Qui il
    trascinamento lo chiediamo noi, esplicitamente."""

    def mouseDown_(self, evento):
        self.window().performWindowDragWithEvent_(evento)


class Onda(NSView):
    """Le barrette del volume: le ultime 25 misure, la più recente a destra.

    A silenzio diventa **una riga sola**: 25 puntini fermi sembravano un layout
    rotto (visto nel primo giro di scatti del prototipo)."""

    @objc.python_method
    def prepara(self):
        self._liv = [0.0] * BARRE
        return self

    @objc.python_method
    def spingi(self, livello: float):
        self._liv = self._liv[1:] + [max(0.0, min(1.0, float(livello)))]
        self.setNeedsDisplay_(True)

    @objc.python_method
    def azzera(self):
        self._liv = [0.0] * BARRE

    def drawRect_(self, _r):
        b = self.bounds()
        cy = b.size.height / 2.0
        if max(self._liv) <= SILENZIO_ONDA:
            NSColor.tertiaryLabelColor().setFill()
            NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                NSMakeRect(0, cy - 1, b.size.width, 2), 1, 1
            ).fill()
            return
        NSColor.labelColor().setFill()
        for i, v in enumerate(self._liv):
            h = max(2.0, v * b.size.height)
            NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
                NSMakeRect(i * (LARGA_BARRA + GAP_BARRA), cy - h / 2.0, LARGA_BARRA, h),
                LARGA_BARRA / 2.0, LARGA_BARRA / 2.0,
            ).fill()


class Pannello(NSObject):
    @objc.python_method
    def inizializza(self, app):
        self.app = app
        # La scorciatoia vera, per i tooltip. La decide il .env (DETTATURA_HOTKEY)
        # e l'app la traduce in simboli: scriverla qui a mano vorrebbe dire che al
        # primo cambio la barra mente. Il getattr serve alle prove, che passano
        # un'app finta.
        self.tasti = getattr(app, "tasti", "⌘S")
        self.finestra = None
        self.menu_btn = None            # ci si aggancia il menu di rumps
        self._testo = ""
        self._stato = PRONTO
        self._etichetta = ""
        self._livello = 0.0
        self._copiato = False           # la spunta verde, per 1,2 s
        self._firma = None              # la forma già a video: se non cambia, non si tocca
        self._azione_attiva = False     # se l'icona di sinistra fa qualcosa
        # Chi comanda la posizione: finché è False la barra torna sotto l'icona a
        # ogni comparsa; al primo trascinamento passa a True e da lì in poi decide
        # Reda. Vive in RAM: riavviare l'app la rimanda a casa.
        self._spostata = False
        # L'ultima origine che abbiamo chiesto noi. Serve a non scambiare i nostri
        # spostamenti per un trascinamento (vedi finestraMossa_).
        self._atteso = None
        # Se la barra è già riuscita a mettersi sotto l'icona almeno una volta.
        # Nel primo secondo dopo l'avvio macOS non ha ancora piazzato l'icona
        # (misurato: risponde 0,0 fino a ~1,5 s), e senza questo la barra
        # resterebbe al ripiego per tutta la giornata: le comparse sono ~1 al dì.
        self._a_casa = False
        return self

    # -- costruzione ----------------------------------------------------------
    @objc.python_method
    def _icona(self, nome, punti, azione=None, aiuto=None, lato=LATO_ICONA):
        """Un'icona dentro una casella FISSA.

        Le SF Symbols hanno misure tutte diverse (`eraser` 21x19, `doc.on.doc`
        16x18, `checkmark.circle.fill` 15x15): in una casella elastica il
        passaggio Copia → Copiato farebbe saltare il layout di 1-3 px."""
        b = NSButton.alloc().initWithFrame_(NSMakeRect(0, 0, lato, lato))
        b.setImage_(_simbolo(nome, punti))
        b.setImagePosition_(NSImageOnly)
        b.setImageScaling_(NSImageScaleProportionallyDown)
        b.setBordered_(False)
        if azione is not None:
            b.setTarget_(self)
            b.setAction_(azione)
        if aiuto:
            b.setToolTip_(aiuto)
        return b

    @objc.python_method
    def _campo(self, font, colore=None, allinea_destra=False):
        t = NSTextField.alloc().initWithFrame_(NSMakeRect(0, 0, 10, 10))
        t.setStringValue_("")
        t.setBezeled_(False)
        t.setDrawsBackground_(False)
        t.setEditable_(False)
        t.setSelectable_(False)
        t.setFont_(font)
        t.setTextColor_(colore or NSColor.labelColor())
        t.cell().setLineBreakMode_(NSLineBreakByTruncatingTail)
        return t

    @objc.python_method
    def _costruisci(self):
        self.contenuto = VistaTrascina.alloc().initWithFrame_(
            NSMakeRect(0, 0, NOCC_REGISTRA_L, NOCC_A)
        )

        # sinistra: mic quando puoi parlare, stop mentre registri, il segnale
        # quando qualcosa non va. È sempre la stessa casella: cambia solo cosa c'è dentro
        self.b_azione = self._icona("mic", 15, "premi:", f"Detta ({self.tasti})")
        self.contenuto.addSubview_(self.b_azione)

        self.onda = Onda.alloc().initWithFrame_(
            NSMakeRect(X_ONDA, 0, ONDA_L, ONDA_A)
        ).prepara()
        self.contenuto.addSubview_(self.onda)

        self.crono = self._campo(FONT_CRONO)
        self.contenuto.addSubview_(self.crono)

        self.messaggio = self._campo(FONT_MSG)
        self.contenuto.addSubview_(self.messaggio)

        self.b_chiudi = self._icona("xmark", 11, "chiudiClic:", "Chiudi", lato=24)
        self.contenuto.addSubview_(self.b_chiudi)

        # il testo: resta modificabile, perché «Copia» copia quello che c'è
        # adesso nel campo (dettatura.py) — se l'hai corretto, vale la correzione
        self.scroll = NSScrollView.alloc().initWithFrame_(NSMakeRect(0, 0, 10, 10))
        self.scroll.setHasVerticalScroller_(True)
        self.scroll.setAutohidesScrollers_(True)
        # 🔴 Scroller in sovrimpressione, non a lato. Con quelli classici la
        # barra si mangia 17 punti di larghezza per il cursore, il testo va a
        # capo per 17 punti, e andando a capo il cursore serve davvero: una
        # frase che ci starebbe finisce su due righe per sempre (visto).
        self.scroll.setScrollerStyle_(NSScrollerStyleOverlay)
        self.scroll.setBorderType_(NSNoBorder)
        self.scroll.setDrawsBackground_(False)
        self.testo_view = NSTextView.alloc().initWithFrame_(NSMakeRect(0, 0, 10, 10))
        self.testo_view.setEditable_(True)
        self.testo_view.setRichText_(False)
        self.testo_view.setFont_(FONT_TESTO)
        self.testo_view.setTextColor_(NSColor.labelColor())
        self.testo_view.setDrawsBackground_(False)
        self.testo_view.setAutoresizingMask_(NSViewWidthSizable)
        # senza questi due il testo disegnato sta 5 punti più a destra di dove lo
        # misuriamo, e la larghezza adattiva tronca una frase che ci starebbe
        self.testo_view.setTextContainerInset_(NSMakeSize(0, 0))
        self.testo_view.textContainer().setLineFragmentPadding_(0)
        self.testo_view.textContainer().setWidthTracksTextView_(True)
        self.scroll.setDocumentView_(self.testo_view)
        self.contenuto.addSubview_(self.scroll)

        self.conteggio = self._campo(FONT_CONTA, NSColor.secondaryLabelColor())
        self.contenuto.addSubview_(self.conteggio)

        self.nota = self._campo(FONT_NOTA, NSColor.secondaryLabelColor())
        self.contenuto.addSubview_(self.nota)

        self.b_svuota = self._icona("eraser", 15, "svuota:", "Svuota")
        self.b_copia = self._icona("doc.on.doc", 15, "copia:", "Copia (Invio)")
        self.b_copia.setKeyEquivalent_("\r")
        self.menu_btn = self._icona("ellipsis", 15, "apriMenu:", "Modalità e impostazioni")
        for b in (self.b_svuota, self.b_copia, self.menu_btn):
            self.contenuto.addSubview_(b)

        # -- la finestra: vetro vero, niente cornice ---------------------------
        self.finestra = BarraPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, NOCC_REGISTRA_L, NOCC_A),
            NSWindowStyleMaskNonactivatingPanel, NSBackingStoreBuffered, False,
        )
        self.finestra.setOpaque_(False)
        # LA riga che salva gli angoli: senza, gli arrotondamenti mostrano un
        # rettangolo nero e il vetro diventa cieco. setOpaque_(False) non basta.
        self.finestra.setBackgroundColor_(NSColor.clearColor())
        self.finestra.setHasShadow_(True)
        self.finestra.setLevel_(NSFloatingWindowLevel)
        self.finestra.setMovableByWindowBackground_(True)
        # senza questo la barra sparisce ogni volta che clicchi su Warp: è
        # l'auto-chiusura più frequente possibile. NON TOGLIERE.
        self.finestra.setHidesOnDeactivate_(False)
        # e senza questo non si vede affatto quando Warp è a schermo intero: una
        # finestra flottante non entra da sola nello Space di un'app fullscreen
        self.finestra.setCollectionBehavior_(
            NSWindowCollectionBehaviorCanJoinAllSpaces
            | NSWindowCollectionBehaviorFullScreenAuxiliary
        )
        # senza questo, chiuderla la distrugge e riaprirla fa crashare l'app
        self.finestra.setReleasedWhenClosed_(False)
        # è l'aspetto con cui i contrasti sono stati misurati e approvati (ticket
        # 05). Non impedisce al vetro di scurirsi sul fondo scuro: quello lo
        # decide NSGlassEffectView, e labelColor lo segue da solo.
        self.finestra.setAppearance_(
            NSAppearance.appearanceNamed_(NSAppearanceNameVibrantLight)
        )

        self.radice = VistaTrascina.alloc().initWithFrame_(
            NSMakeRect(0, 0, NOCC_REGISTRA_L, NOCC_A)
        )
        self.vetro = self._crea_vetro(NOCC_REGISTRA_L, NOCC_A)
        self.radice.addSubview_(self.vetro)
        self.finestra.setContentView_(self.radice)

        # Quando la trascini, macOS ce lo dice: da quel momento il posto lo
        # scegli tu e la barra smette di tornare sotto l'icona.
        NSNotificationCenter.defaultCenter().addObserver_selector_name_object_(
            self, "finestraMossa:", NSWindowDidMoveNotification, self.finestra
        )

        # Igiene: le versioni vecchie salvavano la posizione per sempre nel plist.
        # Quel valore è ancora lì e punta a un monitor che potresti non avere più
        # (nel plist di Reda c'è x=2764, un secondo schermo scollegato). Nessuno
        # lo rilegge — l'autosave non si aggancia più — ma tenerlo è sporcizia.
        NSWindow.removeFrameUsingName_(NOME_SALVATAGGIO_VECCHIO)

        self._firma = None
        self._ridisegna()

    @objc.python_method
    def _crea_vetro(self, L, A):
        """Il materiale. `contentView` e basta: addSubview_ sul vetro non ha
        z-order garantito, e il contenuto finirebbe dietro il materiale."""
        raggio = min(A / 2.0, RAGGIO_MAX)
        if NSGlassEffectView is not None:
            v = NSGlassEffectView.alloc().initWithFrame_(NSMakeRect(0, 0, L, A))
            v.setCornerRadius_(raggio)
            v.setStyle_(0)          # Regular (1 = Clear: mai mescolarli)
            bianco, alfa = TINTA_VETRO
            v.setTintColor_(NSColor.colorWithWhite_alpha_(bianco, alfa))
            v.setContentView_(self.contenuto)
            return v
        # macOS senza Liquid Glass: lo sfocato di prima, con gli angoli tondi
        v = NSVisualEffectView.alloc().initWithFrame_(NSMakeRect(0, 0, L, A))
        v.setState_(1)              # Active
        v.setWantsLayer_(True)
        v.layer().setCornerRadius_(raggio)
        v.layer().setMasksToBounds_(True)
        v.addSubview_(self.contenuto)
        return v

    # -- che forma ha adesso --------------------------------------------------
    @objc.python_method
    def _forma(self) -> str:
        if self._stato == REGISTRA:
            return REGISTRA
        if self._etichetta == ATTESA:
            return OCCUPATO
        if self._stato == ELABORA:
            return ELABORA
        if self._etichetta in ERRORI:
            return ERRORE
        return DISTESA if self._testo.strip() else RIPOSO

    @objc.python_method
    def _messaggio(self) -> str:
        return _maiuscola(self._etichetta)

    @objc.python_method
    def _dettature(self) -> int:
        """Quante dettature ci sono nel campo: si accodano separate da una riga
        vuota (dettatura.py incolla `precedente + "\\n\\n" + nuovo`)."""
        return len([p for p in self._testo.split("\n\n") if p.strip()])

    @objc.python_method
    def _altezza_testo(self, larghezza: float) -> int:
        """Quanto è alto questo testo mandato a capo in questa larghezza.
        Lo chiede a TextKit invece di indovinarlo dal numero di caratteri."""
        if not self._testo:
            return RIGA
        a = NSAttributedString.alloc().initWithString_attributes_(
            self._testo, {NSFontAttributeName: FONT_TESTO}
        )
        r = a.boundingRectWithSize_options_(
            NSMakeSize(larghezza, 10000), NSStringDrawingUsesLineFragmentOrigin
        )
        return int(min(TESTO_ALTO_MAX, max(RIGA, math.ceil(r.size.height))))

    @objc.python_method
    def _misure(self, forma):
        """(larghezza, altezza, altezza del testo, nota) per la forma corrente."""
        if forma == REGISTRA:
            return NOCC_REGISTRA_L, NOCC_A, 0, ""
        if forma != DISTESA:
            largo = _larghezza(self._messaggio(), FONT_MSG)
            coda = CODA_MSG + (PASSO_ICONE if forma == ERRORE else 0)
            L = max(NOCC_MIN, int(X_MSG + math.ceil(largo) + MARGINE_CELL + coda))
            return L, NOCC_A, 0, ""

        # la distesa: la larghezza segue la riga più lunga, l'altezza il testo accodato
        righe = self._testo.split("\n") or [""]
        serve = max(_larghezza(r, FONT_TESTO) for r in righe)
        L = int(min(DIST_MAX, max(DIST_MIN, FISSO + math.ceil(serve) + MARGINE_CELL)))
        h_testo = self._altezza_testo(L - FISSO)
        n = self._dettature()
        nota = f"{n} dettature in coda" if n >= 2 else ""
        blocco = h_testo + (H_NOTA if nota else 0)
        A = int(max(DIST_A, blocco + ARIA_DISTESA))
        return L, A, h_testo, nota

    # -- il layout ------------------------------------------------------------
    @objc.python_method
    def _applica(self, forma, L, A, h_testo, nota):
        """L'unico posto dove si decide dove sta ogni cosa."""
        nocciola = forma != DISTESA
        cy_icona = (NOCC_A - LATO_ICONA) / 2.0 if nocciola else A - 46

        for v, visibile in (
            (self.onda, forma == REGISTRA),
            (self.crono, forma == REGISTRA),
            (self.messaggio, nocciola and forma != REGISTRA),
            (self.b_chiudi, forma == ERRORE),
            (self.scroll, not nocciola),
            (self.conteggio, not nocciola),
            (self.nota, bool(nota)),
            (self.b_svuota, not nocciola),
            (self.b_copia, not nocciola),
            (self.menu_btn, not nocciola),
        ):
            v.setHidden_(not visibile)

        icona, punti, tinta, attiva, aiuto = {
            RIPOSO: ("mic", 15, None, True, f"Detta ({self.tasti})"),
            REGISTRA: ("stop.fill", 13, NSColor.systemRedColor(), True,
                       f"Ferma ({self.tasti})"),
            ELABORA: ("circle.dotted", 15, None, False, None),
            OCCUPATO: ("circle.dotted", 15, None, False, None),
            # arancione e non rosso: il rosso è già il REC, e se lo fosse anche
            # l'errore smetterebbe di voler dire «sto registrando»
            ERRORE: ("exclamationmark.triangle.fill", 14,
                     NSColor.systemOrangeColor(), False, None),
            DISTESA: ("mic", 15, None, True, f"Detta ({self.tasti})"),
        }[forma]
        self.b_azione.setImage_(_simbolo(icona, punti))
        self.b_azione.setContentTintColor_(tinta)
        self.b_azione.setToolTip_(aiuto or "")
        self._azione_attiva = attiva
        self.b_azione.setFrame_(
            NSMakeRect(X_ICONA if nocciola else 18, cy_icona, LATO_ICONA, LATO_ICONA)
        )

        if forma == REGISTRA:
            self.onda.setFrame_(NSMakeRect(X_ONDA, (NOCC_A - ONDA_A) / 2.0, ONDA_L, ONDA_A))
            self.crono.setFrame_(NSMakeRect(X_CRONO, (NOCC_A - 19) / 2.0, L_CRONO, 19))
        elif nocciola:
            largo = L - X_MSG - CODA_MSG - (PASSO_ICONE if forma == ERRORE else 0)
            self.messaggio.setFrame_(NSMakeRect(X_MSG, (NOCC_A - 20) / 2.0, largo, 20))
            if forma == ERRORE:
                self.b_chiudi.setFrame_(NSMakeRect(L - 36, (NOCC_A - 24) / 2.0, 24, 24))
        else:
            largo = L - FISSO
            blocco = h_testo + (H_NOTA if nota else 0)
            y = (A - blocco) / 2.0
            if nota:
                self.nota.setFrame_(NSMakeRect(X_TESTO, y, largo, H_NOTA))
                y += H_NOTA
            self.scroll.setFrame_(NSMakeRect(X_TESTO, y, largo, h_testo))
            self.conteggio.setFrame_(NSMakeRect(L - 226, A - 41, 88, 19))
            for i, b in enumerate((self.b_svuota, self.b_copia, self.menu_btn)):
                b.setFrame_(NSMakeRect(L - 114 + i * PASSO_ICONE, cy_icona,
                                       LATO_ICONA, LATO_ICONA))

        self.contenuto.setFrame_(NSMakeRect(0, 0, L, A))
        self.radice.setFrame_(NSMakeRect(0, 0, L, A))
        self.vetro.setFrame_(NSMakeRect(0, 0, L, A))
        raggio = min(A / 2.0, RAGGIO_MAX)
        if NSGlassEffectView is not None:
            self.vetro.setCornerRadius_(raggio)
        else:
            self.vetro.layer().setCornerRadius_(raggio)

        self._ridimensiona(L, A)

    @objc.python_method
    def _ridimensiona(self, L, A):
        """La barra cresce dal centro e verso il basso: il bordo superiore non si
        muove e il centro nemmeno — come la Dynamic Island che si espande.

        Niente clamp verticale: parcheggiata in basso, la barra si alzerebbe da
        sola mentre parli (misurato: 246 punti di salto). Il clamp orizzontale
        invece serve sul serio — con l'icona vicino al bordo destro, una distesa
        da 720 centrata sotto di lei uscirebbe fuori di centinaia di punti."""
        ora = self.finestra.frame()
        cornice = self.finestra.frameRectForContentRect_(NSMakeRect(0, 0, L, A))
        cx = ora.origin.x + ora.size.width / 2.0
        alto = ora.origin.y + ora.size.height
        x = cx - cornice.size.width / 2.0
        v = self._schermo_di(ora).visibleFrame()
        if cornice.size.width < v.size.width:
            x = max(v.origin.x + MARGINE_SCHERMO, x)
            x = min(v.origin.x + v.size.width - cornice.size.width - MARGINE_SCHERMO, x)
        nuovo = NSMakeRect(x, alto - cornice.size.height,
                           cornice.size.width, cornice.size.height)
        self._atteso = (round(nuovo.origin.x), round(nuovo.origin.y))
        self.finestra.setFrame_display_(nuovo, True)
        self.finestra.invalidateShadow()

    @objc.python_method
    def _ridisegna(self):
        """Chiamata a ogni battito (10 volte al secondo): rifà il layout solo se
        la forma è davvero cambiata, e per il resto tocca solo le scritte."""
        if self.finestra is None:
            return
        forma = self._forma()
        L, A, h_testo, nota = self._misure(forma)
        firma = (forma, L, A, h_testo, nota)
        if firma != self._firma:
            self._firma = firma
            self._applica(forma, L, A, h_testo, nota)

        if forma == REGISTRA:
            self.onda.spingi(self._livello)
            trovato = re.search(r"\d+:\d{2}", self._etichetta)
            self.crono.setStringValue_(trovato.group(0) if trovato else "")
        else:
            self.onda.azzera()
            if forma != DISTESA:
                self.messaggio.setStringValue_(self._messaggio())
            else:
                parole = len(self._testo.split())
                self.conteggio.setStringValue_(
                    "copiato" if self._copiato
                    else ("1 parola" if parole == 1 else f"{parole} parole")
                )
                self.nota.setStringValue_(nota)

    # -- aggiornamenti dallo stato dell'app -----------------------------------
    @objc.python_method
    def aggiorna(self, stato: str, etichetta: str, livello: float = 0.0):
        if self.finestra is None:
            return
        self._stato, self._etichetta, self._livello = stato, etichetta, livello
        self._ridisegna()

    @objc.python_method
    def imposta_testo(self, testo: str):
        if self.finestra is None:
            self._costruisci()
        if testo == self._testo:
            return
        self._testo = testo
        self._sincronizza_testo()
        self._ridisegna()

    @objc.python_method
    def _sincronizza_testo(self):
        """Scrive nel campo solo se è davvero diverso da quello che c'è: il
        confronto è con il campo, non con una nostra copia. Al primo giro la
        copia diceva «l'ho già mostrato» e il testo non compariva mai."""
        if str(self.testo_view.string()) == self._testo:
            return
        self.testo_view.setString_(self._testo)
        if self._testo:
            self.testo_view.scrollRangeToVisible_((len(self._testo), 0))

    @objc.python_method
    def mostra_anteprima(self, fisso: str, provvisorio: str):
        """Mentre parli la barra è una nocciola: non si legge testo, si vedono
        l'onda e il cronometro (ticket 02, deciso il 26/8).

        I blocchi di anteprima arrivano ogni 1,3-5 secondi: mostrarli
        allargherebbe la barra a ogni blocco — 310 → 390 → 470 punti, ognuna con
        la sua animazione — e la barra striscerebbe di lato tutto il tempo. Il
        testo arriva tutto insieme alla fine, quando c'è qualcosa da leggere.

        Il metodo resta perché dettatura.py lo chiama: cambia cosa fa, non come
        lo si chiama."""

    @objc.python_method
    def testo_corrente(self) -> str:
        return str(self.testo_view.string()) if self.finestra is not None else ""

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
        con l'icona vicino al bordo destro, una barra centrata sotto di lei
        uscirebbe fuori di centinaia di punti."""
        v = self._schermo_di(r).visibleFrame()
        x, y = r.origin.x, r.origin.y
        # se la barra è più larga (o più alta) dello schermo il clamp non ha una
        # soluzione: si appoggia all'angolo e tanto basta
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
            # menu, e sommarcene un altro sfaserebbe la barra rispetto all'icona
            # da cui deve scendere (misurato: 9 punti invece di 6)
            y = min(v.origin.y + v.size.height - r.size.height, y)
        return NSMakeRect(x, y, r.size.width, r.size.height)

    @objc.python_method
    def _muovi(self, r):
        """Sposta la barra ricordandosi dove l'ha chiesta: così l'avviso di
        spostamento che macOS rimanda indietro non viene scambiato per una
        trascinata di Reda."""
        self._atteso = (round(r.origin.x), round(r.origin.y))
        self.finestra.setFrameOrigin_(r.origin)

    @objc.python_method
    def _casa(self):
        """Sotto l'icona del microfono, centrata. È il posto di casa della barra.

        Torna True se l'icona c'era davvero: se no si è ripiegato altrove e vale
        la pena riprovare più tardi.
        """
        f = self.finestra.frame()
        icona = self._ancora_icona()
        if icona is None:
            # senza icona non c'è un "sotto": in alto al centro è il ripiego meno
            # sbagliato — nascere a 0,0 la metterebbe in basso a sinistra
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
        """Decide se rimettere la barra a casa. Chi l'ha trascinata comanda.

        Fuori da una comparsa non si tocca niente — se no la barra salterebbe
        sotto l'icona a ogni frase dettata. L'unica eccezione è la barra che non
        è mai riuscita ad arrivare a casa: quella riprova, e appena ci riesce
        smette (il ripiego è sempre lo stesso punto, quindi finché l'icona manca
        la barra resta ferma lo stesso).
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
        # barra già aperta (dettatura.py, senza guardia). Riposizionare lì
        # farebbe saltare la barra sotto l'icona a ogni frase dettata.
        comparsa = not self.e_aperto()
        if self.finestra is None:
            self._costruisci()
        if testo is not None:
            self.imposta_testo(testo)
        self._posa(comparsa)
        self.finestra.makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)

    @objc.python_method
    def chiudi(self):
        if self.finestra is not None:
            self.finestra.orderOut_(None)

    # -- azioni (selettori Objective-C) ---------------------------------------
    @objc.python_method
    def segnala_copia(self):
        """L'icona diventa una spunta verde per 1,2 s: è la risposta alla domanda
        «l'ha preso davvero?», data senza far sparire la barra."""
        self._copiato = True
        self.b_copia.setImage_(_simbolo("checkmark.circle.fill", 15))
        self.b_copia.setContentTintColor_(NSColor.systemGreenColor())
        self._ridisegna()
        NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
            1.2, False, lambda _t: self._ripristina_copia()
        )

    @objc.python_method
    def _ripristina_copia(self):
        if self.finestra is None:
            return
        self._copiato = False
        self.b_copia.setImage_(_simbolo("doc.on.doc", 15))
        self.b_copia.setContentTintColor_(None)
        self._ridisegna()

    def premi_(self, _s):
        if self._azione_attiva:
            self.app.dal_bottone()

    def chiudiClic_(self, _s):
        self.chiudi()

    def copia_(self, _s):
        self.app.copia_dal_pannello()

    def svuota_(self, _s):
        self.app.svuota_pannello()

    def apriMenu_(self, _s):
        self.app.mostra_menu()
