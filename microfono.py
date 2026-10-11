"""Il microfono vive in un processo a parte: l'app non tocca mai CoreAudio.

🔴 PERCHÉ UN PROCESSO (11/10). Il 12/9 la chiusura dello stream PortAudio si
era impiccata in un abbraccio mortale dentro CoreAudio (`sample`:
Pa_AbortStream → AudioDeviceStop ↔ startStopCallback, zero Python negli
stack). La cura di allora — chiudere in un thread usa-e-getta — salvava il
thread principale, ma NON il microfono: il thread audio di CoreAudio restava
appeso col lucchetto del dispositivo in mano, e ogni apertura successiva ci
finiva dietro. Diario del 22/9 e del 26/9: «nessuna risposta, lo do per
perso» tre volte di fila, poi «troppo corto» senza un solo «microfono
aperto», fino al riavvio del Mac. Dentro un processo un deadlock di
CoreAudio non si scioglie più: si può solo uccidere il processo.

Quindi il microfono ne ha uno suo, usa e getta: registra UNA dettatura, la
consegna, e muore con `os._exit` SENZA chiudere lo stream — la chiusura, cioè
il punto dove nasceva il deadlock, non avviene proprio (lo stream lo smonta
il sistema insieme al processo). Se si impicca lo stesso mentre apre, si
uccide e se ne prende un altro.

🔴 E IL MICROFONO GIUSTO. PortAudio legge l'elenco dei dispositivi UNA volta,
quando si carica. Un'app accesa da giorni registrava dal microfono che era
predefinito il giorno dell'avvio: chiuso il coperchio, arrivato l'iPhone o
cambiate le cuffie, ascoltava un dispositivo muto o sparito (diario del 14/9:
4 minuti e mezzo di parlato, «non ho sentito la voce»). Ogni figlio rilegge
l'elenco appena prima di aprire: usa il microfono predefinito di ADESSO.

Il padre (`Microfono`) tiene sempre un figlio già caldo — Python e PortAudio
caricati, fermo ad aspettare — così ⌘S non paga gli 0,3 s di avvio, e la
prima parola non si perde.

Questo file NON importa numpy né AppKit in cima: il figlio deve nascere
leggero, e non deve mai sfiorare il Dock.
"""
from __future__ import annotations

import json
import os
import queue
import struct
import subprocess
import sys
import threading
import time

FREQUENZA = 16_000  # Hz: quanto basta al parlato, e tiene i file piccoli

# I messaggi del figlio al padre: un byte di tipo + 4 di lunghezza + i dati.
PRONTO = b"P"    # Python e PortAudio caricati: aspetto «via»
APERTO = b"O"    # lo stream è partito (json: nome del microfono, secondi)
AUDIO = b"A"     # int16 mono a FREQUENZA
FINE = b"F"      # dopo «basta»: questo era l'ultimo audio
ERRORE = b"E"    # testo
ELENCO = b"L"    # json: i microfoni, per `--check`
MORTO = b"X"     # non arriva dal figlio: lo dice il lettore quando il tubo si chiude
_TESTA = struct.Struct("<cI")

APERTURA_MAX = 3.0     # «via» detto, stream non partito: si è impiccato aprendo
TENTATIVI_APERTURA = 2
SILENZIO_MAX = 2.0     # stream aperto ma niente audio da tanto: il microfono si è fermato
RIAPERTURE_MAX = 2     # quante volte, in una dettatura, si prova a riprenderlo
CODA_STOP = 0.15       # audio raccolto ancora dopo «basta»: è l'ultima parola
ATTESA_FINE = 1.5      # oltre, il figlio che sta consegnando si uccide e basta
PAUSA_MAX = 30.0       # se i figli caldi muoiono appena nati: al massimo uno ogni 30 s


def comando_figlio(script) -> list[str]:
    """Come si lancia il figlio: lo stesso programma, con «--microfono».

    Nel bundle `sys.executable` È l'app (PyInstaller); da sorgente è Python, e
    gli si passa lo script."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--microfono"]
    return [sys.executable, str(script), "--microfono"]


# =============================================================== il figlio
def figlio() -> None:
    """Il processo del microfono: aspetta «via», registra, consegna, sparisce.

    Non torna mai: finisce sempre con `os._exit`."""
    # Il canale col padre è il VERO stdout: lo si mette da parte, e al suo
    # posto va stderr. Così una print di troppo — nostra, di sounddevice, di
    # chiunque — finisce nel nulla invece di sporcare l'audio.
    canale = os.dup(1)
    os.dup2(2, 1)
    lucchetto = threading.Lock()

    def manda(tipo: bytes, dati: bytes = b"") -> None:
        vista = memoryview(_TESTA.pack(tipo, len(dati)) + dati)
        try:
            with lucchetto:
                while vista:
                    vista = vista[os.write(canale, vista):]
        except OSError:          # il padre non c'è più: niente a cui consegnare
            os._exit(0)

    ordini: queue.SimpleQueue = queue.SimpleQueue()

    def ascolta() -> None:
        try:
            for riga in sys.stdin.buffer:
                ordini.put(riga.strip())
        except (OSError, ValueError):
            pass
        ordini.put(b"addio")     # stdin chiuso: il padre è morto o ci congeda

    threading.Thread(target=ascolta, daemon=True).start()

    try:
        import sounddevice as sd
    except Exception as e:       # niente PortAudio: non c'è niente da fare qui
        manda(ERRORE, f"PortAudio non si carica ({e})".encode())
        os._exit(2)
    manda(PRONTO)

    # Da caldo il figlio può solo elencare i microfoni (non si consuma: serve al
    # menu) o partire. Qualsiasi altra parola, o stdin chiuso, è un congedo.
    while True:
        ordine = ordini.get()
        if ordine == b"elenca":
            try:
                manda(ELENCO, json.dumps(_microfoni(sd)).encode())
            except Exception as e:
                manda(ERRORE, f"nessun microfono ({e})".encode())
            continue
        if ordine == b"via" or ordine.startswith(b"via "):
            break
        os._exit(0)
    opzioni = json.loads(ordine[4:] or b"{}") if ordine != b"via" else {}
    richiesto = opzioni.get("microfono") or ""

    t0 = time.monotonic()
    try:
        elenco = _microfoni(sd)
    except Exception as e:
        manda(ERRORE, f"nessun microfono ({e})".encode())
        os._exit(3)
    # quello scelto dal menu, se è collegato; se no il predefinito di sistema
    # — dire «non c'è» e non registrare niente sarebbe peggio
    dispositivo, nome = None, elenco["predefinito"]
    if richiesto and richiesto in elenco["indici"]:
        dispositivo, nome = elenco["indici"][richiesto], richiesto
    if not nome:
        manda(ERRORE, b"nessun microfono collegato")
        os._exit(3)

    blocchi: queue.SimpleQueue = queue.SimpleQueue()

    def arriva(dati, _frame, _tempo, _stato) -> None:
        # sul thread audio di CoreAudio: copia e via, il resto lo fa il ciclo
        blocchi.put(bytes(dati))

    try:
        stream = sd.RawInputStream(samplerate=FREQUENZA, channels=1, dtype="int16",
                                   device=dispositivo, callback=arriva)
        stream.start()
    except Exception as e:
        manda(ERRORE, f"il microfono «{nome}» non si apre ({e})".encode())
        os._exit(4)
    manda(APERTO, json.dumps({
        "nome": nome,
        "richiesto": richiesto,
        "ripiego": bool(richiesto) and nome != richiesto,
        "secondi": round(time.monotonic() - t0, 3),
    }).encode())

    scadenza = None              # dopo «basta»: fino a quando raccogliere ancora
    while scadenza is None or time.monotonic() < scadenza:
        try:
            manda(AUDIO, blocchi.get(timeout=0.03))
        except queue.Empty:
            pass
        if scadenza is None:
            try:
                ordine = ordini.get_nowait()
            except queue.Empty:
                continue
            if ordine == b"elenca":  # arrivato tardi: a registrazione partita non conta
                continue
            if ordine != b"basta":   # «addio»: il padre non vuole più niente
                os._exit(0)
            scadenza = time.monotonic() + CODA_STOP
    while True:
        try:
            manda(AUDIO, blocchi.get_nowait())
        except queue.Empty:
            break
    manda(FINE)
    # 🔴 NIENTE stream.close(): è lì che PortAudio si impiccava. Il processo
    # finisce e il sistema smonta lo stream con lui.
    os._exit(0)


def _microfoni(sd) -> dict:
    """I microfoni di ADESSO: PortAudio rilegge l'elenco da capo.

    È tutto il motivo per cui il figlio esiste (vedi in cima): l'elenco che
    PortAudio si fa caricandosi invecchia, e nessuno glielo rinfresca."""
    sd._terminate()
    sd._initialize()
    indici = {}
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] > 0:
            indici.setdefault(d["name"], i)      # due omonimi: vince il primo
    try:
        predefinito = sd.query_devices(kind="input")["name"]
    except Exception:                            # nessun predefinito di sistema
        predefinito = next(iter(indici), "")
    return {"predefinito": predefinito, "tutti": list(indici), "indici": indici}


# ================================================================= il padre
class _Figlio:
    """Un processo del microfono, e il filo che ne legge i messaggi."""

    def __init__(self, comando, consegna):
        self.pronto = False      # ha caricato PortAudio
        self.morto = False       # il tubo si è chiuso
        self.proc = subprocess.Popen(comando, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE)
        self._consegna = consegna
        threading.Thread(target=self._leggi, daemon=True, name="mic-lettore").start()

    def _leggi(self) -> None:
        f = self.proc.stdout
        try:
            while True:
                testa = f.read(_TESTA.size)
                if len(testa) < _TESTA.size:
                    break
                tipo, n = _TESTA.unpack(testa)
                dati = f.read(n) if n else b""
                if len(dati) < n:
                    break
                self._consegna(self, tipo, dati)
        except (OSError, ValueError):
            pass
        self.morto = True
        try:                     # niente zombie: il processo si raccoglie qui
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.uccidi()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        for tubo in (self.proc.stdout, self.proc.stdin):
            try:
                tubo.close()
            except (OSError, ValueError):
                pass
        self._consegna(self, MORTO, b"")

    def ordina(self, parola: bytes) -> bool:
        if self.morto:
            return False
        try:
            self.proc.stdin.write(parola + b"\n")
            self.proc.stdin.flush()
            return True
        except (OSError, ValueError):
            return False

    def uccidi(self) -> None:
        try:
            self.proc.kill()
        except OSError:
            pass


class _Presa:
    """Una dettatura dal punto di vista del microfono."""

    def __init__(self, su_audio, aperto, fallito, finito):
        self.su_audio = su_audio
        self.aperto_cb = aperto
        self.fallito_cb = fallito
        self.finito_cb = finito
        self.figlio: _Figlio | None = None
        self.t_via = 0.0         # quando il figlio di adesso ha avuto «via»
        self.aperto = False      # il figlio di adesso ha aperto lo stream
        self.mai_aperto = True   # nessun figlio, in questa dettatura, ha mai aperto
        self.nome = ""
        self.ultimo_audio = 0.0
        self.fermando = False
        self.t_stop = 0.0
        self.tentativi = 0       # aperture fallite di fila
        self.riaperture = 0      # microfoni ripresi a dettatura in corso
        self.ultimo_errore = ""  # quello che ha detto il figlio prima di morire
        self.chiusa = False      # finito o fallito già detto: da qui non parla più


class Microfono:
    """Il lato dell'app: accende, spegne, e tiene d'occhio il figlio.

    Le richiamate (`su_audio`, `aperto`, `fallito`, `finito`) arrivano da
    thread di servizio, MAI dal thread principale: devono essere brevi e non
    devono richiamare il Microfono. `finito` o `fallito`, uno dei due, arriva
    SEMPRE, una volta sola — tranne dopo `annulla()`, che è un congedo muto.
    """

    def __init__(self, comando: list[str], diario=print, dispositivo: str = "",
                 caldo: bool = True):
        self._comando = comando
        self._diario = diario
        # il microfono scelto dal menu; vuoto = il predefinito di sistema,
        # quello di ADESSO (lo rilegge ogni figlio)
        self.dispositivo = dispositivo
        # gli ultimi microfoni visti da un figlio: il menu li mostra senza
        # aspettare. Il predefinito vuoto vuol dire «non lo so ancora».
        self.microfoni = {"predefinito": "", "tutti": []}
        self._elenco_nuovo = threading.Event()
        self._lucchetto = threading.RLock()
        self._caldo: _Figlio | None = None
        self._presa: _Presa | None = None
        self._ultimo_parto = 0.0
        # quanti figli caldi di fila sono morti senza servire a niente: se
        # succede (bundle rotto, PortAudio che non si carica) si rallenta, o la
        # guardia ne farebbe nascere dieci al secondo
        self._morti_inutili = 0
        # senza figlio caldo (`--check`): chi elenca e basta non deve lasciare
        # un processo acceso dietro di sé
        self._spento = not caldo
        self._guasto = ""        # perché i figli non nascono, se non nascono
        threading.Thread(target=self._guardia, daemon=True, name="mic-guardia").start()

    # -- per l'app ----------------------------------------------------------
    def cambia(self, dispositivo: str) -> None:
        """Il microfono scelto dal menu («» = automatico). Vale dalla prossima
        dettatura — o da subito, se ce n'è una in corso: il figlio di adesso si
        congeda e il prossimo apre quello nuovo, senza fermare il cronometro."""
        with self._lucchetto:
            if dispositivo == self.dispositivo:
                return
            self.dispositivo = dispositivo
            p = self._presa
            if p is not None and not p.chiusa and not p.fermando and p.figlio is not None:
                self._diario(f"microfono cambiato a dettatura in corso: "
                             f"{dispositivo or 'automatico'}")
                p.figlio.uccidi()
                self._dai_figlio(p)

    def aggiorna_elenco(self, attesa: float = 0.3) -> dict:
        """Chiede al figlio caldo i microfoni di adesso e aspetta un attimo la
        risposta (il menu si sta aprendo: non può aspettare di più). Se non
        arriva, si mostra l'ultimo elenco noto — che il figlio aggiorna
        comunque da solo ogni volta che nasce."""
        with self._lucchetto:
            f = self._caldo
            self._elenco_nuovo.clear()
            chiesto = f is not None and f.pronto and f.ordina(b"elenca")
        if chiesto:
            self._elenco_nuovo.wait(attesa)
        return self.microfoni

    def accendi(self, su_audio, aperto, fallito, finito) -> None:
        with self._lucchetto:
            if self._presa is not None:
                # una dettatura vecchia ancora in consegna: si chiude adesso,
                # con quello che ha dato
                self._chiudi(self._presa, fallita=None)
            p = _Presa(su_audio, aperto, fallito, finito)
            self._presa = p
            self._dai_figlio(p)

    def spegni(self) -> None:
        """Basta così: l'ultima parola arriva fra un attimo, poi `finito`."""
        with self._lucchetto:
            p = self._presa
            if p is None or p.fermando or p.chiusa:
                return
            p.fermando = True
            p.t_stop = time.monotonic()
            if p.figlio is None or not p.figlio.ordina(b"basta"):
                self._chiudi(p, fallita=None)

    def annulla(self) -> None:
        """La dettatura non serve più: il figlio muore e nessuno viene avvisato."""
        with self._lucchetto:
            p = self._presa
            if p is None:
                return
            p.chiusa = True
            self._presa = None
            if p.figlio is not None:
                p.figlio.uccidi()

    def chiudi_tutto(self) -> None:
        """All'uscita dell'app: nessun figlio deve sopravviverle col microfono in mano."""
        with self._lucchetto:
            self._spento = True
            for f in (self._caldo, self._presa.figlio if self._presa else None):
                if f is not None:
                    f.uccidi()

    def elenca(self, attesa: float = 6.0) -> dict:
        """I microfoni come li vede un figlio appena nato (per `--check`).
        Non apre niente: nessun pallino arancione, nessun permesso chiesto."""
        risposta: queue.SimpleQueue = queue.SimpleQueue()

        def consegna(_f, tipo, dati):
            if tipo in (ELENCO, ERRORE, MORTO):
                risposta.put((tipo, dati))

        f = _Figlio(self._comando, consegna)
        f.ordina(b"elenca")
        try:
            tipo, dati = risposta.get(timeout=attesa)
        except queue.Empty:
            f.uccidi()
            raise RuntimeError(f"il processo del microfono non risponde in {attesa:.0f}s")
        f.uccidi()
        if tipo == ELENCO:
            return json.loads(dati)
        raise RuntimeError(dati.decode("utf-8", "replace") or "il processo del microfono è morto")

    # -- interno: sempre sotto il lucchetto -----------------------------------
    def _nuovo_figlio(self) -> _Figlio | None:
        self._ultimo_parto = time.monotonic()
        try:
            f = _Figlio(self._comando, self._consegna)
        except OSError as e:
            if not self._guasto:
                self._diario(f"microfono: il processo non parte ({e})")
            self._guasto = str(e)
            self._morti_inutili += 1
            return None
        self._guasto = ""
        return f

    def _dai_figlio(self, p: _Presa) -> None:
        """Un figlio alla presa, e «via». Il caldo se c'è, se no uno nuovo."""
        f, self._caldo = self._caldo, None
        if f is None or f.morto:
            f = self._nuovo_figlio()
        p.figlio = f
        p.aperto = False
        p.t_via = time.monotonic()
        if f is not None:
            # json con ensure_ascii: il nome del microfono («Mario Rossi’s
            # iPhone») viaggia in puro ASCII, su una riga sola
            f.ordina(b"via " + json.dumps({"microfono": self.dispositivo}).encode())
        # se f è None (o «via» non è passato) ci pensa la guardia al prossimo giro

    def _chiudi(self, p: _Presa, fallita: str | None) -> None:
        """Fine della presa: con `fallita` è un fallimento, se no è finita."""
        if p.chiusa:
            return
        p.chiusa = True
        if self._presa is p:
            self._presa = None
        if p.figlio is not None and not p.figlio.morto:
            p.figlio.uccidi()        # dopo FINE è già uscito da solo: non fa niente
        if fallita is None:
            p.finito_cb()
        else:
            p.fallito_cb(fallita, not p.mai_aperto)

    def _consegna(self, f: _Figlio, tipo: bytes, dati: bytes) -> None:
        """Dal filo lettore di un figlio, qualunque esso sia."""
        if tipo == AUDIO:
            # la strada calda (~100 volte al secondo): il lucchetto solo per
            # sapere di chi è, la richiamata fuori
            with self._lucchetto:
                p = self._presa
                if p is None or p.chiusa or p.figlio is not f:
                    return       # un figlio vecchio, già congedato: si butta
                p.ultimo_audio = time.monotonic()
                su_audio = p.su_audio
            su_audio(dati)
            return
        with self._lucchetto:
            if tipo == PRONTO:
                f.pronto = True
                self._morti_inutili = 0
                if f is self._caldo:
                    f.ordina(b"elenca")  # costa 3 ms: il menu avrà l'elenco fresco
                return
            if tipo == ELENCO:
                elenco = json.loads(dati)
                self.microfoni = {"predefinito": elenco.get("predefinito", ""),
                                  "tutti": elenco.get("tutti", [])}
                self._elenco_nuovo.set()
                return
            p = self._presa
            mio = p is not None and not p.chiusa and p.figlio is f
            if tipo == MORTO:
                if f is self._caldo:
                    self._caldo = None
                    self._morti_inutili += 1
                if mio and p.fermando:
                    self._chiudi(p, fallita=None)
                # a dettatura in corso ci pensa la guardia: riapre
                return
            if not mio:
                if tipo == ERRORE:
                    self._diario(f"microfono: {dati.decode('utf-8', 'replace')}")
                return
            if tipo == APERTO:
                info = json.loads(dati)
                di_nuovo = not p.mai_aperto
                p.aperto = True
                p.mai_aperto = False
                p.tentativi = 0
                p.nome = info.get("nome", "")
                p.ultimo_audio = time.monotonic()
                if info.get("ripiego"):
                    self._diario(f"microfono: «{info.get('richiesto')}» non è collegato, "
                                 f"uso «{p.nome}»")
                self._diario(f"microfono {'ripreso' if di_nuovo else 'aperto'} in "
                             f"{info.get('secondi', 0):.2f}s ({p.nome})")
                p.aperto_cb(p.nome, di_nuovo)
            elif tipo == FINE:
                self._chiudi(p, fallita=None)
            elif tipo == ERRORE:
                testo = dati.decode("utf-8", "replace")
                self._diario(f"microfono: {testo}")
                p.ultimo_errore = testo
                f.uccidi()           # la guardia vede il morto e decide

    # -- la guardia -----------------------------------------------------------
    def _guardia(self) -> None:
        while True:
            time.sleep(0.1)
            try:
                with self._lucchetto:
                    if self._spento:
                        return
                    self._sorveglia(time.monotonic())
            except Exception as e:   # la guardia non deve morire mai
                self._diario(f"microfono, guardia: {type(e).__name__}: {e}")

    def _sorveglia(self, ora: float) -> None:
        p = self._presa
        if p is not None and not p.chiusa:
            f = p.figlio
            if p.fermando:
                if ora - p.t_stop > ATTESA_FINE:
                    self._diario(f"microfono: consegna non finita in {ATTESA_FINE:.1f}s, "
                                 "lo chiudo con quello che c'è")
                    self._chiudi(p, fallita=None)
            elif f is None or f.morto or (not p.aperto and ora - p.t_via > APERTURA_MAX):
                motivo = p.ultimo_errore or (
                    "il processo non parte" if f is None else
                    "non risponde" if not f.morto else "il processo è caduto")
                p.ultimo_errore = ""
                if f is not None:
                    f.uccidi()
                if p.aperto:
                    self._riprendi(p, f"«{p.nome}» {motivo}")
                else:
                    p.tentativi += 1
                    if p.tentativi < TENTATIVI_APERTURA:
                        self._diario(f"microfono: {motivo} aprendo, riprovo con un processo nuovo")
                        self._dai_figlio(p)
                    else:
                        self._diario(f"microfono: {motivo}, mi arrendo")
                        self._chiudi(p, fallita=motivo)
            elif p.aperto and ora - p.ultimo_audio > SILENZIO_MAX:
                # aperto, ma l'audio ha smesso di arrivare: il dispositivo è
                # sparito (cuffie spente, iPhone andato via) o CoreAudio si è
                # fermato. Il figlio si butta e se ne prende un altro, che
                # sceglierà il microfono predefinito di adesso.
                f.uccidi()
                self._riprendi(p, f"«{p.nome}» muto da {ora - p.ultimo_audio:.1f}s")

        if self._caldo is not None and self._caldo.morto:
            self._caldo = None
        # Il caldo appena preso da una dettatura si rimpiazza SUBITO: la
        # prossima ⌘S può arrivare fra un secondo, e un figlio che nasce in
        # quel momento costa 0,3 s di avvio — le prime parole. Si aspetta solo
        # se i caldi continuano a morire da soli: 1, 2, 4… fino a 30 s.
        pausa = 0.0 if not self._morti_inutili else min(PAUSA_MAX, 2.0 ** self._morti_inutili)
        if (self._caldo is None and not self._spento
                and ora - self._ultimo_parto >= pausa):
            self._caldo = self._nuovo_figlio()

    def _riprendi(self, p: _Presa, perche: str) -> None:
        if p.riaperture >= RIAPERTURE_MAX:
            self._diario(f"microfono: {perche}, già ripreso {p.riaperture} volte: mi arrendo")
            self._chiudi(p, fallita=f"{perche}")
            return
        p.riaperture += 1
        self._diario(f"microfono: {perche}, lo riprendo")
        self._dai_figlio(p)
