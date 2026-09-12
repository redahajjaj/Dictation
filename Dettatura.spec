# -*- mode: python ; coding: utf-8 -*-
# Bundle vero: identità propria, quindi macOS chiede i permessi a "Dettatura"
# e se li ricorda anche quando Homebrew aggiorna Python.
import os

# I file veri (vocabolario.txt, correzioni.txt) contengono i nomi di chi usa
# l'app e git li ignora: su un clone appena fatto non esistono ancora. Si
# imbarca quello che c'è — l'app semina il resto dagli esempi al primo avvio.
_config = [f for f in ("vocabolario.txt", "correzioni.txt",
                       "vocabolario.esempio.txt", "correzioni.esempio.txt")
           if os.path.exists(f)]

a = Analysis(
    ["dettatura.py"],
    pathex=[],
    binaries=[],
    datas=[(f, ".") for f in _config],
    # niente hiddenimports: la scorciatoia è Carbon via ctypes (scorciatoia.py),
    # pynput non c'è più
    hiddenimports=[],
    hookspath=[], hooksconfig={}, runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "PIL", "pytest"],
    noarchive=False, optimize=0,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Dettatura",
          debug=False, bootloader_ignore_signals=False, strip=False,
          upx=False, console=False, argv_emulation=False,
          target_arch=None, codesign_identity=None, entitlements_file=None)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="Dettatura")
app = BUNDLE(
    # l'icona la genera fai-icona.py; PyInstaller la copia in Resources e
    # scrive lui CFBundleIconFile — non va messo a mano nell'info_plist qui
    # sotto, o lo sovrascrive e l'icona sparisce
    coll, name="Dettatura.app", icon="Dettatura.icns",
    bundle_identifier="com.reda.dettatura",
    version="1.0",
    info_plist={
        # 🔴 Niente LSUIElement: Reda vuole l'icona nel Dock, per ritrovare
        # l'app e riaprirla dopo averla chiusa. Conseguenza: compare anche in
        # ⌘Tab, e il clic sull'icona nel Dock deve fare qualcosa — ci pensa
        # _clic_nel_dock() in dettatura.py, o sembrerebbe rotta.
        "NSMicrophoneUsageDescription": "Serve per registrare quello che detti e trascriverlo.",
        "NSAppleEventsUsageDescription": "Serve per copiare il testo negli appunti.",
        "CFBundleName": "Dettatura",
        "CFBundleDisplayName": "Dettatura",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
    },
)
