#!/usr/bin/env python3
"""Genera l'icona di Dettatura: matita bianca su terracotta.

Fondo a tinta piena, matita bianca inclinata a 60°: lo stesso glifo che sta
nella barra dei menu (`pencil` di SF Symbols + GRADI_MATITA = 15, perché SF la
disegna a 45,07°).

Python puro + PyObjC. Nessuna dipendenza nuova: niente Pillow.

GEOMETRIA — dalla specifica misurata su questa macchina (macOS 26.6.2):
  macOS 26 ridisegna comunque l'icona: corpo 824 px dentro una tela 1024,
  margine 100 px per lato, angolo reso 234 px (28,4% del corpo), più ombra e
  lucidatura messe dal sistema. La finestra utile del raggio è 12%–30% del lato
  del corpo: fuori di lì il sistema non riconosce la «piastrella» e appoggia
  l'arte su un piatto grigio 214,214,214.
  Qui disegniamo ESATTAMENTE quella geometria, così il file è insieme la
  sorgente per l'.icns e l'anteprima onesta di ciò che si vedrà. L'ombra NON la
  disegniamo: la mette il sistema, e disegnarla la raddoppierebbe.

USO:
    python icona-matita-piena.py            → anteprima + provino
    python icona-matita-piena.py --tavola   → tavola di confronto (colori/scale)
"""
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

from AppKit import (
    NSWorkspace,
    NSImage, NSImageSymbolConfiguration, NSImageSymbolScaleMedium,
    NSFontWeightRegular, NSFontWeightMedium, NSFontWeightSemibold,
    NSFontWeightBold,
    NSBitmapImageRep, NSCalibratedRGBColorSpace, NSGraphicsContext, NSColorSpace,
    NSColor, NSBezierPath, NSAffineTransform, NSFont,
    NSMakeRect, NSMakeSize, NSMakePoint, NSZeroRect, NSRectFill,
    NSRectFillUsingOperation, NSCompositingOperationSourceOver,
    NSCompositingOperationSourceAtop, NSImageInterpolationHigh,
    NSBitmapImageFileTypePNG, NSAttributedString,
    NSFontAttributeName, NSForegroundColorAttributeName,
    NSColorRenderingIntentPerceptual,
)

CARTELLA = str(Path(__file__).resolve().parent)

# ---------------------------------------------------------------- geometria --
TELA = 1024.0
CORPO = 824.0                  # quanto ne rende macOS 26, misurato
MARGINE = (TELA - CORPO) / 2   # 100
# 🔴 LA TRAPPOLA PIÙ CONTROINTUITIVA, verificata con 15 bundle veri
# (`sweep-forma.py`): disegnare la sagoma ESATTA di macOS fa RIFIUTARE l'icona.
#   `sonda-sagoma.py` misura la piastrella che il sistema rende per Calculator,
#   Notes e Obsidian: sagome identiche, corpo 824 in una tela 1024, e l'angolo
#   si mangia 252 px di lato (30,6%). NON è un rettangolo con gli angoli tondi:
#   è una superellisse piena, esponente ~4,4, senza lati davvero dritti.
#   Ho disegnato quella. Risultato: 🔴 PIATTO GRIGIO. Anche a n=6. Passa solo a
#   n=8, che ormai è un quadrato.
# Il classificatore di macOS 26 non vuole il risultato finale: vuole un
# RETTANGOLO CON GLI ANGOLI TONDI, raggio fra il 12% e il 30% del lato del
# corpo (misurato: 8% e 32% cadono sul piatto, 12%..30% passano). Poi la
# maschera squircle vera la mette lui — la sua è più tonda della mia, quindi mi
# taglia gli angoli e non resta nessun buco.
RAGGIO_FRAZIONE = 0.2246       # in mezzo alla finestra: massimo margine da entrambi i bordi

# La matita: stesso simbolo e stessa inclinazione della barra dei menu.
GRADI_MATITA = 15.0            # SF la disegna a 45,07° → 60,07°
# 🔴 La barra dei menu usa Medium (PESO_BARRA). Qui va Bold, e NON è
# un'incoerenza: 17 pt in una casella da 22 e 1024 px sono due mondi ottici.
# Misurato sul provino: a 16 px la matita Medium si riduce a una sbavatura
# grigia, la Bold resta una diagonale. Il peso lo si sceglie per la misura in
# cui si guarda, non per il nome.
PESO = NSFontWeightBold
# Altezza della matita in frazione del CORPO. 0,74 → matita lunga 0,74/sin60 =
# 88% del corpo: aggressiva, ma è la misura che sopravvive a 32 e 16 px.
ALTEZZA_MATITA = 0.74

# Il colore: COTTO PROFONDO. Perché non la grafite (che pure sarebbe il
# materiale della matita): il problema di Reda è «non so come riattivarlo», cioè
# TROVARE l'app. Un riquadro quasi nero, in una finestra del Finder o in
# Spotlight, si confonde con Terminale, VS Code e mezza cartella Applicazioni.
# Un cotto caldo e saturo è un segnale di colore riconoscibile a 16 px, dove il
# glifo non si legge più e si riconosce solo la macchia.
#
# 🔴 Perché 7A3016 e non il più acceso 8C3A1A: macOS 26 non copia l'arte, la
# trasforma in VETRO — bisello, ombra interna, il bianco che diventa un avorio
# tiepido. Misurato sulla maschera del glifo, con bundle veri
# (`contrasto-reso.py`), il vetro si mangia circa un terzo del contrasto:
#     fondo      progetto   reso 1024   reso 128   reso 32
#     8C3A1A       7,61:1      5,86:1     5,68:1    4,69:1   ← 32 px al pelo
#     7A3016       9,20:1      6,88:1     6,73:1    5,44:1   ← scelto
#     6B2A13      10,59:1      7,77:1     7,54:1    6,06:1
#     2F2A26      14,19:1     10,00:1     9,67:1    7,39:1   (grafite)
# Il contrasto da rispettare è quello RESO, non quello progettato.
COTTO_PROFONDO = (0x7A, 0x30, 0x16)
FONDO = COTTO_PROFONDO
INCHIOSTRO = (0xFF, 0xFF, 0xFF)


# ------------------------------------------------------------------ utensili --
def _rep(larg, alt):
    return NSBitmapImageRep.alloc().initWithBitmapDataPlanes_pixelsWide_pixelsHigh_bitsPerSample_samplesPerPixel_hasAlpha_isPlanar_colorSpaceName_bytesPerRow_bitsPerPixel_(
        None, int(larg), int(alt), 8, 4, True, False,
        NSCalibratedRGBColorSpace, 0, 0)


class Tela:
    """Un contesto grafico su bitmap, con `with`."""

    def __init__(self, larg, alt):
        self.rep = _rep(larg, alt)
        self.larg, self.alt = int(larg), int(alt)

    def __enter__(self):
        ctx = NSGraphicsContext.graphicsContextWithBitmapImageRep_(self.rep)
        NSGraphicsContext.saveGraphicsState()
        NSGraphicsContext.setCurrentContext_(ctx)
        ctx.setImageInterpolation_(NSImageInterpolationHigh)
        NSColor.clearColor().set()
        NSRectFill(NSMakeRect(0, 0, self.larg, self.alt))
        return self

    def __exit__(self, *_):
        NSGraphicsContext.restoreGraphicsState()
        return False

    def immagine(self):
        im = NSImage.alloc().initWithSize_(NSMakeSize(self.larg, self.alt))
        im.addRepresentation_(self.rep)
        return im


def colore(rgb, alfa=1.0):
    r, g, b = rgb
    return NSColor.colorWithSRGBRed_green_blue_alpha_(r / 255.0, g / 255.0,
                                                      b / 255.0, alfa)


def salva_png(rep, percorso):
    """Ritaggia in sRGB prima di scrivere: senza, il PNG esce con il profilo
    del display e i valori letti non sono quelli che ho chiesto."""
    srgb = rep.bitmapImageRepByConvertingToColorSpace_renderingIntent_(
        NSColorSpace.sRGBColorSpace(), NSColorRenderingIntentPerceptual)
    if srgb is None:
        srgb = rep
    dati = srgb.representationUsingType_properties_(NSBitmapImageFileTypePNG, {})
    dati.writeToFile_atomically_(percorso, True)
    return srgb


def pixel(rep, x, y):
    bpr, dati = rep.bytesPerRow(), rep.bitmapData()
    i = y * bpr + x * 4
    return tuple(dati[i:i + 4])


# ------------------------------------------------------------------- squircle --
def piastrella(x, y, larg, alt, frazione=RAGGIO_FRAZIONE):
    """La sagoma da CONSEGNARE al sistema: rettangolo con angoli tondi normali.

    Non è la forma che si vedrà — quella la disegna macOS. È la forma che macOS
    riconosce come piastrella invece di appoggiarla sul piatto grigio.
    """
    r = min(larg, alt) * frazione
    return NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
        NSMakeRect(x, y, larg, alt), r, r)


def superellisse(x, y, larg, alt, n=4.4, passi=2048):
    """La sagoma VERA di macOS 26, misurata. Serve solo per confronto: darla al
    sistema come arte fa scattare il piatto grigio (vedi RAGGIO_FRAZIONE)."""
    a, b = larg / 2.0, alt / 2.0
    cx, cy = x + a, y + b
    p = NSBezierPath.bezierPath()
    e = 2.0 / n
    for i in range(passi):
        t = 2.0 * math.pi * i / passi
        c, s = math.cos(t), math.sin(t)
        u = cx + a * math.copysign(abs(c) ** e, c)
        v = cy + b * math.copysign(abs(s) ** e, s)
        (p.moveToPoint_ if i == 0 else p.lineToPoint_)(NSMakePoint(u, v))
    p.closePath()
    return p


# --------------------------------------------------------------------- matita --
def _simbolo(nome, punti, peso):
    im = NSImage.imageWithSystemSymbolName_accessibilityDescription_(nome, None)
    if im is None:
        raise SystemExit(f"SF Symbol «{nome}» assente su questo macOS")
    cfg = NSImageSymbolConfiguration.configurationWithPointSize_weight_scale_(
        punti, peso, NSImageSymbolScaleMedium)
    im = im.imageWithSymbolConfiguration_(cfg)
    im.setTemplate_(True)
    return im


def matita_bianca(gradi=GRADI_MATITA, peso=PESO, lato=1400):
    """La matita di SF, ruotata, già bianca, su una tela quadrata.

    Torna (immagine, centro_inchiostro, larghezza_inchiostro, altezza_inchiostro)
    in coordinate della tela, con l'origine in basso a sinistra.
    🔴 Il riquadro dell'NSImage NON è il disegno: l'inchiostro riempie solo il
    78-80% del riquadro (misurato). Centrare sul riquadro sposta la matita.
    """
    im = _simbolo("pencil", 900, peso)
    ms = im.size()
    k = (lato * 0.62) / max(ms.width, ms.height)
    larg, alt = ms.width * k, ms.height * k

    with Tela(lato, lato) as t:
        tr = NSAffineTransform.transform()
        tr.translateXBy_yBy_(lato / 2.0, lato / 2.0)
        tr.rotateByDegrees_(gradi)
        tr.translateXBy_yBy_(-larg / 2.0, -alt / 2.0)
        tr.concat()
        im.drawInRect_fromRect_operation_fraction_(
            NSMakeRect(0, 0, larg, alt), NSZeroRect,
            NSCompositingOperationSourceOver, 1.0)
        tr.invert()
        tr.concat()
        colore(INCHIOSTRO).set()
        NSRectFillUsingOperation(NSMakeRect(0, 0, lato, lato),
                                 NSCompositingOperationSourceAtop)
        rep = t.rep
        fuori = t.immagine()

    # bbox dell'inchiostro, in righe della bitmap (riga 0 = in alto)
    bpr, dati = rep.bytesPerRow(), rep.bitmapData()
    x0, y0, x1, y1 = lato, lato, -1, -1
    for riga in range(lato):
        base = riga * bpr
        fetta = dati[base:base + lato * 4]
        for col in range(lato):
            if fetta[col * 4 + 3] > 8:
                if col < x0: x0 = col
                if col > x1: x1 = col
                if riga < y0: y0 = riga
                if riga > y1: y1 = riga
    # da righe (dall'alto) a y dal basso
    yb0, yb1 = lato - 1 - y1, lato - 1 - y0
    centro = ((x0 + x1 + 1) / 2.0, (yb0 + yb1 + 1) / 2.0)
    return fuori, centro, (x1 - x0 + 1), (yb1 - yb0 + 1), lato


# ---------------------------------------------------------------- l'icona vera --
def disegna_icona(lato=TELA, fondo=FONDO, altezza=ALTEZZA_MATITA, peso=PESO):
    s = lato / TELA
    corpo, margine = CORPO * s, MARGINE * s
    mat, (cx, cy), _im_l, im_a, lato_mat = matita_bianca(peso=peso)

    with Tela(lato, lato) as t:
        colore(fondo).setFill()
        piastrella(margine, margine, corpo, corpo).fill()

        k = (altezza * corpo) / im_a
        tr = NSAffineTransform.transform()
        tr.translateXBy_yBy_(lato / 2.0, lato / 2.0)
        tr.scaleBy_(k)
        tr.translateXBy_yBy_(-cx, -cy)
        tr.concat()
        mat.drawInRect_fromRect_operation_fraction_(
            NSMakeRect(0, 0, lato_mat, lato_mat), NSZeroRect,
            NSCompositingOperationSourceOver, 1.0)
        return t.rep


# ------------------------------------------- chiedere al sistema, non credergli --
PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" \
"http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>stub</string>
<key>CFBundleIdentifier</key><string>com.reda.anteprimamatitapiena</string>
<key>CFBundleName</key><string>AnteprimaMatitaPiena</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>CFBundleIconFile</key><string>AppIcon.icns</string>
<key>LSUIElement</key><true/></dict></plist>"""


def come_la_rende_macos(rep_arte):
    """Costruisce un .app usa-e-getta con dentro quest'arte e torna l'NSImage
    che il SISTEMA mostra. È l'unico modo onesto di fare un'anteprima: maschera,
    ombra e lucidatura non sono mie, e il piatto grigio si vede solo così.

    Nell'iconset ci va SOLO il 1024: dare anche i riquadri 16 e 32 fa comparire
    il piatto grigio proprio a 32 px (succede pure a Obsidian, app vera).
    """
    base = f"{CARTELLA}/_anteprima-bundle"
    app = f"{base}/AnteprimaMatitaPiena.app"
    iset = f"{base}/AppIcon.iconset"
    shutil.rmtree(base, ignore_errors=True)
    os.makedirs(f"{app}/Contents/MacOS")
    os.makedirs(f"{app}/Contents/Resources")
    os.makedirs(iset)
    salva_png(rep_arte, f"{iset}/icon_512x512@2x.png")
    r = subprocess.run(["iconutil", "--convert", "icns", iset, "-o",
                        f"{app}/Contents/Resources/AppIcon.icns"],
                       capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("iconutil: " + r.stderr)
    with open(f"{app}/Contents/Info.plist", "w") as f:
        f.write(PLIST)
    with open(f"{app}/Contents/MacOS/stub", "w") as f:
        f.write("#!/bin/sh\nexit 0\n")
    os.chmod(f"{app}/Contents/MacOS/stub", 0o755)
    subprocess.run(["touch", app])       # basta questo: `killall Dock` non serve
    time.sleep(1.0)
    return NSWorkspace.sharedWorkspace().iconForFile_(app), app


def rendi(im, lato):
    with Tela(lato, lato) as t:
        im.drawInRect_fromRect_operation_fraction_(
            NSMakeRect(0, 0, lato, lato), NSZeroRect,
            NSCompositingOperationSourceOver, 1.0)
        return t.rep


def controlla_piatto(rep):
    """Il piatto grigio è un vassoio 214,214,214 sotto l'arte rimpicciolita.
    Si legge DENTRO il corpo, non sul bordo: sul bordo c'è il riflesso che
    macOS mette anche alle icone buone (Calculator lì dà 246,246,245)."""
    L = rep.pixelsWide()
    bpr, d = rep.bytesPerRow(), rep.bitmapData()
    y = L // 2
    f = d[y * bpr: y * bpr + L * 4]
    c = next((x for x in range(L) if f[x * 4 + 3] > 200), None)
    if c is None:
        return None, None, "vuoto"
    dentro = min(c + max(4, L // 17), L - 1)
    px = tuple(f[dentro * 4: dentro * 4 + 3])
    grigio = (abs(px[0] - px[1]) < 14 and abs(px[1] - px[2]) < 14 and px[0] > 150)
    return L - 2 * c, px, ("🔴 PIATTO GRIGIO" if grigio else "ok, è la mia tinta")


# ---------------------------------------------------------------- il provino --
def scala(sorgente, misura):
    """Accetta un NSImage (quello che mostra il sistema) o un rep a 1024."""
    if isinstance(sorgente, NSBitmapImageRep):
        im = NSImage.alloc().initWithSize_(NSMakeSize(1024, 1024))
        im.addRepresentation_(sorgente)
    else:
        im = sorgente
    return rendi(im, misura)


def larghezza_testo(testo, punti):
    return NSAttributedString.alloc().initWithString_attributes_(testo, {
        NSFontAttributeName: NSFont.systemFontOfSize_(punti),
    }).size().width


def scrivi(testo, x, y, punti, col):
    a = NSAttributedString.alloc().initWithString_attributes_(testo, {
        NSFontAttributeName: NSFont.systemFontOfSize_(punti),
        NSForegroundColorAttributeName: col,
    })
    a.drawAtPoint_(NSMakePoint(x, y))
    return a.size().width


def provino(sorgente, percorso):
    """Le cinque misure vere, affiancate, su chiaro e su scuro — più lo zoom 8×
    dei due riquadri piccoli, che è il posto dove un'icona muore.

    La sorgente è quello che mostra il SISTEMA, non la mia arte: ombra,
    lucidatura e maschera sono sue, e un provino della sola arte mentirebbe."""
    misure = [512, 128, 64, 32, 16]
    immagini = {}
    for m in misure:
        im = NSImage.alloc().initWithSize_(NSMakeSize(m, m))
        im.addRepresentation_(scala(sorgente, m))
        immagini[m] = im

    note = (
        "Non è la mia arte: è quello che macOS 26 MOSTRA per un .app vero",
        "costruito con dentro quest'icona. Maschera, ombra e lucidatura",
        "sono sue — e anche il vetro: il bianco piatto che ho disegnato",
        "esce come un avorio in rilievo, e il contrasto reso è un terzo",
        "più basso di quello progettato (misurato, non stimato).",
        "",
        "L'arte è un rettangolo con gli angoli tondi al 22,46%. La sagoma",
        "VERA di macOS, disegnata da me, finisce 🔴 sul piatto grigio:",
        "verificato costruendo 15 bundle, uno per forma.",
    )
    passo, bordo = 56, 56
    larg_note = max(larghezza_testo(r, 21) for r in note)
    larg = int(max(bordo * 2 + sum(misure) + passo * (len(misure) - 1),
                   bordo + 32 * 8 + 16 * 8 + passo * 4 + larg_note + bordo))
    riga_h = 512 + 76           # icone + etichette
    zoom_h = 32 * 8 + 76
    alt = int(bordo * 2 + riga_h * 2 + zoom_h + 56)

    y_zoom = bordo
    y_scuro = y_zoom + zoom_h + 56
    y_chiaro = y_scuro + riga_h

    with Tela(larg, alt) as t:
        colore((0xEE, 0xEE, 0xF0)).setFill()
        NSRectFill(NSMakeRect(0, 0, larg, alt))
        colore((0x1E, 0x1E, 0x20)).setFill()
        NSRectFill(NSMakeRect(0, y_scuro, larg, riga_h))

        for base_y, col_txt in ((y_chiaro, colore((0x55, 0x55, 0x5A))),
                                (y_scuro, colore((0x9A, 0x9A, 0xA0)))):
            x = bordo
            for m in misure:
                immagini[m].drawInRect_fromRect_operation_fraction_(
                    NSMakeRect(x, base_y + 46, m, m), NSZeroRect,
                    NSCompositingOperationSourceOver, 1.0)
                scrivi(f"{m} px", x, base_y + 14, 22, col_txt)
                x += m + passo

        # zoom 8× di 32 e 16: qui si vede se il disegno sopravvive davvero
        x = bordo
        for m in (32, 16):
            z = m * 8
            NSGraphicsContext.currentContext().setImageInterpolation_(1)  # nessuna
            immagini[m].drawInRect_fromRect_operation_fraction_(
                NSMakeRect(x, y_zoom + 40, z, z), NSZeroRect,
                NSCompositingOperationSourceOver, 1.0)
            NSGraphicsContext.currentContext().setImageInterpolation_(
                NSImageInterpolationHigh)
            scrivi(f"{m} px · zoom 8×", x, y_zoom + 8, 22, colore((0x55, 0x55, 0x5A)))
            x += z + passo * 2
        g = colore((0x8A, 0x8A, 0x90))
        cima = y_zoom + 40 + 32 * 8 - 24
        for i, riga in enumerate(note):
            scrivi(riga, x, cima - i * 30, 21, g)
        salva_png(t.rep, percorso)
    return percorso


# ---------------------------------------------------------------- la tavola --
def tavola(percorso):
    candidati = [
        ("grafite calda  2F2A26", (0x2F, 0x2A, 0x26)),
        ("nero caldo     241F1B", (0x24, 0x1F, 0x1B)),
        ("blu notte      1C2B4A", (0x1C, 0x2B, 0x4A)),
        ("terracotta     93441F", (0x93, 0x44, 0x1F)),
        ("ambra          C07818", (0xC0, 0x78, 0x18)),
    ]
    scale = [0.55, 0.62, 0.68]
    pesi = [(NSFontWeightMedium, "Med"), (NSFontWeightSemibold, "Semi"),
            (NSFontWeightBold, "Bold")]

    cella, passo = 160, 24
    sx = 220
    larg = sx + len(scale) * len(pesi) * (cella + passo) + 40
    alt = 60 + len(candidati) * (cella + 90)

    with Tela(larg, alt) as t:
        colore((0xEC, 0xEC, 0xEE)).setFill()
        NSRectFill(NSMakeRect(0, 0, larg, alt))
        for i, (nome, rgb) in enumerate(candidati):
            y = alt - 60 - (i + 1) * (cella + 90) + 90
            scrivi(nome, 20, y + cella / 2 - 8, 20, colore((0x33, 0x33, 0x36)))
            x = sx
            for a in scale:
                for peso, pn in pesi:
                    rep = disegna_icona(512, rgb, a, peso)
                    im = NSImage.alloc().initWithSize_(NSMakeSize(512, 512))
                    im.addRepresentation_(rep)
                    im.drawInRect_fromRect_operation_fraction_(
                        NSMakeRect(x, y, cella, cella), NSZeroRect,
                        NSCompositingOperationSourceOver, 1.0)
                    im.drawInRect_fromRect_operation_fraction_(
                        NSMakeRect(x + cella / 2 - 16, y - 40, 32, 32), NSZeroRect,
                        NSCompositingOperationSourceOver, 1.0)
                    im.drawInRect_fromRect_operation_fraction_(
                        NSMakeRect(x + cella / 2 + 24, y - 32, 16, 16), NSZeroRect,
                        NSCompositingOperationSourceOver, 1.0)
                    if i == 0:
                        scrivi(f"{a:.2f} {pn}", x, alt - 40, 17,
                               colore((0x55, 0x55, 0x5A)))
                    x += cella + passo
        salva_png(t.rep, percorso)
    return percorso


# ------------------------------------------------------------------- lancio --
if __name__ == "__main__":
    if "--tavola" in sys.argv:
        p = tavola(f"{CARTELLA}/tavola-matita-piena.png")
        print("tavola:", p)
        raise SystemExit(0)

    # 1. l'ARTE: il file che andrebbe nell'iconset. Angoli tondi al 22,46%.
    rep = disegna_icona()
    arte = f"{CARTELLA}/arte-matita-piena.png"
    srgb = salva_png(rep, arte)
    print("arte (la sorgente per l'.icns):", arte)
    print("  pixel fondo (200,200) =", pixel(srgb, 200, 200), " chiesto", FONDO)
    print("  pixel centro (512,512) =", pixel(srgb, 512, 512), " atteso bianco")
    print("  pixel angolo (10,10)   =", pixel(srgb, 10, 10), " atteso alfa 0")

    # 2. l'ANTEPRIMA: quello che macOS mostra davvero. Glielo chiedo.
    im, app = come_la_rende_macos(rep)
    rep_sist = rendi(im, 1024)
    ante = f"{CARTELLA}/anteprima-matita-piena.png"
    salva_png(rep_sist, ante)
    print("anteprima (come la rende macOS):", ante)
    print("  bundle usa-e-getta:", app)
    for lato in (1024, 128, 64, 32, 16):
        corpo, px, esito = controlla_piatto(rendi(im, lato))
        print(f"  {lato:5d} px -> corpo {corpo} px, tinta dentro {px}  {esito}")

    # 3. il PROVINO, dalla resa vera del sistema
    p = provino(im, f"{CARTELLA}/provino-matita-piena.png")
    print("provino:", p)

    # 4. l'.icns che finisce nel pacchetto.
    #
    # 🔴 NIENTE 16 e 32 nell'iconset, ed è la scoperta che vale tutto il resto:
    # la decisione «è una piastrella o la appoggio su un piatto grigio?» macOS
    # la prende PER SINGOLA RAPPRESENTAZIONE, e uno squircle disegnato a 32 px
    # (corpo 26, raggio 5,8) dopo la rasterizzazione non legge più come tale.
    # Misurato: iconset completo 16→1024 = piatto grigio a 32 px; iconset senza
    # i piccoli = pulito a ogni misura, perché macOS scala dal grande.
    # Non è un difetto nostro: capita anche a Obsidian, che i piccoli li spedisce.
    iconset = Path(CARTELLA) / "Dettatura.iconset"
    if iconset.exists():
        shutil.rmtree(iconset)
    iconset.mkdir()
    for lato, nome in ((128, "icon_128x128.png"), (256, "icon_128x128@2x.png"),
                       (256, "icon_256x256.png"), (512, "icon_256x256@2x.png"),
                       (512, "icon_512x512.png"), (1024, "icon_512x512@2x.png")):
        salva_png(rendi(im, lato), str(iconset / nome))
    icns = Path(CARTELLA) / "Dettatura.icns"
    r = subprocess.run(["iconutil", "--convert", "icns", str(iconset),
                        "-o", str(icns)], capture_output=True, text=True)
    if r.returncode:
        print("🔴 iconutil ha fallito:", r.stderr.strip())
        raise SystemExit(1)
    shutil.rmtree(iconset)
    print(f"icona: {icns}  ({icns.stat().st_size // 1024} KB)")
