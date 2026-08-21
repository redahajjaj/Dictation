# -*- mode: python ; coding: utf-8 -*-
# Bundle vero: identità propria, quindi macOS chiede i permessi a "Dettatura"
# e se li ricorda anche quando Homebrew aggiorna Python.
a = Analysis(
    ["dettatura.py"],
    pathex=[],
    binaries=[],
    datas=[("vocabolario.txt", "."), ("correzioni.txt", ".")],
    hiddenimports=["pynput.keyboard._darwin", "pynput.mouse._darwin"],
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
    coll, name="Dettatura.app", icon=None, bundle_identifier="com.reda.dettatura",
    version="1.0",
    info_plist={
        "LSUIElement": True,                      # solo barra dei menu, niente Dock
        "NSMicrophoneUsageDescription": "Serve per registrare quello che detti e trascriverlo.",
        "NSAppleEventsUsageDescription": "Serve per copiare il testo negli appunti.",
        "CFBundleName": "Dettatura",
        "CFBundleDisplayName": "Dettatura",
        "LSMinimumSystemVersion": "12.0",
        "NSHighResolutionCapable": True,
    },
)
