"""La finestra delle impostazioni: chiave Groq, storico, parole speciali.

Chiesta da Reda il 12/10: «nella finestra a scomparsa si possa gestire e
cambiare la API, aprire lo storico delle trascrizioni, e una parte con tutte
le parole speciali personali — quelle con la pronuncia un po' vaga».

Si apre dal ⚙ della barra (a riposo e sugli errori) o dal menu •••. Tre schede:

- **Chiave Groq** — quella in uso (mascherata) e se funziona; una nuova si
  incolla, si PROVA e solo se Groq la accetta si salva nel .env; il modello che
  pulisce il testo.
- **Storico** — le dettature, dalla più recente, con la ricerca; il testo
  pulito o quello grezzo, e Copia.
- **Parole speciali** — vocabolario e correzioni in una lista sola, che si
  modifica come un foglio: parola · come la sente Whisper · gruppo (archivio.py
  li legge e li riscrive senza perdere niente).

Questa è una finestra vera, e qui rubare il primo piano è giusto: ci si
scrive dentro. È l'opposto della barra (vedi `Pannello._mostra`).

Il lavoro vero lo fa l'app (`app.prova_chiave`, `app.salva_parole`…): qui c'è
solo la faccia. Le prove la costruiscono con un'app finta (prova-impostazioni.py).
"""
from __future__ import annotations

import threading
from dataclasses import replace

import objc
from AppKit import (
    NSAlert,
    NSAlertFirstButtonReturn,
    NSAlertSecondButtonReturn,
    NSApp,
    NSBackingStoreBuffered,
    NSBezelBorder,
    NSBox,
    NSBoxSeparator,
    NSButton,
    NSColor,
    NSFont,
    NSFontWeightSemibold,
    NSLineBreakByTruncatingTail,
    NSMakeRect,
    NSMakeSize,
    NSPopUpButton,
    NSScrollView,
    NSSearchField,
    NSSecureTextField,
    NSSegmentedControl,
    NSSegmentSwitchTrackingSelectOne,
    NSTableColumn,
    NSTableView,
    NSTabView,
    NSTabViewItem,
    NSTextAlignmentRight,
    NSTextField,
    NSTextView,
    NSView,
    NSViewHeightSizable,
    NSViewWidthSizable,
    NSWindow,
    NSWindowStyleMaskClosable,
    NSWindowStyleMaskMiniaturizable,
    NSWindowStyleMaskTitled,
    NSWorkspace,
)
from Foundation import NSIndexSet, NSNotFound, NSObject, NSURL
from PyObjCTools import AppHelper

from archivio import Parola

LARGO, ALTO = 760, 560
MARGINE = 20
URL_CHIAVI = "https://console.groq.com/keys"
AUTOMATICO = "Automatico (lo sceglie Dettatura)"

SCHEDE = ("chiave", "storico", "parole")


def _etichetta(testo, x, y, largo, alto=18, punti=13.0, peso=None, colore=None):
    t = NSTextField.labelWithString_(testo)
    t.setFrame_(NSMakeRect(x, y, largo, alto))
    t.setFont_(NSFont.systemFontOfSize_weight_(punti, peso) if peso is not None
               else NSFont.systemFontOfSize_(punti))
    if colore is not None:
        t.setTextColor_(colore)
    t.cell().setLineBreakMode_(NSLineBreakByTruncatingTail)
    return t


def _testo_a_capo(testo, x, y, largo, alto, punti=12.0):
    t = NSTextField.wrappingLabelWithString_(testo)
    t.setFrame_(NSMakeRect(x, y, largo, alto))
    t.setFont_(NSFont.systemFontOfSize_(punti))
    t.setTextColor_(NSColor.secondaryLabelColor())
    return t


def _bottone(titolo, x, y, largo, bersaglio, azione, alto=28):
    b = NSButton.buttonWithTitle_target_action_(titolo, bersaglio, azione)
    b.setFrame_(NSMakeRect(x, y, largo, alto))
    return b


def _separatore(x, y, largo):
    s = NSBox.alloc().initWithFrame_(NSMakeRect(x, y, largo, 1))
    s.setBoxType_(NSBoxSeparator)
    return s


def _tabella(sorgente, colonne, frame):
    """(scroll, tabella): una tabella a celle, modificabile dove serve."""
    scroll = NSScrollView.alloc().initWithFrame_(frame)
    scroll.setHasVerticalScroller_(True)
    scroll.setBorderType_(NSBezelBorder)
    tv = NSTableView.alloc().initWithFrame_(NSMakeRect(0, 0, frame.size.width, frame.size.height))
    for ident, titolo, larghezza, modificabile in colonne:
        c = NSTableColumn.alloc().initWithIdentifier_(ident)
        c.headerCell().setStringValue_(titolo)
        c.setWidth_(larghezza)
        c.setEditable_(modificabile)
        tv.addTableColumn_(c)
    tv.setUsesAlternatingRowBackgroundColors_(True)
    tv.setAllowsMultipleSelection_(True)
    tv.setDataSource_(sorgente)
    tv.setDelegate_(sorgente)
    scroll.setDocumentView_(tv)
    return scroll, tv


# ================================================================ le tabelle
class _TabellaStorico(NSObject):
    """Le righe dello storico: quando · testo (la prima riga)."""

    @objc.python_method
    def prepara(self, padrone):
        self.padrone = padrone
        self.voci = []            # quelle mostrate (filtrate dalla ricerca)
        return self

    def numberOfRowsInTableView_(self, _tv):
        return len(self.voci)

    def tableView_objectValueForTableColumn_row_(self, _tv, colonna, riga):
        if not 0 <= riga < len(self.voci):
            return ""
        v = self.voci[riga]
        if colonna.identifier() == "quando":
            giorno, _, ora = v.quando.partition(" ")
            a, m, g = giorno.split("-")
            return f"{g}/{m} {ora}"
        return " ".join(v.testo.split())

    def tableViewSelectionDidChange_(self, _notifica):
        self.padrone._mostra_trascrizione()


class _TabellaParole(NSObject):
    """Le parole speciali: si modificano scrivendo nelle celle."""

    @objc.python_method
    def prepara(self, padrone):
        self.padrone = padrone
        self.parole: list[Parola] = []   # tutte
        self.indici: list[int] = []      # quelle mostrate (filtrate dalla ricerca)
        return self

    def numberOfRowsInTableView_(self, _tv):
        return len(self.indici)

    def tableView_objectValueForTableColumn_row_(self, _tv, colonna, riga):
        if not 0 <= riga < len(self.indici):
            return ""
        return getattr(self.parole[self.indici[riga]], colonna.identifier())

    def tableView_setObjectValue_forTableColumn_row_(self, _tv, valore, colonna, riga):
        if not 0 <= riga < len(self.indici):
            return
        i = self.indici[riga]
        valore = str(valore or "")
        if getattr(self.parole[i], colonna.identifier()) == valore:
            return
        self.parole[i] = replace(self.parole[i], **{colonna.identifier(): valore})
        self.padrone._parole_cambiate()


# ================================================================ la finestra
class Impostazioni(NSObject):
    @objc.python_method
    def inizializza(self, app):
        self.app = app
        self.finestra = None
        self._modificate = False      # parole cambiate e non ancora salvate
        self._prova_n = 0             # quale prova della chiave è l'ultima
        return self

    # -- per l'app --------------------------------------------------------
    @objc.python_method
    def mostra(self, scheda: str = "chiave"):
        if self.finestra is None:
            self._costruisci()
            self.finestra.center()
        self.schede.selectTabViewItemAtIndex_(SCHEDE.index(scheda) if scheda in SCHEDE else 0)
        self._aggiorna_chiave()
        self._carica_storico()
        if not self._modificate:
            self._carica_parole()
        NSApp.activateIgnoringOtherApps_(True)
        self.finestra.makeKeyAndOrderFront_(None)

    @objc.python_method
    def e_aperta(self) -> bool:
        return self.finestra is not None and self.finestra.isVisible()

    # -- costruzione --------------------------------------------------------
    @objc.python_method
    def _costruisci(self):
        self.finestra = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            NSMakeRect(0, 0, LARGO, ALTO),
            NSWindowStyleMaskTitled | NSWindowStyleMaskClosable | NSWindowStyleMaskMiniaturizable,
            NSBackingStoreBuffered, False,
        )
        self.finestra.setTitle_("Impostazioni di Dettatura")
        # senza, chiuderla la distrugge e riaprirla fa crashare l'app (come la barra)
        self.finestra.setReleasedWhenClosed_(False)
        self.finestra.setDelegate_(self)

        self.schede = NSTabView.alloc().initWithFrame_(NSMakeRect(12, 10, LARGO - 24, ALTO - 16))
        area = self.schede.contentRect().size
        self._L, self._A = area.width, area.height
        for etichetta, costruttore in (("Chiave Groq", self._scheda_chiave),
                                       ("Storico", self._scheda_storico),
                                       ("Parole speciali", self._scheda_parole)):
            vista = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, self._L, self._A))
            costruttore(vista)
            voce = NSTabViewItem.alloc().initWithIdentifier_(etichetta)
            voce.setLabel_(etichetta)
            voce.setView_(vista)
            self.schede.addTabViewItem_(voce)
        self.finestra.contentView().addSubview_(self.schede)

    # -- la chiave -----------------------------------------------------------
    @objc.python_method
    def _scheda_chiave(self, v):
        L, A, x = self._L, self._A, MARGINE
        y = A - 40
        v.addSubview_(_etichetta("La chiave di Groq", x, y, 400, 22, 15, NSFontWeightSemibold))
        y -= 38
        v.addSubview_(_testo_a_capo(
            "Serve a trascrivere e a pulire le dettature. Sta nel file .env, leggibile solo "
            "da te, e non esce mai dal Mac se non verso Groq.", x, y, L - 2 * x, 32))

        y -= 44
        v.addSubview_(_etichetta("In uso:", x, y, 70))
        self.l_chiave = _etichetta("—", x + 70, y, 170)
        self.l_chiave.setFont_(NSFont.monospacedSystemFontOfSize_weight_(12.5, 0.0))
        v.addSubview_(self.l_chiave)
        self.l_stato = _etichetta("", x + 245, y, L - 2 * x - 245 - 100)
        v.addSubview_(self.l_stato)
        v.addSubview_(_bottone("Prova", L - x - 90, y - 6, 90, self, "provaAttuale:"))

        y -= 52
        v.addSubview_(_etichetta("Nuova chiave:", x, y, 110))
        self.campo_chiave = NSSecureTextField.alloc().initWithFrame_(
            NSMakeRect(x + 110, y - 3, L - 2 * x - 110 - 200, 24))
        self.campo_chiave.setPlaceholderString_("gsk_…")
        v.addSubview_(self.campo_chiave)
        v.addSubview_(_bottone("Incolla", L - x - 190, y - 6, 80, self, "incollaChiave:"))
        self.b_salva_chiave = _bottone("Prova e salva", L - x - 105, y - 6, 105, self,
                                       "salvaChiave:")
        v.addSubview_(self.b_salva_chiave)
        y -= 30
        self.l_esito = _etichetta("", x + 110, y, L - 2 * x - 110)
        v.addSubview_(self.l_esito)
        y -= 30
        v.addSubview_(_bottone("Crea una chiave gratis su console.groq.com ↗", x + 104, y - 6,
                               330, self, "apriConsole:"))
        y -= 34
        v.addSubview_(_testo_a_capo(
            "La nuova chiave si prova prima di salvarla: se Groq la rifiuta, resta quella "
            "di adesso. Vale dalla dettatura dopo, senza riavviare niente.",
            x + 110, y - 20, L - 2 * x - 110, 34))

        y -= 64
        v.addSubview_(_separatore(x, y, L - 2 * x))
        y -= 40
        v.addSubview_(_etichetta("Modello che pulisce il testo:", x, y, 220))
        self.modelli = NSPopUpButton.alloc().initWithFrame_pullsDown_(
            NSMakeRect(x + 220, y - 5, 320, 26), False)
        self.modelli.addItemWithTitle_(AUTOMATICO)
        self.modelli.setTarget_(self)
        self.modelli.setAction_("sceltoModello:")
        v.addSubview_(self.modelli)
        y -= 34
        v.addSubview_(_testo_a_capo(
            "«Automatico» usa il migliore attivo sul tuo account (oggi openai/gpt-oss-120b). "
            "L'elenco si aggiorna quando la chiave funziona.", x + 220, y - 16, L - 2 * x - 220, 34))

    @objc.python_method
    def _aggiorna_chiave(self):
        self.l_chiave.setStringValue_(self.app.chiave_mascherata() or "nessuna")
        self._prova(None)

    @objc.python_method
    def _prova(self, chiave):
        """Prova la chiave (None = quella in uso) in un thread: la rete non
        deve mai bloccare la finestra. Solo l'ultima prova lanciata conta."""
        self._prova_n += 1
        n = self._prova_n
        nuova = chiave is not None
        if nuova:
            self.l_esito.setTextColor_(NSColor.secondaryLabelColor())
            self.l_esito.setStringValue_("la provo con Groq…")
            self.b_salva_chiave.setEnabled_(False)
        else:
            self.l_stato.setTextColor_(NSColor.secondaryLabelColor())
            self.l_stato.setStringValue_("la provo…" if self.app.chiave_mascherata() else "")
            if not self.app.chiave_mascherata():
                return

        def lavora():
            esito = self.app.prova_chiave(chiave)
            AppHelper.callAfter(self._esito_prova, n, nuova, chiave, esito)

        threading.Thread(target=lavora, daemon=True, name="prova-chiave").start()

    @objc.python_method
    def _esito_prova(self, n, nuova, chiave, esito):
        if n != self._prova_n or self.finestra is None:
            return
        ok, messaggio, modelli = esito
        colore = NSColor.systemGreenColor() if ok else NSColor.systemRedColor()
        if modelli:
            self._riempi_modelli(modelli)
        if not nuova:
            self.l_stato.setTextColor_(colore)
            self.l_stato.setStringValue_(("✓ " if ok else "✗ ") + messaggio)
            return
        self.b_salva_chiave.setEnabled_(True)
        if not ok:
            self.l_esito.setTextColor_(colore)
            self.l_esito.setStringValue_(f"✗ {messaggio}: non l'ho salvata")
            return
        self.app.salva_chiave(chiave)
        self.campo_chiave.setStringValue_("")
        self.l_esito.setTextColor_(colore)
        self.l_esito.setStringValue_("✓ funziona, salvata: vale dalla prossima dettatura")
        self.l_chiave.setStringValue_(self.app.chiave_mascherata())
        self.l_stato.setTextColor_(colore)
        self.l_stato.setStringValue_("✓ " + messaggio)

    @objc.python_method
    def _riempi_modelli(self, modelli):
        scelto = self.app.modello_scelto()
        self.modelli.removeAllItems()
        self.modelli.addItemWithTitle_(AUTOMATICO)
        nomi = list(modelli)
        if scelto and scelto not in nomi:
            nomi.append(scelto)
        self.modelli.addItemsWithTitles_(nomi)
        self.modelli.selectItemWithTitle_(scelto or AUTOMATICO)

    def provaAttuale_(self, _s):
        self._prova(None)

    def incollaChiave_(self, _s):
        from AppKit import NSPasteboard, NSPasteboardTypeString
        testo = NSPasteboard.generalPasteboard().stringForType_(NSPasteboardTypeString) or ""
        self.campo_chiave.setStringValue_("".join(str(testo).split()))

    def salvaChiave_(self, _s):
        chiave = "".join(str(self.campo_chiave.stringValue()).split())
        if not chiave:
            self.l_esito.setTextColor_(NSColor.systemOrangeColor())
            self.l_esito.setStringValue_("incolla prima la chiave nuova")
            return
        self._prova(chiave)

    def apriConsole_(self, _s):
        NSWorkspace.sharedWorkspace().openURL_(NSURL.URLWithString_(URL_CHIAVI))

    def sceltoModello_(self, _s):
        titolo = str(self.modelli.titleOfSelectedItem() or "")
        self.app.salva_modello("" if titolo == AUTOMATICO else titolo)

    # -- lo storico ----------------------------------------------------------
    @objc.python_method
    def _scheda_storico(self, v):
        L, A, x = self._L, self._A, MARGINE
        self.cerca_storico = NSSearchField.alloc().initWithFrame_(
            NSMakeRect(x, A - 44, 300, 26))
        self.cerca_storico.setPlaceholderString_("cerca nelle dettature")
        self.cerca_storico.setTarget_(self)
        self.cerca_storico.setAction_("cercaStorico:")
        v.addSubview_(self.cerca_storico)
        self.l_quante = _etichetta("", x + 320, A - 40, L - 2 * x - 320)
        self.l_quante.setAlignment_(NSTextAlignmentRight)
        self.l_quante.setTextColor_(NSColor.secondaryLabelColor())
        v.addSubview_(self.l_quante)

        self.sorgente_storico = _TabellaStorico.alloc().init().prepara(self)
        alto_tabella = 200
        scroll, self.t_storico = _tabella(
            self.sorgente_storico,
            (("quando", "Quando", 92, False), ("testo", "Dettatura", L - 2 * x - 112, False)),
            NSMakeRect(x, A - 56 - alto_tabella, L - 2 * x, alto_tabella))
        self.t_storico.setAllowsMultipleSelection_(False)
        v.addSubview_(scroll)

        y = A - 56 - alto_tabella - 40
        self.versione = NSSegmentedControl.segmentedControlWithLabels_trackingMode_target_action_(
            ["Pulito", "Grezzo"], NSSegmentSwitchTrackingSelectOne, self, "cambiaVersione:")
        self.versione.setFrame_(NSMakeRect(x, y, 150, 26))
        self.versione.setSelectedSegment_(0)
        v.addSubview_(self.versione)
        self.l_dettaglio = _etichetta("", x + 165, y + 4, L - 2 * x - 165 - 210)
        self.l_dettaglio.setTextColor_(NSColor.secondaryLabelColor())
        v.addSubview_(self.l_dettaglio)
        v.addSubview_(_bottone("Apri il file", L - x - 200, y - 1, 100, self, "apriStorico:"))
        v.addSubview_(_bottone("Copia", L - x - 92, y - 1, 92, self, "copiaTrascrizione:"))

        alto_testo = y - 14
        s = NSScrollView.alloc().initWithFrame_(NSMakeRect(x, 6, L - 2 * x, alto_testo - 6))
        s.setHasVerticalScroller_(True)
        s.setBorderType_(NSBezelBorder)
        self.testo_storico = NSTextView.alloc().initWithFrame_(
            NSMakeRect(0, 0, L - 2 * x, alto_testo - 6))
        self.testo_storico.setEditable_(False)
        self.testo_storico.setSelectable_(True)
        self.testo_storico.setFont_(NSFont.systemFontOfSize_(13))
        self.testo_storico.setTextContainerInset_(NSMakeSize(6, 6))
        self.testo_storico.setAutoresizingMask_(NSViewWidthSizable | NSViewHeightSizable)
        s.setDocumentView_(self.testo_storico)
        v.addSubview_(s)

    @objc.python_method
    def _carica_storico(self):
        self._tutte = self.app.trascrizioni()
        self._filtra_storico()

    @objc.python_method
    def _filtra_storico(self):
        cerca = str(self.cerca_storico.stringValue() or "").strip().lower()
        voci = [t for t in self._tutte
                if not cerca or cerca in t.testo.lower() or cerca in t.grezzo.lower()]
        self.sorgente_storico.voci = voci
        self.t_storico.reloadData()
        n = len(self._tutte)
        self.l_quante.setStringValue_(
            f"{len(voci)} su {n}" if cerca else ("1 dettatura" if n == 1 else f"{n} dettature"))
        if voci:
            self.t_storico.selectRowIndexes_byExtendingSelection_(
                NSIndexSet.indexSetWithIndex_(0), False)
        self._mostra_trascrizione()

    @objc.python_method
    def _trascrizione_scelta(self):
        riga = self.t_storico.selectedRow()
        voci = self.sorgente_storico.voci
        return voci[riga] if 0 <= riga < len(voci) else None

    @objc.python_method
    def _mostra_trascrizione(self):
        t = self._trascrizione_scelta()
        if t is None:
            self.testo_storico.setString_("")
            self.l_dettaglio.setStringValue_("")
            return
        grezzo = self.versione.selectedSegment() == 1
        self.testo_storico.setString_(t.grezzo if grezzo else t.testo)
        self.l_dettaglio.setStringValue_(
            f"{t.quando} · {t.modo} · {t.secondi}s · {len(t.testo.split())} parole")

    def cercaStorico_(self, _s):
        self._filtra_storico()

    def cambiaVersione_(self, _s):
        self._mostra_trascrizione()

    def copiaTrascrizione_(self, _s):
        t = self._trascrizione_scelta()
        if t is not None:
            self.app.copia_testo(t.grezzo if self.versione.selectedSegment() == 1 else t.testo)
            self.l_dettaglio.setStringValue_("✓ copiata negli appunti")

    def apriStorico_(self, _s):
        self.app.apri_storico(None)

    # -- le parole speciali ---------------------------------------------------
    @objc.python_method
    def _scheda_parole(self, v):
        L, A, x = self._L, self._A, MARGINE
        v.addSubview_(_testo_a_capo(
            "Le parole che Dettatura deve scrivere giuste: nomi, aziende, termini tecnici. "
            "Se Whisper ne sente una in un altro modo, scrivi accanto come la sente — doppio "
            "clic sulla cella, varianti separate da virgole: da lì in poi si corregge da sola.",
            x, A - 54, L - 2 * x, 46, 12.5))
        self.cerca_parole = NSSearchField.alloc().initWithFrame_(NSMakeRect(x, A - 88, 260, 26))
        self.cerca_parole.setPlaceholderString_("cerca una parola")
        self.cerca_parole.setTarget_(self)
        self.cerca_parole.setAction_("cercaParole:")
        v.addSubview_(self.cerca_parole)
        self.l_parole = _etichetta("", x + 280, A - 84, L - 2 * x - 280)
        self.l_parole.setAlignment_(NSTextAlignmentRight)
        self.l_parole.setTextColor_(NSColor.secondaryLabelColor())
        v.addSubview_(self.l_parole)

        self.sorgente_parole = _TabellaParole.alloc().init().prepara(self)
        larghezza = L - 2 * x
        scroll, self.t_parole = _tabella(
            self.sorgente_parole,
            (("parola", "Parola", 170, True),
             ("varianti", "Whisper la sente anche come", larghezza - 170 - 150 - 20, True),
             ("gruppo", "Gruppo", 150, True)),
            NSMakeRect(x, 50, larghezza, A - 100 - 50))
        v.addSubview_(scroll)

        v.addSubview_(_bottone("+", x, 12, 36, self, "aggiungiParola:"))
        v.addSubview_(_bottone("−", x + 40, 12, 36, self, "togliParole:"))
        v.addSubview_(_bottone("Apri i file", x + 90, 12, 100, self, "apriFileParole:"))
        self.l_salvate = _etichetta("", x + 200, 18, L - 2 * x - 200 - 250)
        v.addSubview_(self.l_salvate)
        self.b_annulla = _bottone("Annulla modifiche", L - x - 245, 12, 140, self,
                                  "annullaParole:")
        v.addSubview_(self.b_annulla)
        # niente Invio su Salva: Invio chiude la cella che stai scrivendo, e
        # salverebbe a ogni parola invece che quando lo decidi tu
        self.b_salva = _bottone("Salva", L - x - 100, 12, 100, self, "salvaParole:")
        v.addSubview_(self.b_salva)
        self._segna_modificate(False)

    @objc.python_method
    def _carica_parole(self):
        self.sorgente_parole.parole = self.app.parole()
        self._segna_modificate(False)
        self._filtra_parole()

    @objc.python_method
    def _filtra_parole(self):
        cerca = str(self.cerca_parole.stringValue() or "").strip().lower()
        parole = self.sorgente_parole.parole
        self.sorgente_parole.indici = [
            i for i, p in enumerate(parole)
            if not cerca or cerca in p.parola.lower() or cerca in p.varianti.lower()
            or cerca in p.gruppo.lower()]
        self.t_parole.reloadData()
        n = len([p for p in parole if p.parola.strip()])
        storpiate = len([p for p in parole if p.parola.strip() and p.varianti.strip()])
        self.l_parole.setStringValue_(f"{n} parole · {storpiate} con le storpiature")

    @objc.python_method
    def _segna_modificate(self, si: bool):
        self._modificate = si
        self.b_salva.setEnabled_(si)
        self.b_annulla.setEnabled_(si)
        if si:
            self.l_salvate.setTextColor_(NSColor.systemOrangeColor())
            self.l_salvate.setStringValue_("modifiche non salvate")

    @objc.python_method
    def _parole_cambiate(self):
        self._segna_modificate(True)
        self._filtra_parole()

    def cercaParole_(self, _s):
        self._filtra_parole()

    def aggiungiParola_(self, _s):
        # la ricerca si svuota: una riga nuova filtrata via non si vedrebbe
        self.cerca_parole.setStringValue_("")
        parole = self.sorgente_parole.parole
        riga = self.t_parole.selectedRow()
        gruppo = (parole[self.sorgente_parole.indici[riga]].gruppo
                  if 0 <= riga < len(self.sorgente_parole.indici) else "altro")
        parole.append(Parola("", "", gruppo))
        self._parole_cambiate()
        nuova = len(self.sorgente_parole.indici) - 1
        self.t_parole.selectRowIndexes_byExtendingSelection_(
            NSIndexSet.indexSetWithIndex_(nuova), False)
        self.t_parole.scrollRowToVisible_(nuova)
        self.t_parole.editColumn_row_withEvent_select_(0, nuova, None, True)

    def togliParole_(self, _s):
        righe = self.t_parole.selectedRowIndexes()
        via = set()
        i = righe.firstIndex()
        while i != NSNotFound and i < len(self.sorgente_parole.indici):
            via.add(self.sorgente_parole.indici[i])
            i = righe.indexGreaterThanIndex_(i)
        if not via:
            return
        self.sorgente_parole.parole = [p for j, p in enumerate(self.sorgente_parole.parole)
                                       if j not in via]
        self.t_parole.deselectAll_(None)
        self._parole_cambiate()

    def annullaParole_(self, _s):
        self._carica_parole()
        self.l_salvate.setStringValue_("")

    def salvaParole_(self, _s):
        self._salva_parole()

    @objc.python_method
    def _salva_parole(self) -> bool:
        # una cella ancora in modifica non ha consegnato il suo valore: si chiude prima
        self.finestra.makeFirstResponder_(None)
        try:
            self.app.salva_parole(self.sorgente_parole.parole)
        except OSError as e:
            self.l_salvate.setTextColor_(NSColor.systemRedColor())
            self.l_salvate.setStringValue_(f"non salvate: {e}")
            return False
        self._carica_parole()
        self.l_salvate.setTextColor_(NSColor.systemGreenColor())
        self.l_salvate.setStringValue_("✓ salvate: valgono dalla prossima dettatura")
        return True

    def apriFileParole_(self, _s):
        self.app.apri_file_parole()

    # -- la chiusura con le parole non salvate --------------------------------
    def windowShouldClose_(self, _finestra):
        self.finestra.makeFirstResponder_(None)
        if not self._modificate:
            return True
        # Un foglio attaccato alla finestra, non un NSAlert libero: quelli in
        # quest'app possono nascere dietro a tutto (vedi pannello.py).
        avviso = NSAlert.alloc().init()
        avviso.setMessageText_("Hai cambiato delle parole speciali")
        avviso.setInformativeText_("Le salvo prima di chiudere?")
        avviso.addButtonWithTitle_("Salva")
        avviso.addButtonWithTitle_("Non salvare")
        avviso.addButtonWithTitle_("Annulla")

        def risposta(scelta):
            if scelta == NSAlertFirstButtonReturn:
                if self._salva_parole():
                    self.finestra.orderOut_(None)
            elif scelta == NSAlertSecondButtonReturn:
                self._carica_parole()
                self.l_salvate.setStringValue_("")
                self.finestra.orderOut_(None)

        avviso.beginSheetModalForWindow_completionHandler_(self.finestra, risposta)
        return False
