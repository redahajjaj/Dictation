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

Il vetro è quello vero di macOS 26 (`NSGlassEffectView`, stile Regular): **si
adatta al fondo**, quindi sopra un'app scura diventa scuro. Per questo i colori
vengono tutti dal sistema (`labelColor` e compagnia fanno il flip da soli):
l'unica tinta scritta a mano è il rosso del REC.

La tinta della capsula e il filo di luce sul bordo li dipingiamo noi, dentro il
contentView (`VistaVetro` e `Filo`). **Non** con `setTintColor_`: quella macOS la
scarta quando la finestra non è key, e la barra cambiava colore a ogni clic.
"""
from __future__ import annotations

import math
import re
import time

import objc
from AppKit import (
    NSAffineTransform,
    NSAnimationContext,
    NSApp,
    NSAppearance,
    NSAppearanceNameVibrantLight,
    NSAttributedString,
    NSBackingStoreBuffered,
    NSBezierPath,
    NSButton,
    NSColor,
    NSCompositingOperationSourceOver,
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
    NSWorkspace,
)
from Foundation import (NSNotificationCenter, NSObject, NSPointInRect,
                        NSRunLoop, NSRunLoopCommonModes, NSZeroRect)

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
# La larghezza che il campo di testo avrà da grande. Serve alla NASCITA della
# scroll view, non da grande: il testo entra nel campo PRIMA che _applica gli
# dia la sua misura, e a 10 punti di larghezza il testo va a capo ogni due
# caratteri. Il campo si gonfia — misurato: 10.652 punti per 12 dettature in
# coda, contro i 560 veri — e quell'altezza NON si sgonfia più quando la barra
# si allarga, perché TextKit 2 del testo fuori dalla finestra tiene solo una
# stima e la corregge solo dove guarda. Risultato: la barra scorreva per
# migliaia di punti sopra il vetro vuoto. Misurato: nata larga 10 → rotta,
# 40 → rotta, 80 → rotta, da 136 in su → a posto.
L_TESTO_MAX = DIST_MAX - FISSO   # 436: il campo della distesa più larga
ARIA_DISTESA = 26            # sopra + sotto il blocco di testo

STACCO_ICONA = 6             # quanto la barra sta sotto l'icona del microfono
MARGINE_SCHERMO = 8          # quanto respiro lasciarle dai bordi dello schermo

# l'onda: 25 barrette da 3 punti con 2 di gap = 123 punti esatti
BARRE, LARGA_BARRA, GAP_BARRA = 25, 3.0, 2.0
ONDA_L = BARRE * LARGA_BARRA + (BARRE - 1) * GAP_BARRA
ONDA_A = 22
X_ONDA, X_CRONO, L_CRONO = 48, 182, 44
NOCC_REGISTRA_L = 248        # misurata sul prototipo, approvata il 24/8

# La tinta della capsula. NON è più `setTintColor_` del vetro: macOS la butta
# via quando la finestra non è key e la rimpiazza con un neutro, così al primo
# clic la barra saltava di 74 livelli di grigio (misurato: 129 → 203) e il
# contrasto del testo crollava a 1,6:1 — illeggibile. Dipinta a mano dentro
# `contenuto` il salto è 4 livelli, invisibile.
#
# L'alfa è bassa apposta: **meno tinta = più leggibile**, non il contrario. Dove
# il testo è chiaro, schiarire la capsula ce lo affoga. Misurato su 3 fondi × 2
# stati (bianco · scuro · foto): α0,35 → 2,6-6,3:1 · α0,28 → 2,9-6,4 ·
# **α0,20 → 3,5-6,5** · α0,16 → 3,8-7,8, ma il vetro comincia a perdere corpo.
TINTA_VETRO = (0.96, 0.20)
# Il filo di luce sul bordo: è la leva che fa leggere «vetro» invece di
# «rettangolo grigio». Oltre 1,5pt diventa un contorno disegnato, non vetro.
FILO_L, FILO_ALFA = 1.0, 0.65

# L'anello che pulsa attorno a Copia quando il testo va negli appunti. È il
# secondo pezzo della stessa risposta: la spunta verde dice COSA è successo,
# l'anello dice QUANDO — e l'occhio prende il movimento prima del colore.
# Cresce e svanisce: non lampeggia e non resta acceso, o farebbe concorrenza
# alla spunta invece di accompagnarla.
#
# 🔴 Gli 8 punti di crescita sono un tetto fisico, non un gusto: il bottone sta
# a 18 punti dal bordo alto della capsula, quindi l'anello arriva a 10 dal filo.
# Più larghi, e uscirebbe dal vetro.
ALONE_CRESCITA = 8.0         # quanto l'anello esce dalla casella del bottone
ALONE_DURATA = 0.55          # tutta la pulsazione, in secondi
ALONE_SPESSORE = 1.5         # come il filo: oltre, è un contorno disegnato
ALONE_ALFA = 0.60            # opacità di partenza, poi va a zero
SILENZIO_ONDA = 0.02

# Le transizioni. 0,30 s con una ease-out ripida: la barra parte veloce e si
# posa. `CAMediaTimingFunction` non è importabile dal venv (PyObjC non ha i
# metadati di QuartzCore): la classe si prende dal runtime, e l'unico
# costruttore esposto è `alloc().initWithControlPoints____` — quattro trattini
# bassi. `functionWithControlPoints_____` NON esiste, tira AttributeError.
#
# ANIMA si spegne dalle prove: durante il volo `frame()` torna il valore
# INTERPOLATO, e ogni controllo che misura la barra subito dopo `aggiorna()`
# leggerebbe una misura a metà strada.
ANIMA = True
DURATA_TRANSIZIONE = 0.30
DURATA_COMPARSA = 0.16   # la dissolvenza del contenuto, dopo che la capsula è
                         # arrivata: più corta del volo, o sembra un ritardo

# Il risucchio: la barra si accartoccia in una goccia sul proprio bordo alto e
# sparisce. Quando è a casa, il suo bordo alto È già sotto l'icona — quindi
# accartocciarsi sul posto È risucchiarsi sotto il microfono, senza un ramo in
# più; e quando l'hai trascinata lontano si chiude dov'è, che è l'unica cosa
# sensata: attraversare lo schermo in un quarto di secondo non è una goccia.
GOCCIA_L, GOCCIA_A = 26.0, 4.0
DURATA_RISUCCHIO = 0.26     # uscire è più svelto che entrare (0,30)
DURATA_SPARIZIONE = 0.12    # il contenuto se ne va nella prima metà del volo
# 🔴 La curva è l'OPPOSTO di CURVA. Quella è una ease-out: a un quarto del tempo
# ha già fatto il 61% della strada — la barra sparirebbe di scatto e poi
# resterebbe ferma. Questa è una ease-in: al 25% ha fatto il 9%, parte piano e
# accelera. È l'acqua che se ne va giù.
try:
    CURVA_RISUCCHIO = objc.lookUpClass("CAMediaTimingFunction").alloc(
    ).initWithControlPoints____(0.42, 0.0, 1.0, 1.0)
except Exception:
    CURVA_RISUCCHIO = None
try:
    CURVA = objc.lookUpClass("CAMediaTimingFunction").alloc().initWithControlPoints____(
        0.2, 0.0, 0.0, 1.0)
except Exception:      # niente QuartzCore: si usa la curva di sistema
    CURVA = None

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


def _simbolo(nome: str, punti: float, peso=NSFontWeightRegular):
    """Un'icona di sistema, pronta per essere tinta da chi la ospita."""
    im = NSImage.imageWithSystemSymbolName_accessibilityDescription_(nome, None)
    if im is None:
        return None
    cfg = NSImageSymbolConfiguration.configurationWithPointSize_weight_scale_(
        punti, peso, NSImageSymbolScaleMedium
    )
    im = im.imageWithSymbolConfiguration_(cfg)
    im.setTemplate_(True)      # template = si lascia colorare, e segue chiaro/scuro
    return im


# La matita di SF Symbols è disegnata a 45° esatti — misurato sul corpo del
# glifo, escludendo punta e gomma che sbilanciano il baricentro: 45,07°.
# Inclinata deve stare a circa 60, quindi 45 + 15.
GRADI_MATITA = 15
# Le icone di sistema accanto sono dritte e piene; una matita obliqua a peso
# normale, fra loro, si legge come un trattino.
PESO_BARRA = NSFontWeightMedium
# Tutti gli stati della barra dei menu nella stessa casella: ruotare fa crescere
# l'ingombro, e senza una casella comune l'icona salterebbe di larghezza a ogni
# cambio di stato. 22 = l'altezza della barra dei menu: una matita in diagonale
# occupa la casella lungo l'obliquo, quindi a parità di casella si legge più
# piccola dei simboli dritti che le stanno accanto.
CASELLA_BARRA = 22.0


def _simbolo_inclinato(nome: str, punti: float, gradi: float,
                       casella: float = CASELLA_BARRA, peso=NSFontWeightRegular):
    """Lo stesso simbolo di _simbolo, ruotato e centrato in una casella fissa.

    Resta template: la tinta continua a metterla macOS, e il chiaro/scuro pure.
    🔴 Ruotano solo i simboli fatti di sola matita (`pencil`, `applepencil`):
    nei compositi — `pencil.line`, `pencil.and.outline` — ruoterebbe anche la
    riga o il cerchio, e il disegno diventa una «L» o una «ø» sbarrata.
    """
    im = _simbolo(nome, punti, peso)
    if im is None:
        return None
    misura = im.size()

    # Ruotando, il riquadro che serve cresce. Se non ci sta nella casella, il
    # disegno si rimpicciolisce invece di farsi tagliare a un bordo in silenzio.
    rad = math.radians(gradi)
    cos, sin = abs(math.cos(rad)), abs(math.sin(rad))
    ingombro_l = misura.width * cos + misura.height * sin
    ingombro_a = misura.width * sin + misura.height * cos
    k = min(1.0, casella / ingombro_l, casella / ingombro_a) if ingombro_l else 1.0
    largo, alto = misura.width * k, misura.height * k

    def disegna(_rect):
        t = NSAffineTransform.transform()
        t.translateXBy_yBy_(casella / 2.0, casella / 2.0)
        if gradi:
            t.rotateByDegrees_(gradi)
        t.translateXBy_yBy_(-largo / 2.0, -alto / 2.0)
        t.concat()
        im.drawInRect_fromRect_operation_fraction_(
            NSMakeRect(0, 0, largo, alto), NSZeroRect,
            NSCompositingOperationSourceOver, 1.0,
        )
        return True

    fuori = NSImage.imageWithSize_flipped_drawingHandler_(
        NSMakeSize(casella, casella), False, disegna
    )
    fuori.setTemplate_(True)
    return fuori


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
        """Esc deve passare dall'unico imbuto di chiusura.

        Prima faceva `orderOut_` di suo e scavalcava `Pannello.chiudi()`: da
        quando la chiusura è un volo, Esc chiuderebbe di netto mentre il ✕ e il
        segno si risucchiano — e premuto a metà volo lascerebbe lo stato del
        volo acceso per sempre.
        (il rimando al padrone è un ciclo di ritenzione voluto: l'app non
        rilascia mai il pannello)"""
        p = getattr(self, "padrone", None)
        if p is not None:
            p.chiudi()
        else:
            self.orderOut_(None)


class VistaTrascina(NSView):
    """La superficie da cui si trascina la barra.

    `setMovableByWindowBackground_` da solo non basta: il fondo della finestra è
    trasparente e sopra ci sta il vetro, che intercetta il clic. Qui il
    trascinamento lo chiediamo noi, esplicitamente."""

    def mouseDown_(self, evento):
        self.window().performWindowDragWithEvent_(evento)


class VistaVetro(VistaTrascina):
    """Il contenuto dentro il vetro — e la superficie che ci dipinge la tinta.

    La tinta sta qui e non su `setTintColor_` del vetro perché AppKit quella la
    scarta appena la finestra non è key (vedi TINTA_VETRO). Disegnata qui invece
    è sempre la stessa, key o non key.

    Si arrotonda da sola: `clipsToBounds` di NSGlassEffectView è False, quindi il
    contentView non viene ritagliato dagli angoli tondi della capsula — senza il
    raggio, agli angoli spunterebbero quattro quadrati di tinta."""

    @objc.python_method
    def prepara(self, raggio):
        self._raggio = raggio
        return self

    @objc.python_method
    def imposta_raggio(self, raggio):
        if raggio != self._raggio:
            self._raggio = raggio
        self.setNeedsDisplay_(True)

    def drawRect_(self, _r):
        bianco, alfa = TINTA_VETRO
        NSColor.colorWithWhite_alpha_(bianco, alfa).setFill()
        NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            self.bounds(), self._raggio, self._raggio
        ).fill()


class Filo(NSView):
    """Il filo di luce lungo il bordo della capsula.

    Copre tutta la barra, quindi `hitTest_` deve tornare None: senza, si
    mangerebbe ogni clic e ammazzerebbe il trascinamento e i bottoni."""

    @objc.python_method
    def prepara(self, raggio):
        self._raggio = raggio
        return self

    @objc.python_method
    def imposta_raggio(self, raggio):
        self._raggio = raggio
        self.setNeedsDisplay_(True)

    def hitTest_(self, _p):
        return None

    def drawRect_(self, _r):
        b = self.bounds()
        r = max(0.0, self._raggio - FILO_L / 2.0)
        p = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            NSMakeRect(FILO_L / 2.0, FILO_L / 2.0,
                       b.size.width - FILO_L, b.size.height - FILO_L), r, r
        )
        p.setLineWidth_(FILO_L)
        NSColor.colorWithWhite_alpha_(1.0, FILO_ALFA).setStroke()
        p.stroke()


class Alone(NSView):
    """L'anello che pulsa attorno a Copia: la conferma «l'ha preso davvero»
    detta con un movimento invece che con una scritta.

    Sta SOPRA il bottone, quindi — come il Filo — `hitTest_` deve tornare None:
    senza, si mangerebbe il clic su Copia e il bottone smetterebbe di rispondere.

    Il tempo lo legge dall'orologio, non contando i fotogrammi. Se il run loop
    ne perde qualcuno l'anello arriva in fondo lo stesso; con un contatore, un
    run loop lento lo lascerebbe acceso per sempre."""

    @objc.python_method
    def prepara(self):
        self._t0 = None          # quando è partita la corsa; None = spento
        self._q = 0.0            # a che punto è, da 0 a 1
        self.setHidden_(True)
        return self

    def hitTest_(self, _p):
        return None              # 🔴 come il Filo. NON TOGLIERE: uccide Copia.

    @objc.python_method
    def parti(self):
        self._t0 = time.monotonic()
        self._q = 0.0
        self.setHidden_(False)
        self.setNeedsDisplay_(True)

    @objc.python_method
    def avanza(self) -> bool:
        """Un fotogramma. Torna False quando la corsa è finita."""
        if self._t0 is None:
            return False
        self._q = (time.monotonic() - self._t0) / ALONE_DURATA
        if self._q >= 1.0:
            self.spegni()
            return False
        self.setNeedsDisplay_(True)
        return True

    @objc.python_method
    def spegni(self):
        self._t0 = None
        self.setHidden_(True)

    def drawRect_(self, _r):
        if self._t0 is None:
            return
        q = max(0.0, min(1.0, self._q))
        b = self.bounds()
        cx, cy = b.size.width / 2.0, b.size.height / 2.0
        # il raggio parte dal bordo del bottone e frena arrivando, l'opacità
        # cala più in fretta: così l'anello si dissolve mentre si allarga,
        # invece di spegnersi di colpo a corsa finita
        r = (LATO_ICONA / 2.0 - 1.0) + ALONE_CRESCITA * (1.0 - (1.0 - q) ** 3)
        p = NSBezierPath.bezierPathWithOvalInRect_(
            NSMakeRect(cx - r, cy - r, 2 * r, 2 * r))
        p.setLineWidth_(ALONE_SPESSORE)
        NSColor.systemGreenColor().colorWithAlphaComponent_(
            ALONE_ALFA * (1.0 - q) ** 1.5).setStroke()
        p.stroke()


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
        self._t_spunta = None           # il timer della spunta: tenuto, per non
                                        # farlo spegnere dalla copia precedente
        self._t_alone = None            # il timer dell'anello, uno solo alla volta
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
        # Quante transizioni sono in volo. Contatore e non booleano: il battito
        # a 10 Hz può farne partire una seconda mentre la prima vola, e il
        # completion handler della prima aprirebbe il cancello troppo presto.
        self._animazioni = 0
        # Quale volo di comparsa/sparizione è in corso: None | "chiude" | "apre".
        # Diverso da _animazioni, che conta le transizioni di FORMA e può valere
        # più di uno apposta: il volo invece è uno solo.
        self._volo = None
        # 🔴 Token di generazione. Il completion handler di NSAnimationContext
        # NON si annulla: parte lo stesso a fine durata. Misurato: dopo aver
        # congelato un volo, il completion vecchio ha fatto orderOut_ e si è
        # ripreso la barra appena riaperta. Cambiare questo numero lo rende
        # innocuo. Il congelamento da solo NON basta.
        self._giro = 0
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
        raggio = min(NOCC_A / 2.0, RAGGIO_MAX)
        self.contenuto = VistaVetro.alloc().initWithFrame_(
            NSMakeRect(0, 0, NOCC_REGISTRA_L, NOCC_A)
        ).prepara(raggio)
        # La capsula ritaglia il suo contenuto: mentre cresce, testo e icone si
        # scoprono invece di comparire fuori bordo. È la NOSTRA vista, non il
        # vetro: `clipsToBounds` di NSGlassEffectView resta False e non si tocca.
        # 🔴 Da qui in poi ALONE_CRESCITA è un tetto duro, non morbido: l'anello
        # che sborda viene tagliato invece che disegnato fuori.
        self.contenuto.setClipsToBounds_(True)

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

        # Il segno che richiude, in alto a sinistra: solo nella distesa. Nella
        # nocciola sopra il microfono restano 8 punti — misurato, non ci sta
        # nessun riquadro utile. Riquadro 16 e non LATO_ICONA=28 perché il tappo
        # sinistro della distesa è un semicerchio pieno (raggio 32 = metà
        # altezza): a 28 gli angoli uscirebbero dal vetro, e 🔴 il vetro non
        # ritaglia — clipsToBounds di NSGlassEffectView è False e quello del
        # contenuto ritaglia al RETTANGOLO, quindi un glifo fuori dalla capsula
        # finisce disegnato sul desktop.
        self.b_riduci = self._icona("minus.circle", 12, "riduciClic:",
                                    "Riduci (Esc)", lato=16)
        self.contenuto.addSubview_(self.b_riduci)

        # il testo: resta modificabile, perché «Copia» copia quello che c'è
        # adesso nel campo (dettatura.py) — se l'hai corretto, vale la correzione
        self.scroll = NSScrollView.alloc().initWithFrame_(
            NSMakeRect(0, 0, L_TESTO_MAX, TESTO_ALTO_MAX))
        self.scroll.setHasVerticalScroller_(True)
        self.scroll.setAutohidesScrollers_(True)
        # 🔴 Scroller in sovrimpressione, non a lato. Con quelli classici la
        # barra si mangia 17 punti di larghezza per il cursore, il testo va a
        # capo per 17 punti, e andando a capo il cursore serve davvero: una
        # frase che ci starebbe finisce su due righe per sempre (visto).
        self.scroll.setScrollerStyle_(NSScrollerStyleOverlay)
        self.scroll.setBorderType_(NSNoBorder)
        self.scroll.setDrawsBackground_(False)
        self.testo_view = NSTextView.alloc().initWithFrame_(
            NSMakeRect(0, 0, L_TESTO_MAX, TESTO_ALTO_MAX))
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

        # Sopra i bottoni ma sotto il filo. L'ordine è tutto: sotto i bottoni
        # l'anello sparirebbe dietro l'icona, sopra il filo coprirebbe il bordo
        # della capsula. Basta scriverlo qui, prima del filo.
        lato_alone = LATO_ICONA + 2 * ALONE_CRESCITA
        self.alone = Alone.alloc().initWithFrame_(
            NSMakeRect(0, 0, lato_alone, lato_alone)
        ).prepara()
        self.contenuto.addSubview_(self.alone)

        # per ULTIMO: sotto qualsiasi altra vista il filo sparirebbe
        self.filo = Filo.alloc().initWithFrame_(
            NSMakeRect(0, 0, NOCC_REGISTRA_L, NOCC_A)
        ).prepara(raggio)
        self.contenuto.addSubview_(self.filo)

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
        self.finestra.padrone = self   # Esc: cancelOperation_ ci passa chiudi()
        # ⚠️ Dentro il vetro questa riga NON comanda: NSGlassEffectView
        # sovrascrive l'appearance del proprio sottoalbero (misurato: con la
        # finestra forzata a VibrantLight, su fondo scuro il campo di testo
        # legge VibrantDark). Chi decide i colori del contenuto è
        # `_adaptiveAppearance` del vetro. Resta perché vale per il ripiego
        # NSVisualEffectView di macOS < 26.
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
            # Regular. Clear (1) non è «vetro più forte», è vetro più sottile: e
            # il salto key/non-key passa da +41 a +90. Mai mescolarli.
            v.setStyle_(0)
            # Niente setTintColor_: la tinta la dipinge `contenuto` (VistaVetro).
            # Questa riga era l'unica causa del cambio di colore al clic.
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
    def _applica(self, forma, L, A, h_testo, nota, anima=False):
        """L'unico posto dove si decide dove sta ogni cosa.

        Con `anima` a True ogni frame passa dall'animator e vola dentro UN SOLO
        NSAnimationContext — lo stesso in cui vola la finestra. Contenuto e
        capsula si muovono insieme: mai uno a destinazione e l'altro in viaggio.

        🔴 Niente maschere di autoresizing: misurato, la mask sul vetro fa
        atterrare la finestra a `vecchia - nuova` dopo un rimpicciolimento
        grosso, e quella sui bottoni raddoppia l'aritmetica di questo metodo.
        """
        entranti = []

        def telaio(v, r):
            # Chi ENTRA non vola: si posa dove finirà e la capsula lo scopre
            # crescendo (clipsToBounds). Farlo volare da dov'era prima gli
            # farebbe attraversare la barra da parte a parte.
            (v.animator() if anima and v not in entranti else v).setFrame_(r)

        nocciola = forma != DISTESA
        cy_icona = (NOCC_A - LATO_ICONA) / 2.0 if nocciola else A - 46

        for v, visibile in (
            (self.onda, forma == REGISTRA),
            (self.crono, forma == REGISTRA),
            (self.messaggio, nocciola and forma != REGISTRA),
            (self.b_chiudi, forma == ERRORE),
            (self.b_riduci, not nocciola),
            (self.scroll, not nocciola),
            (self.conteggio, not nocciola),
            (self.nota, bool(nota)),
            (self.b_svuota, not nocciola),
            (self.b_copia, not nocciola),
            (self.menu_btn, not nocciola),
        ):
            if not visibile:
                v.setHidden_(True)          # chi esce sparisce e basta
            elif anima and v.isHidden():
                entranti.append(v)          # svelato in dissolvenza più sotto
            else:
                v.setAlphaValue_(1.0)
                v.setHidden_(False)

        # nocciola = niente bottone Copia: se l'anello stava correndo si ferma,
        # invece di girare a vuoto sopra il nulla. Fuori dal ciclo qui sopra:
        # là dentro verrebbe ri-mostrato a ogni cambio forma anche da spento.
        # E prima del gruppo: un anello già spento non deve finire fra gli
        # `entranti` e ricomparire in dissolvenza.
        if nocciola:
            self._ferma_alone()

        if anima:
            NSAnimationContext.beginGrouping()
            ctx = NSAnimationContext.currentContext()
            ctx.setDuration_(DURATA_TRANSIZIONE)   # il default è 0,25, non 0,30
            if CURVA is not None:
                ctx.setTimingFunction_(CURVA)
            # 🔴 Chi entra resta invisibile per tutto il volo e compare DOPO, in
            # dissolvenza (vedi `svela`). Farlo comparire subito significa
            # vederlo fuori dalla capsula: prende il frame di destinazione a
            # istante zero, mentre la capsula è ancora piccola — e il ritaglio
            # non lo tiene, perché al primo fotogramma la maschera del layer
            # segue ancora il modello, già arrivato. Guardato negli scatti: il
            # testo finiva scritto sul desktop, sopra il bordo della barra.
            # Prima si apre il contenitore, poi appare il contenuto.
            for v in entranti:
                v.setAlphaValue_(0.0)
                v.setHidden_(False)

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
        telaio(self.b_azione,
               NSMakeRect(X_ICONA if nocciola else 18, cy_icona, LATO_ICONA, LATO_ICONA))

        if forma == REGISTRA:
            telaio(self.onda, NSMakeRect(X_ONDA, (NOCC_A - ONDA_A) / 2.0, ONDA_L, ONDA_A))
            telaio(self.crono, NSMakeRect(X_CRONO, (NOCC_A - 19) / 2.0, L_CRONO, 19))
        elif nocciola:
            largo = L - X_MSG - CODA_MSG - (PASSO_ICONE if forma == ERRORE else 0)
            telaio(self.messaggio, NSMakeRect(X_MSG, (NOCC_A - 20) / 2.0, largo, 20))
            if forma == ERRORE:
                telaio(self.b_chiudi, NSMakeRect(L - 36, (NOCC_A - 24) / 2.0, 24, 24))
        else:
            # Il segno, sopra il microfono e nella sua stessa colonna (centro
            # x = 32, come b_azione: 18 + 28/2). È l'unico punto in alto a
            # sinistra dove un riquadro ci sta INTERO dentro la capsula: il
            # tappo è un semicerchio di raggio 32 centrato in (32, A-32), e i
            # quattro angoli di questo riquadro ne distano al massimo 31,05 —
            # 0,95 di franco, uguale per ogni altezza della barra.
            # Il bordo basso tocca esattamente il bordo alto del mic (A-18):
            # adiacenti, zero sovrapposizione di clic.
            telaio(self.b_riduci, NSMakeRect(24, A - 18, 16, 16))
            largo = L - FISSO
            blocco = h_testo + (H_NOTA if nota else 0)
            y = (A - blocco) / 2.0
            if nota:
                telaio(self.nota, NSMakeRect(X_TESTO, y, largo, H_NOTA))
                y += H_NOTA
            telaio(self.scroll, NSMakeRect(X_TESTO, y, largo, h_testo))
            telaio(self.conteggio, NSMakeRect(L - 226, A - 41, 88, 19))
            x_copia = 0.0
            for i, b in enumerate((self.b_svuota, self.b_copia, self.menu_btn)):
                x = L - 114 + i * PASSO_ICONE
                telaio(b, NSMakeRect(x, cy_icona, LATO_ICONA, LATO_ICONA))
                if b is self.b_copia:
                    x_copia = x
            # l'anello segue Copia: se la barra si allarga mentre pulsa, senza
            # questo resterebbe indietro a mezz'aria. La posizione la ricava
            # dalla stessa formula del bottone, non leggendone il frame: in volo
            # quel frame è un valore in viaggio, non la destinazione.
            lato_alone = LATO_ICONA + 2 * ALONE_CRESCITA
            telaio(self.alone, NSMakeRect(x_copia - ALONE_CRESCITA,
                                          cy_icona - ALONE_CRESCITA,
                                          lato_alone, lato_alone))

        raggio = min(A / 2.0, RAGGIO_MAX)
        cresce = A > self.finestra.frame().size.height

        def raggia():
            if NSGlassEffectView is not None:
                self.vetro.setCornerRadius_(raggio)
            else:
                self.vetro.layer().setCornerRadius_(raggio)
            # il raggio cambia con la forma (nocciola 22, distesa 32): tinta e
            # filo non lo ereditano da nessuno, glielo si deve ridire
            self.contenuto.imposta_raggio(raggio)
            self.filo.imposta_raggio(raggio)

        pieno = NSMakeRect(0, 0, L, A)
        telaio(self.contenuto, pieno)
        telaio(self.radice, pieno)
        telaio(self.vetro, pieno)
        telaio(self.filo, pieno)

        if not anima:
            raggia()
            for v in entranti:
                v.setAlphaValue_(1.0)
            self._ridimensiona(L, A)
            return

        def svela():
            """Il contenuto compare quando la capsula è arrivata."""
            if not entranti:
                return
            NSAnimationContext.beginGrouping()
            NSAnimationContext.currentContext().setDuration_(DURATA_COMPARSA)
            for v in entranti:
                if not v.isHidden():
                    v.animator().setAlphaValue_(1.0)
            NSAnimationContext.endGrouping()

        def poi():
            # Il raggio non si anima mai, ma il QUANDO conta: crescendo, un
            # raggio 32 messo subito starebbe su una barra ancora alta 44 — più
            # della metà dell'altezza — per tutti i 0,3 s.
            if cresce:
                raggia()
            svela()

        # rimpicciolendo il raggio va subito, o resterebbe grande su una barra
        # già bassa per tutta la durata del volo
        if not cresce:
            raggia()
        try:
            self._ridimensiona(L, A, True, poi)
        finally:
            NSAnimationContext.endGrouping()

    @objc.python_method
    def _ridimensiona(self, L, A, anima=False, poi=None):
        """La barra cresce dal centro e verso il basso: il bordo superiore non si
        muove e il centro nemmeno — come la Dynamic Island che si espande.

        Niente clamp verticale: parcheggiata in basso, la barra si alzerebbe da
        sola mentre parli (misurato: 246 punti di salto). Il clamp orizzontale
        invece serve sul serio — con l'icona vicino al bordo destro, una distesa
        da 720 centrata sotto di lei uscirebbe fuori di centinaia di punti.

        Il conto qui sotto è già animation-safe: campionando ogni fotogramma di
        una transizione, `origin.y + height` resta lo stesso numero.

        Con `anima` la finestra vola dentro il gruppo già aperto da `_applica`, e
        `poi` è quello che va fatto a volo finito. `invalidateShadow` sta lì
        dentro: chiamata subito, ricalcolerebbe l'ombra sulla sagoma VECCHIA e la
        barra volerebbe per tutti i 0,3 s con l'ombra della forma di partenza."""
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
        if not anima:
            self.finestra.setFrame_display_(nuovo, True)
            # AppKit può costringerci contro il bordo alto dello schermo:
            # `_atteso` deve dire quello che ci è stato DATO, non quello che
            # abbiamo chiesto, o il prossimo giro lo scambia per un trascinamento
            o = self.finestra.frame().origin
            self._atteso = (round(o.x), round(o.y))
            self.finestra.invalidateShadow()
            return

        self._animazioni += 1

        def fine():
            self._animazioni = max(0, self._animazioni - 1)
            o = self.finestra.frame().origin
            self._atteso = (round(o.x), round(o.y))
            if poi is not None:
                poi()
            self.finestra.invalidateShadow()

        NSAnimationContext.currentContext().setCompletionHandler_(fine)
        self.finestra.animator().setFrame_display_(nuovo, True)

    @objc.python_method
    def _ridisegna(self):
        """Chiamata a ogni battito (10 volte al secondo): rifà il layout solo se
        la forma è davvero cambiata, e per il resto tocca solo le scritte."""
        # cintura oltre alle bretelle di e_aperto: imposta_testo, segnala_copia
        # e il ripristino della copia arrivano qui senza passare da lì, e in
        # mezzo a un volo rifarebbero il layout sopra la goccia
        if self.finestra is None or self._volo is not None:
            return
        forma = self._forma()
        L, A, h_testo, nota = self._misure(forma)
        firma = (forma, L, A, h_testo, nota)
        if firma != self._firma:
            # `_firma is not None` salta il primissimo layout (finestra ancora al
            # frame di nascita); `isVisible()` salta i cambi a barra chiusa — e
            # lì serve davvero: `setFrameOrigin_` chiamata durante un volo viene
            # zittita, e in `apri()` il testo arriva PRIMA di `_posa`, quindi la
            # barra non uscirebbe più da sotto l'icona.
            anima = (ANIMA and self._firma is not None and self.finestra.isVisible()
                     and not NSWorkspace.sharedWorkspace()
                     .accessibilityDisplayShouldReduceMotion())
            self._firma = firma
            self._applica(forma, L, A, h_testo, nota, anima)

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
        # PRIMA il layout, POI il testo. _sincronizza_testo scrive nel campo e
        # subito dopo lo scorre in fondo: se il campo non ha ancora la
        # larghezza che gli spetta, si scorre in fondo a un'altezza che non è
        # quella vera, e la barra resta con migliaia di punti di scorrimento
        # sopra il vuoto. _ridisegna legge self._testo — già aggiornato qui
        # sopra — e non tocca mai il campo, quindi invertirli non gli toglie
        # niente. 🔴 Ma fra le due righe il CAMPO ha ancora il testo vecchio:
        # non infilarci in mezzo niente che chiami testo_corrente().
        self._ridisegna()
        self._sincronizza_testo()

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
        """🔴 Durante il risucchio la finestra è ancora a video — la sparizione
        vera sta in fondo al volo — ma per il resto del mondo la barra è già
        chiusa. Senza questa riga il battito a 10 Hz continua a chiamare
        `aggiorna()` e un cambio di forma a metà volo VINCE: la barra atterra
        visibile a misura di nocciola invece di sparire. Non è teoria: quando
        l'errore scade, l'app cambia l'etichetta e chiama `chiudi()` nello
        stesso battito.
        Mentre si APRE invece resta True: lì la barra c'è davvero."""
        return (self.finestra is not None and self.finestra.isVisible()
                and self._volo != "chiude")

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

    # -- il risucchio ---------------------------------------------------------
    @objc.python_method
    def _goccia(self, pieno):
        """Dove va a finire la barra chiudendosi: stesso centro, sul suo bordo alto.

        NON si chiede all'icona dove sta: la sua posizione può non esserci
        proprio nell'istante del volo (nei primi secondi dopo l'avvio, o con un
        gestore di menubar di mezzo). E non serve — quando la barra è a casa il
        suo bordo alto è già appena sotto l'icona, quindi accartocciarsi sul
        proprio bordo alto È risucchiarsi sotto il microfono."""
        cx = pieno.origin.x + pieno.size.width / 2.0
        alto = pieno.origin.y + pieno.size.height
        return NSMakeRect(cx - GOCCIA_L / 2.0, alto - GOCCIA_A, GOCCIA_L, GOCCIA_A)

    @objc.python_method
    def _pelle(self, L, A, anima=False):
        """Le quattro viste che formano la capsula e devono seguire la finestra.

        🔴 Misurato: la radice segue da sola (è il contentView), ma vetro,
        contenuto e filo NO. Animando la sola finestra, a metà volo la finestra
        è 133x16 e il vetro ancora 602x64: si vede un quadrato con un angolo
        tondo. Le maschere di autoresizing sono vietate qui (fanno atterrare la
        finestra nel posto sbagliato dopo un rimpicciolimento grosso): si fa a
        mano, come fa `telaio` in _applica."""
        r = NSMakeRect(0, 0, L, A)
        for v in (self.contenuto, self.radice, self.vetro, self.filo):
            (v.animator() if anima else v).setFrame_(r)

    @objc.python_method
    def _contenuti(self):
        """Quello che sta DENTRO la capsula, e che sparisce mentre si richiude.

        Non `contenuto` e non il filo: quelli SONO la capsula, e dissolverli
        farebbe arrivare una goccia scolorita invece che di vetro."""
        return (self.b_azione, self.onda, self.crono, self.messaggio,
                self.b_chiudi, self.b_riduci, self.scroll, self.conteggio,
                self.nota, self.b_svuota, self.b_copia, self.menu_btn)

    @objc.python_method
    def _animato(self) -> bool:
        """Stessa regola di _ridisegna: le prove spengono ANIMA, e chi ha chiesto
        meno movimento a macOS va rispettato anche qui."""
        return (ANIMA and not NSWorkspace.sharedWorkspace()
                .accessibilityDisplayShouldReduceMotion())

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

        Il cancello `_animazioni` viene prima di tutto. Misurato: oggi un
        ridimensionamento animato posta solo notifiche di resize e nessuna di
        spostamento, quindi da `_ridimensiona` non arriva niente. È una cintura
        per il giorno che si animerà l'entrata da sotto l'icona: un'animazione di
        sola origine posta origini intermedie che cadono tutte fuori dalla soglia
        di un punto, `_spostata` andrebbe a True al primo fotogramma, e niente in
        questo file lo rimette mai a False.
        """
        if self._animazioni > 0:
            return
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
        # 🔴 PRIMA di tutto il resto: `setFrameOrigin_` chiamata durante
        # un'animazione viene ZITTITA, e la barra si posizionerebbe dove decide
        # il volo vecchio invece che dove diciamo noi.
        self._taglia_volo()
        if testo is not None:
            self.imposta_testo(testo)
        self._posa(comparsa)
        # Solo alla comparsa vera: `apri()` viene chiamata anche su una barra
        # già aperta, a ogni fine dettatura — lì non c'è niente da far nascere.
        if not comparsa or not self._animato():
            self.finestra.makeKeyAndOrderFront_(None)
            NSApp.activateIgnoringOtherApps_(True)
            return

        pieno = self.finestra.frame()
        goccia = self._goccia(pieno)
        self._volo = "apre"
        self._giro += 1
        mio = self._giro
        self._animazioni += 1
        self._atteso = (round(goccia.origin.x), round(goccia.origin.y))
        self.finestra.setHasShadow_(False)
        self.finestra.setFrame_display_(goccia, False)
        self._pelle(GOCCIA_L, GOCCIA_A)
        for v in self._contenuti():
            v.setAlphaValue_(0.0)
        self.finestra.makeKeyAndOrderFront_(None)
        NSApp.activateIgnoringOtherApps_(True)

        def fine():
            self._animazioni = max(0, self._animazioni - 1)
            if mio != self._giro:
                return                   # tagliato da una chiusura: lascia stare
            self._volo = None
            # il frame SALVATO, non il ricalcolo: stessa deriva del risucchio
            self.finestra.setFrame_display_(pieno, False)
            o = self.finestra.frame().origin
            self._atteso = (round(o.x), round(o.y))
            self.finestra.setHasShadow_(True)
            self.finestra.invalidateShadow()
            NSAnimationContext.beginGrouping()
            NSAnimationContext.currentContext().setDuration_(DURATA_COMPARSA)
            for v in self._contenuti():
                if not v.isHidden():
                    v.animator().setAlphaValue_(1.0)
            NSAnimationContext.endGrouping()
            # NON si azzera la firma: la geometria è già giusta, e forzarla
            # farebbe ripartire un volo verso la misura in cui siamo già
            self._ridisegna()

        NSAnimationContext.beginGrouping()
        ctx = NSAnimationContext.currentContext()
        ctx.setDuration_(DURATA_TRANSIZIONE)
        if CURVA is not None:
            ctx.setTimingFunction_(CURVA)   # arrivare si fa frenando: ease-out
        ctx.setCompletionHandler_(fine)
        self._pelle(pieno.size.width, pieno.size.height, True)
        self.finestra.animator().setFrame_display_(pieno, True)
        NSAnimationContext.endGrouping()

    @objc.python_method
    def chiudi(self):
        """La barra si accartoccia in una goccia sul suo bordo alto e sparisce.

        È l'unica porta di chiusura: ci passano il segno ⊖, il ✕ dell'errore,
        Esc, il clic sull'icona e l'errore che si ritira da solo."""
        if self.finestra is None:
            return
        if self._volo == "chiude":
            return                       # già in volo: il battito non lo rilancia
        pieno = self.finestra.frame()
        if not self.finestra.isVisible() or not self._animato():
            self.finestra.orderOut_(None)
            return
        goccia = self._goccia(pieno)
        self._volo = "chiude"
        self._giro += 1
        mio = self._giro
        self._animazioni += 1            # cintura per il cancello di finestraMossa_
        self._atteso = (round(goccia.origin.x), round(goccia.origin.y))
        self._ferma_alone()
        # 🔴 l'ombra è calcolata sul RETTANGOLO della finestra: in volo si
        # vedrebbe un alone squadrato attorno alla capsula. Ricalcolarla a ogni
        # fotogramma non basta, spegnerla sì.
        self.finestra.setHasShadow_(False)
        self.finestra.invalidateShadow()

        # il contenuto se ne va nella prima metà del volo: quando la capsula è
        # già stretta non c'è più niente dentro da schiacciare
        NSAnimationContext.beginGrouping()
        NSAnimationContext.currentContext().setDuration_(DURATA_SPARIZIONE)
        for v in self._contenuti():
            if not v.isHidden():
                v.animator().setAlphaValue_(0.0)
        NSAnimationContext.endGrouping()

        def fine():
            # il decremento PRIMA del controllo sul token: _taglia_volo non
            # decrementa, e solo così il contatore resta in pari
            self._animazioni = max(0, self._animazioni - 1)
            if mio != self._giro:
                return                   # tagliato da apri(): non nascondere niente
            self._volo = None
            self._spegni(pieno)

        NSAnimationContext.beginGrouping()
        ctx = NSAnimationContext.currentContext()
        ctx.setDuration_(DURATA_RISUCCHIO)
        if CURVA_RISUCCHIO is not None:
            ctx.setTimingFunction_(CURVA_RISUCCHIO)
        ctx.setCompletionHandler_(fine)
        self._pelle(GOCCIA_L, GOCCIA_A, True)
        self.finestra.animator().setFrame_display_(goccia, True)
        NSAnimationContext.endGrouping()

    @objc.python_method
    def _spegni(self, pieno):
        """Nasconde la barra e la rimette a misura piena, pronta a riaprirsi.

        Non è cosmetico: `apri()` non ricostruisce niente da sola — se il testo
        è lo stesso `imposta_testo` esce subito, e `_ridisegna` vede la firma
        invariata. Una barra lasciata a 26x4 riaprirebbe come un moncone PER
        SEMPRE. L'unico attrezzo che la rifà è azzerare la firma.

        🔴 E il frame si RIMETTE QUELLO SALVATO, non si ricalcola dalla goccia:
        con una larghezza dispari il mezzo punto del centro si perde a ogni
        giro, e la barra scivola a sinistra di un punto a ogni chiusura, per
        sempre. Non si vede finché sta a casa (che la ricentra a ogni comparsa);
        appena la trascini, la deriva si accumula in eterno.

        🔴 E va fatto DOPO orderOut_: a finestra nascosta `_ridisegna` non anima,
        quindi il frame secco tiene."""
        self.finestra.orderOut_(None)
        self.finestra.setFrame_display_(pieno, False)
        o = self.finestra.frame().origin
        self._atteso = (round(o.x), round(o.y))
        for v in self._contenuti():
            v.setAlphaValue_(1.0)
        self.finestra.setHasShadow_(True)
        self._firma = None
        self._ridisegna()
        self.finestra.invalidateShadow()

    @objc.python_method
    def _taglia_volo(self):
        """Ferma di netto un volo in corso: due clic rapidi sull'icona, o una
        dettatura che finisce mentre la barra si sta chiudendo.

        🔴 DUE MOSSE, E SERVONO ENTRAMBE — misurate una per una:
        1. il TOKEN. Il completion handler non si annulla: parte lo stesso a
           fine durata. Misurato: congelato il volo, il completion vecchio ha
           comunque nascosto la barra appena riaperta.
        2. il CONGELAMENTO a durata 0 verso il frame CORRENTE. Un setFrame
           diretto NON ferma l'animator: misurato, chiesto il pieno a metà volo
           la finestra è atterrata lo stesso alla goccia.
        Per lo stesso motivo azzerare la firma va fatto DOPO il congelamento,
        mai prima: da sola prende la strada del frame secco, che viene
        inghiottito."""
        if self._volo is None:
            return
        self._giro += 1                  # il completion vecchio diventa innocuo
        self._volo = None
        ora = self.finestra.frame()
        pelle = self.vetro.frame()
        NSAnimationContext.beginGrouping()
        NSAnimationContext.currentContext().setDuration_(0.0)
        self._pelle(pelle.size.width, pelle.size.height, True)
        self.finestra.animator().setFrame_display_(ora, True)
        NSAnimationContext.endGrouping()
        self.finestra.setHasShadow_(True)
        for v in self._contenuti():
            v.setAlphaValue_(1.0)
        self._firma = None
        self._ridisegna()

    # -- azioni (selettori Objective-C) ---------------------------------------
    @objc.python_method
    def segnala_copia(self):
        """L'icona diventa una spunta verde per 1,2 s e un anello le pulsa
        attorno per mezzo secondo: è la risposta alla domanda «l'ha preso
        davvero?», data senza far sparire la barra. La spunta dice cosa è
        successo, l'anello dice quando — e l'occhio prende il movimento prima
        del colore.

        🔴 Il timer della spunta ora si tiene da parte. Prima no, e due copie a
        meno di 1,2 s l'una dall'altra facevano spegnere dal timer della prima
        la spunta della seconda dopo un attimo."""
        self._copiato = True
        self.b_copia.setImage_(_simbolo("checkmark.circle.fill", 15))
        self.b_copia.setContentTintColor_(NSColor.systemGreenColor())
        # prima il layout, poi l'anello: così parte già al posto giusto
        self._ridisegna()
        self._pulsa_alone()
        if self._t_spunta is not None:
            self._t_spunta.invalidate()
        self._t_spunta = NSTimer.scheduledTimerWithTimeInterval_repeats_block_(
            1.2, False, lambda _t: self._ripristina_copia()
        )

    @objc.python_method
    def _pulsa_alone(self):
        """Accende l'anello. Vive per conto suo: `_ridisegna` a 10 Hz non lo
        tocca, perché rifà il layout solo se la firma cambia — e copiare non la
        cambia. Se cambia lo stesso, `_applica` lo sposta senza fermarlo.

        Il timer sta in common modes: in default mode si congelerebbe appena
        macOS entra in un tracking loop, e l'anello resterebbe acceso a metà."""
        if self.finestra is None or self.b_copia.isHidden():
            return
        self._ferma_alone()          # due copie di fila = un anello solo
        self.alone.parti()
        t = NSTimer.timerWithTimeInterval_repeats_block_(
            1.0 / 60.0, True, lambda _t: self._battito_alone()
        )
        NSRunLoop.currentRunLoop().addTimer_forMode_(t, NSRunLoopCommonModes)
        self._t_alone = t

    @objc.python_method
    def _battito_alone(self):
        if self.finestra is None or not self.alone.avanza():
            self._ferma_alone()

    @objc.python_method
    def _ferma_alone(self):
        if self._t_alone is not None:
            self._t_alone.invalidate()
            self._t_alone = None
        # getattr: _applica può girare durante _costruisci, prima che l'anello
        # esista — senza, sarebbe un AttributeError muto dentro il layout
        if getattr(self, "alone", None) is not None:
            self.alone.spegni()

    @objc.python_method
    def _ripristina_copia(self):
        if self.finestra is None:
            return
        self._t_spunta = None
        self._copiato = False
        self.b_copia.setImage_(_simbolo("doc.on.doc", 15))
        self.b_copia.setContentTintColor_(None)
        self._ridisegna()

    def premi_(self, _s):
        if self._azione_attiva:
            self.app.dal_bottone()

    def chiudiClic_(self, _s):
        self.chiudi()

    def riduciClic_(self, _s):
        # stessa porta del ✕, del clic sull'icona e dell'errore che scade: così
        # il risucchio lo ereditano tutte e quattro le strade, non solo questa
        self.chiudi()

    def copia_(self, _s):
        self.app.copia_dal_pannello()

    def svuota_(self, _s):
        self.app.svuota_pannello()

    def apriMenu_(self, _s):
        self.app.mostra_menu()
