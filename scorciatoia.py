"""La scorciatoia globale, alla maniera di macOS: Carbon `RegisterEventHotKey`.

🔴 Perché non più pynput (12/9). pynput ascolta i tasti con un *event tap* in
sola lettura, e da macOS Catalina in poi quel tap vuole il permesso
«Monitoraggio input» (kTCCServiceListenEvent) — un permesso DIVERSO
dall'Accessibilità. Se manca, il tap nasce lo stesso: `is_alive()` dice sì,
`AXIsProcessTrusted` dice sì, e i tasti non arrivano MAI. Lo dice tccd, non io
(12/9 09:53:16: `service=kTCCServiceListenEvent … authValue=0`). Tre sessioni
hanno inseguito l'Accessibilità per niente. In più pynput 1.8 scarta ogni
evento «iniettato», quindi da un terminale non si poteva nemmeno provare.

`RegisterEventHotKey` non chiede NESSUN permesso, non ha thread, e macOS
consegna l'evento direttamente al run loop dell'app — quello che rumps già fa
girare. Consuma anche il tasto: l'app davanti non riceve più un ⌘S da «Salva».
Provato il 12/9 su macOS 26.6: registra (noErr) e scatta su un ⌘S sintetico.

La sintassi della scorciatoia nel .env resta quella di prima («<cmd>+s»), così
per Reda non cambia niente.
"""
from __future__ import annotations

import ctypes
import sys

_carbon = ctypes.CDLL("/System/Library/Frameworks/Carbon.framework/Carbon")


def _fourcc(s: str) -> int:
    return (ord(s[0]) << 24) | (ord(s[1]) << 16) | (ord(s[2]) << 8) | ord(s[3])


class _EventTypeSpec(ctypes.Structure):
    _fields_ = [("eventClass", ctypes.c_uint32), ("eventKind", ctypes.c_uint32)]


class _EventHotKeyID(ctypes.Structure):
    _fields_ = [("signature", ctypes.c_uint32), ("id", ctypes.c_uint32)]


_GESTORE = ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)

_carbon.GetApplicationEventTarget.restype = ctypes.c_void_p
_carbon.InstallEventHandler.argtypes = [
    ctypes.c_void_p, _GESTORE, ctypes.c_size_t, ctypes.POINTER(_EventTypeSpec),
    ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
]
_carbon.InstallEventHandler.restype = ctypes.c_int32
_carbon.RegisterEventHotKey.argtypes = [
    ctypes.c_uint32, ctypes.c_uint32, _EventHotKeyID, ctypes.c_void_p,
    ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p),
]
_carbon.RegisterEventHotKey.restype = ctypes.c_int32
_carbon.UnregisterEventHotKey.argtypes = [ctypes.c_void_p]
_carbon.UnregisterEventHotKey.restype = ctypes.c_int32
_carbon.GetEventParameter.argtypes = [
    ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
    ctypes.c_size_t, ctypes.c_void_p, ctypes.c_void_p,
]
_carbon.GetEventParameter.restype = ctypes.c_int32

_CLASSE_TASTIERA = _fourcc("keyb")
_TASTO_PREMUTO = 5                    # kEventHotKeyPressed
_PARAMETRO = _fourcc("----")          # kEventParamDirectObject
_TIPO_ID = _fourcc("hkid")            # typeEventHotKeyID
_FIRMA = _fourcc("DETT")

# I bit dei modificatori come li vuole Carbon (non sono quelli di NSEvent).
_MODIFICATORI = {
    "<cmd>": 0x0100, "<cmd_l>": 0x0100, "<cmd_r>": 0x0100,
    "<shift>": 0x0200, "<shift_l>": 0x0200, "<shift_r>": 0x0200,
    "<alt>": 0x0800, "<alt_l>": 0x0800, "<alt_r>": 0x0800, "<alt_gr>": 0x0800,
    "<ctrl>": 0x1000, "<ctrl_l>": 0x1000, "<ctrl_r>": 0x1000,
}

# Codici virtuali dei tasti: indicano la POSIZIONE fisica sulla tastiera
# (disposizione ANSI/QWERTY), non la lettera stampata. Sulla tastiera italiana
# le lettere e i numeri stanno negli stessi posti, quindi «s» è sempre 1.
_TASTI = {
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8, "v": 9,
    "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17,
    "1": 18, "2": 19, "3": 20, "4": 21, "6": 22, "5": 23, "9": 25, "7": 26, "8": 28, "0": 29,
    "o": 31, "u": 32, "i": 34, "p": 35, "l": 37, "j": 38, "k": 40, "n": 45, "m": 46,
    "<space>": 49, "<enter>": 36, "<tab>": 48, "<esc>": 53,
    "<backspace>": 51, "<delete>": 117,
    "<left>": 123, "<right>": 124, "<down>": 125, "<up>": 126,
    "<f1>": 122, "<f2>": 120, "<f3>": 99, "<f4>": 118, "<f5>": 96, "<f6>": 97,
    "<f7>": 98, "<f8>": 100, "<f9>": 101, "<f10>": 109, "<f11>": 103, "<f12>": 111,
}


def analizza(spec: str) -> tuple[int, int]:
    """Da «<cmd>+<shift>+d» a (codice del tasto, bit dei modificatori).

    Solleva ValueError con una frase leggibile se la scorciatoia non si può
    registrare: è quella che finisce nella barra e in `--check`.
    """
    pezzi = [p.strip().lower() for p in spec.split("+") if p.strip()]
    modificatori = 0
    tasti = []
    for p in pezzi:
        if p in _MODIFICATORI:
            modificatori |= _MODIFICATORI[p]
        else:
            tasti.append(p)
    if len(tasti) != 1:
        raise ValueError(f"«{spec}»: serve esattamente un tasto oltre ai modificatori")
    if tasti[0] not in _TASTI:
        raise ValueError(f"«{spec}»: il tasto «{tasti[0]}» non lo conosco (lettere, cifre, <space>, <f1>…)")
    if not modificatori:
        raise ValueError(f"«{spec}»: senza ⌘ ⌥ ⌃ o ⇧ ruberebbe il tasto a tutte le app")
    return _TASTI[tasti[0]], modificatori


class Scorciatoie:
    """Le scorciatoie globali dell'app. Una sola istanza per processo.

    L'azione gira sul thread principale, dentro il run loop di NSApplication:
    deve essere breve (metti in coda e torna). Se il thread principale è
    piantato non scatta nulla — per quello c'è `./ferma.sh`.
    """

    def __init__(self):
        self._azioni: dict[int, object] = {}
        self._riferimenti: dict[int, ctypes.c_void_p] = {}
        self._prossimo = 1
        # il callback va tenuto vivo da noi: ctypes non lo trattiene, e se il
        # garbage collector lo porta via macOS chiama memoria libera
        self._gestore = _GESTORE(self._scattata)
        self._bersaglio = _carbon.GetApplicationEventTarget()
        spec = _EventTypeSpec(_CLASSE_TASTIERA, _TASTO_PREMUTO)
        ref = ctypes.c_void_p()
        err = _carbon.InstallEventHandler(
            self._bersaglio, self._gestore, 1, ctypes.byref(spec), None, ctypes.byref(ref)
        )
        if err != 0:
            raise OSError(f"InstallEventHandler ha risposto {err}")

    def _scattata(self, _prossimo, evento, _dati) -> int:
        hk = _EventHotKeyID()
        err = _carbon.GetEventParameter(
            evento, _PARAMETRO, _TIPO_ID, None, ctypes.sizeof(hk), None, ctypes.byref(hk)
        )
        azione = self._azioni.get(hk.id) if err == 0 and hk.signature == _FIRMA else None
        if azione is not None:
            try:
                azione()
            except Exception as e:      # un'eccezione qui dentro ucciderebbe il run loop
                print(f"scorciatoia: l'azione ha fallito: {e}", file=sys.stderr)
        return 0                        # noErr: l'evento è nostro, non va oltre

    def registra(self, spec: str, azione) -> str | None:
        """Registra una combinazione. Torna None se è andata, altrimenti il perché."""
        try:
            tasto, modificatori = analizza(spec)
        except ValueError as e:
            return str(e)
        numero = self._prossimo
        ref = ctypes.c_void_p()
        err = _carbon.RegisterEventHotKey(
            tasto, modificatori, _EventHotKeyID(_FIRMA, numero), self._bersaglio, 0, ctypes.byref(ref)
        )
        if err != 0:
            # -9878 = eventHotKeyExistsErr: l'abbiamo già registrata NOI (in un
            # altro processo la stessa combinazione si registra senza errore)
            return f"«{spec}» non si registra (macOS risponde {err})"
        self._prossimo += 1
        self._azioni[numero] = azione
        self._riferimenti[numero] = ref
        return None

    def togli_tutte(self) -> None:
        for ref in self._riferimenti.values():
            _carbon.UnregisterEventHotKey(ref)
        self._riferimenti.clear()
        self._azioni.clear()
