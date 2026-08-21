"""
Il pannello che scende dall'icona nella barra: mostra quello che hai dettato,
lo lascia correggere a mano e lo copia con un bottone.

Serve a vedere il testo *prima* di incollarlo, invece di scoprirlo dopo in Warp.
"""
from __future__ import annotations

import objc
from AppKit import (
    NSApp,
    NSBezelStyleRounded,
    NSButton,
    NSColor,
    NSFont,
    NSMakeRect,
    NSMakeSize,
    NSMinYEdge,
    NSNoBorder,
    NSPopover,
    NSPopoverBehaviorTransient,
    NSScrollView,
    NSTextField,
    NSTextView,
    NSView,
    NSViewController,
    NSViewWidthSizable,
)
from Foundation import NSObject

LARGHEZZA = 470
MARGINE = 14
ALTEZZA_BOTTONI = 32
ALTEZZA_TITOLO = 17
ALTEZZA_MIN = 210
ALTEZZA_MAX = 460


class Pannello(NSObject):
    """Un solo popover, riusato a ogni dettatura: si costruisce la prima volta."""

    # -- costruzione ---------------------------------------------------------
    # I metodi di una sottoclasse NSObject diventano selettori Objective-C, dove
    # il numero di ":" fissa gli argomenti: quelli marcati qui sotto restano
    # Python puro. Solo copia_/ridetta_ devono essere veri selettori (i bottoni
    # li chiamano come "copia:" e "ridetta:").
    @objc.python_method
    def inizializza(self, app):
        self.app = app
        self.popover = None
        self.vista = None
        self.testo_view = None
        self.scroll = None
        self.titolo = None
        self.b_copia = None
        self.b_ridetta = None
        return self

    @objc.python_method
    def _altezza_per(self, testo: str) -> int:
        """Il pannello cresce col testo, entro due limiti: né francobollo né lenzuolo."""
        righe = max(1, len(testo) // 58 + testo.count("\n") + 1)
        return max(ALTEZZA_MIN, min(ALTEZZA_MAX, 90 + righe * 17))

    @objc.python_method
    def _disponi(self, altezza: int):
        """Rimette i controlli al loro posto: il pannello cresce e si stringe col testo."""
        largo = LARGHEZZA - 2 * MARGINE
        self.vista.setFrame_(NSMakeRect(0, 0, LARGHEZZA, altezza))
        self.titolo.setFrame_(
            NSMakeRect(MARGINE, altezza - MARGINE - ALTEZZA_TITOLO, largo, ALTEZZA_TITOLO)
        )
        self.b_copia.setFrame_(NSMakeRect(LARGHEZZA - MARGINE - 110, MARGINE, 110, ALTEZZA_BOTTONI))
        self.b_ridetta.setFrame_(NSMakeRect(MARGINE, MARGINE, 100, ALTEZZA_BOTTONI))
        self.scroll.setFrame_(
            NSMakeRect(MARGINE, MARGINE * 2 + ALTEZZA_BOTTONI - 6, largo,
                       altezza - MARGINE * 3 - ALTEZZA_TITOLO - ALTEZZA_BOTTONI - 4)
        )

    @objc.python_method
    def _costruisci(self, altezza: int):
        vista = NSView.alloc().initWithFrame_(NSMakeRect(0, 0, LARGHEZZA, altezza))
        self.vista = vista

        self.titolo = NSTextField.labelWithString_("")
        self.titolo.setFont_(NSFont.systemFontOfSize_(11))
        self.titolo.setTextColor_(NSColor.secondaryLabelColor())
        vista.addSubview_(self.titolo)

        scroll = NSScrollView.alloc().initWithFrame_(
            NSMakeRect(MARGINE, 40, LARGHEZZA - 2 * MARGINE, altezza - 100)
        )
        self.scroll = scroll
        scroll.setHasVerticalScroller_(True)
        scroll.setAutohidesScrollers_(True)
        scroll.setBorderType_(NSNoBorder)
        scroll.setDrawsBackground_(False)

        self.testo_view = NSTextView.alloc().initWithFrame_(scroll.contentView().bounds())
        self.testo_view.setEditable_(True)          # correggibile prima di copiare
        self.testo_view.setRichText_(False)
        self.testo_view.setFont_(NSFont.systemFontOfSize_(13))
        self.testo_view.setTextColor_(NSColor.labelColor())
        self.testo_view.setDrawsBackground_(False)
        self.testo_view.setAutoresizingMask_(NSViewWidthSizable)
        self.testo_view.textContainer().setWidthTracksTextView_(True)
        scroll.setDocumentView_(self.testo_view)
        vista.addSubview_(scroll)

        self.b_copia = NSButton.buttonWithTitle_target_action_("Copia", self, "copia:")
        self.b_copia.setBezelStyle_(NSBezelStyleRounded)
        self.b_copia.setKeyEquivalent_("\r")        # Invio = copia
        vista.addSubview_(self.b_copia)

        self.b_ridetta = NSButton.buttonWithTitle_target_action_("Ridetta", self, "ridetta:")
        self.b_ridetta.setBezelStyle_(NSBezelStyleRounded)
        vista.addSubview_(self.b_ridetta)

        self._disponi(altezza)

        controller = NSViewController.alloc().init()
        controller.setView_(vista)

        self.popover = NSPopover.alloc().init()
        self.popover.setContentViewController_(controller)
        self.popover.setContentSize_(NSMakeSize(LARGHEZZA, altezza))
        self.popover.setBehavior_(NSPopoverBehaviorTransient)  # si chiude cliccando fuori
        self.popover.setAnimates_(True)

    # -- uso -----------------------------------------------------------------
    @objc.python_method
    def mostra(self, testo: str, intestazione: str):
        altezza = self._altezza_per(testo)
        if self.popover is None:
            self._costruisci(altezza)
        else:
            self._disponi(altezza)
        self.popover.setContentSize_(NSMakeSize(LARGHEZZA, altezza))

        self.titolo.setStringValue_(intestazione)
        self.testo_view.setString_(testo)

        bottone_barra = self.app._nsapp.nsstatusitem.button()
        if bottone_barra is None:
            return
        self.popover.showRelativeToRect_ofView_preferredEdge_(
            bottone_barra.bounds(), bottone_barra, NSMinYEdge
        )
        NSApp.activateIgnoringOtherApps_(True)
        self.testo_view.window().makeFirstResponder_(self.testo_view)

    @objc.python_method
    def chiudi(self):
        if self.popover is not None:
            self.popover.performClose_(None)

    @objc.python_method
    def testo_corrente(self) -> str:
        return str(self.testo_view.string()) if self.testo_view is not None else ""

    # -- azioni dei bottoni (selettori Objective-C) ---------------------------
    def copia_(self, _sender):
        self.app.copia_dal_pannello()

    def ridetta_(self, _sender):
        self.app.ridetta_dal_pannello()
