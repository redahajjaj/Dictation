#!/usr/bin/env python3
"""Banco di prova della logica: niente microfono, niente rete, niente barra.

    .venv/bin/python prova-logica.py

Prova le regole che decidono se una dettatura arriva negli appunti o si perde:
i tentativi verso Groq, la dettatura messa da parte quando la rete non c'è, la
pulitura a pezzi che lascia il grezzo invece di buttare tutto, cosa si fa a
fine registrazione. Groq è finto: le risposte le decide la prova.
"""
import os
import sys
import tempfile
from pathlib import Path

import numpy as np
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))

import dettatura as D  # noqa: E402

# niente file veri: diario, storico, .env e dettature da parte in una cartella usa e getta
CARTELLA = Path(tempfile.mkdtemp(prefix="prova-logica-"))
D.LOG = CARTELLA / "dettatura.log"
D.STORICO = CARTELLA / "storico.md"
D.DA_RIPROVARE = CARTELLA / "da-trascrivere"
D.ENV = CARTELLA / ".env"
D.PAUSE = (0.01, 0.01, 0.01)          # i tentativi senza aspettare davvero
APPUNTI = []
D.negli_appunti = APPUNTI.append      # gli appunti veri di Reda non si toccano

esiti = []


def controlla(nome, ok, dettaglio=""):
    esiti.append(bool(ok))
    print(f"  {'ok  ' if ok else 'NO  '} {nome}   {dettaglio}")


# ------------------------------------------------------------ Groq finto
class Risposta:
    def __init__(self, codice=200, testo="", json=None, intestazioni=None):
        self.status_code = codice
        self.text = testo
        self._json = json
        self.headers = intestazioni or {}

    def json(self):
        return self._json


class SessioneFinta:
    """Risponde con quello che c'è in coda, una risposta (o eccezione) a POST."""

    def __init__(self, risposte):
        self.risposte = list(risposte)
        self.chiamate = []
        self.headers = {}

    def post(self, url, **kw):
        self.chiamate.append((url, kw))
        r = self.risposte.pop(0)
        if isinstance(r, Exception):
            raise r
        return r

    def get(self, *a, **kw):
        raise requests.ConnectionError("niente rete nelle prove")


def groq_finto(risposte, llm="openai/gpt-oss-120b"):
    g = D.Groq("gsk_finta", llm)
    g.s = SessioneFinta(risposte)
    return g


def chat(testo):
    return Risposta(json={"choices": [{"message": {"content": testo}}]})


DNS = requests.ConnectionError("NameResolutionError: Failed to resolve 'api.groq.com'")


print("\n— le allucinazioni di Whisper —")
controlla("«comunità Amara.org» (con l'accento) si riconosce",
          D.solo_allucinazione("Sottotitoli creati dalla comunità Amara.org"))
controlla("«Grazie.» da solo è un'allucinazione", D.solo_allucinazione(" Grazie."))
controlla("una frase vera con «grazie» resta",
          not D.solo_allucinazione("Grazie a tutti per il lavoro su Acmelux"))

print("\n— il prompt di Whisper sta nel limite di Groq —")
voci = [f"Nomeproprio{i} Cognomelungo{i}" for i in range(200)]
s = D.suggerimento_whisper(voci)
controlla("200 voci lunghe: il prompt resta sotto 896", len(s) <= 896, f"{len(s)} caratteri")
controlla("e non tronca una voce a metà", s.endswith(voci[s.count(",")]), s[-30:])
corto = D.suggerimento_whisper(["Acmelux", "Nordvento"])
controlla("poche voci: ci sono tutte", corto.endswith("Acmelux, Nordvento"), corto)

print("\n— la pulitura a pezzi —")
frase = "Questa è una frase di prova che serve a riempire il testo. "
lungo = frase * 300                                   # ~18.000 caratteri
pezzi = D.spezza(lungo.strip(), D.PEZZO_PULITURA)
controlla("i pezzi stanno nel limite", all(len(p) <= D.PEZZO_PULITURA for p in pezzi),
          f"{len(pezzi)} pezzi, il più lungo {max(map(len, pezzi))}")
controlla("niente si perde tagliando",
          " ".join(pezzi).split() == lungo.split())
controlla("un testo corto resta intero", D.spezza("ciao", 100) == ["ciao"])
senza_punti = "parola " * 3000
controlla("anche senza punteggiatura si taglia fra le parole",
          all(len(p) <= D.PEZZO_PULITURA and not p.startswith(" ")
              for p in D.spezza(senza_punti.strip(), D.PEZZO_PULITURA)))

print("\n— i tentativi verso Groq —")
g = groq_finto([DNS, DNS, Risposta(200, " testo trascritto ")])
controlla("DNS che non risponde due volte, poi risponde: si trascrive",
          g.trascrivi(b"audio", "prompt") == "testo trascritto", f"{len(g.s.chiamate)} chiamate")
g = groq_finto([DNS] * 4)
try:
    g.trascrivi(b"audio", "prompt")
    controlla("rete morta: si arrende con GroqIrraggiungibile", False)
except D.GroqIrraggiungibile:
    controlla("rete morta: si arrende con GroqIrraggiungibile", len(g.s.chiamate) == 4,
              f"{len(g.s.chiamate)} tentativi")
g = groq_finto([Risposta(401, "invalid api key")])
try:
    g.trascrivi(b"audio", "prompt")
    controlla("chiave rifiutata: niente tentativi inutili", False)
except D.ErroreGroq as e:
    controlla("chiave rifiutata: niente tentativi inutili", e.codice == 401 and len(g.s.chiamate) == 1)
g = groq_finto([Risposta(429, "rate limit", intestazioni={"retry-after": "500"})])
try:
    g.trascrivi(b"audio", "prompt")
    controlla("Groq chiede 500 s: non si resta appesi", False)
except D.GroqIrraggiungibile:
    controlla("Groq chiede 500 s: non si resta appesi", len(g.s.chiamate) == 1)
class SessioneLenta(SessioneFinta):
    def post(self, url, **kw):
        D.time.sleep(0.03)                 # una rete appesa, in piccolo
        return super().post(url, **kw)


g = groq_finto([])
g.s = SessioneLenta([requests.Timeout("read timeout")] * 4)
scadenza, D.SCADENZA_CHIAMATA = D.SCADENZA_CHIAMATA, 0.05
try:
    g.trascrivi(b"audio", "prompt")
    controlla("rete appesa: si arrende entro la scadenza, non dopo 4 attese", False)
except D.GroqIrraggiungibile:
    controlla("rete appesa: si arrende entro la scadenza, non dopo 4 attese",
              len(g.s.chiamate) < 4, f"{len(g.s.chiamate)} tentativi")
D.SCADENZA_CHIAMATA = scadenza
g = groq_finto([Risposta(503, "giù"), Risposta(200, "ok")])
controlla("Groq sovraccarico una volta: si riprova", g.trascrivi(b"audio", "p") == "ok")
g = groq_finto([Risposta(200, "x")])
g.trascrivi(b"audio", "p" * 2000)
controlla("anche un prompt troppo lungo passato a mano viene tagliato",
          len(g.s.chiamate[0][1]["data"]["prompt"]) <= 896)

print("\n— la pulitura —")
g = groq_finto([chat("Ciao, come stai?")])
testo, grezzi = g.ripulisci("ciao come stai", "pulito", [])
corpo = g.s.chiamate[0][1]["json"]
controlla("gpt-oss ragiona poco e non manda il ragionamento",
          corpo.get("reasoning_effort") == "low" and corpo.get("include_reasoning") is False)
controlla("un pezzo solo, pulito", testo == "Ciao, come stai?" and grezzi == 0)
g = groq_finto([chat("ok")], llm="qwen/qwen3.8-27b")
g.ripulisci("ciao", "pulito", [])
controlla("gli altri modelli non ricevono parametri che non conoscono",
          "reasoning_effort" not in g.s.chiamate[0][1]["json"])
lungo = (frase * 120).strip()                          # ~7.000 caratteri: 2 pezzi
g = groq_finto([chat("PULITO UNO " * 300), DNS, DNS, DNS, DNS])
testo, grezzi = g.ripulisci(lungo, "pulito", [])
controlla("un pezzo fallisce: resta grezzo, l'altro pulito",
          grezzi == 1 and testo.startswith("PULITO UNO") and frase.strip() in testo,
          f"{grezzi} grezzi")
g = groq_finto([DNS] * 4)
try:
    g.ripulisci("testo breve", "pulito", [])
    controlla("se non riesce nessun pezzo, lo dice", False)
except D.GroqIrraggiungibile:
    controlla("se non riesce nessun pezzo, lo dice", True)
riassunto = (frase * 20).strip()
g = groq_finto([chat("Una frase.")])
try:
    g.ripulisci(riassunto, "pulito", [])
    controlla("un «riassunto» dell'LLM non sostituisce il dettato", False)
except D.PulituraSospetta:
    controlla("un «riassunto» dell'LLM non sostituisce il dettato", True)
g = groq_finto([chat("")])
try:
    g.ripulisci("ciao come stai", "pulito", [])
    controlla("una pulitura vuota non cancella niente", False)
except D.PulituraSospetta:
    controlla("una pulitura vuota non cancella niente", True)

print("\n— l'audio per Groq —")
voce = (np.sin(np.linspace(0, 2000, 16000 * 3)) * 8000).astype(np.int16)
dati, nome, mime = D.codifica(voce)
controlla("di norma FLAC", nome.endswith(".flac") and mime == "audio/flac", f"{len(dati)} byte")
limite = D.LIMITE_FILE
D.LIMITE_FILE = 1000
dati, nome, mime = D.codifica(voce)
D.LIMITE_FILE = limite
controlla("oltre il limite di Groq: Opus", nome.endswith(".ogg") and mime == "audio/ogg",
          f"{len(dati)} byte")


# ------------------------------------------------------------ l'app, a metà
class PannelloFinto:
    def __init__(self):
        self.aperto, self.testo = False, ""

    def e_aperto(self):
        return self.aperto

    def apri(self, testo=None):
        self.aperto = True
        if testo is not None:
            self.testo = testo

    def chiudi(self):
        self.aperto = False

    def aggiorna(self, *a):
        pass

    def testo_corrente(self):
        return self.testo


class MicFinto:
    def __init__(self):
        self.annullato = self.spento = 0
        self.dispositivo = ""

    def annulla(self):
        self.annullato += 1

    def spegni(self):
        self.spento += 1


class AppFinta(D.App):
    def __init__(self, groq=None):
        self._stato_iniziale({"DETTATURA_HOTKEY": "<cmd>+s", "GROQ_API_KEY": "gsk_finta"})
        if groq is not None:
            self.groq = groq
        self._icona_agganciata = True
        self._prossimo_controllo = float("inf")
        self._pannello = PannelloFinto()
        self.mic = MicFinto()
        self.lavori = []

    title = property(lambda s: "", lambda s, v: None)

    def _mostra_icona(self, nome):
        pass

    def _crea_pannello(self):
        return self._pannello

    def _elabora(self, *a):            # il thread vero non parte: si guarda solo se parte
        self.lavori.append(a)


def eventi(app):
    out = []
    while not app._eventi.empty():
        out.append(app._eventi.get())
    return out


def registrazione(app, audio: np.ndarray, sente=None):
    app._giro_reg += 1
    app._pezzi = [audio[i:i + 137] for i in range(0, len(audio), 137)]
    app._sente = bool(audio.any()) if sente is None else sente
    app._mic_nome = "MacBook Air Microphone"
    app._chiudendo = True
    app._dopo_la_registrazione()


print("\n— fine registrazione: cosa si fa dell'audio —")
SR = D.FREQUENZA
rng = np.random.default_rng(1)
a = AppFinta()
registrazione(a, np.zeros(int(SR * 0.4), np.int16))
controlla("0,4 s: troppo corto", a._etichetta == D.ERR_CORTO and not a.lavori)
a = AppFinta()
registrazione(a, np.zeros(SR * 3, np.int16))
controlla("3 s di zeri esatti: «non ho sentito la voce»", a._etichetta == D.ERR_VOCE and not a.lavori)
a = AppFinta()
registrazione(a, np.zeros(SR * 9, np.int16))
controlla("9 s di zeri esatti: il microfono non manda suono, e si dice quale",
          D.e_errore(a._etichetta) and "MacBook Air Microphone" in a._etichetta, a._etichetta)
a = AppFinta()
registrazione(a, (rng.normal(0, 3, SR * 2)).astype(np.int16))
controlla("2 s di fruscio: «non ho sentito la voce», niente Groq",
          a._etichetta == D.ERR_VOCE and not a.lavori)
a = AppFinta()
sottovoce = (np.sin(np.linspace(0, 9000, SR * 6)) * 150).astype(np.int16)
registrazione(a, sottovoce)
controlla("6 s sottovoce (sotto la soglia di voce): si manda lo stesso a Whisper",
          len(a.lavori) == 1 and a._stato == D.ELABORA,
          f"durata_voce {D.durata_voce([sottovoce]):.2f}s")
a = AppFinta()
registrazione(a, (np.sin(np.linspace(0, 3000, SR * 2)) * 9000).astype(np.int16))
controlla("2 s di voce vera: si trascrive", len(a.lavori) == 1)

print("\n— il microfono che manda solo zeri, a registrazione in corso —")
a = AppFinta()
a.registrando, a._giro_reg = True, 7
a._inizio = D.time.time() - 9
a._mic_aperto = D.time.time() - (D.MUTO_DOPO + 0.5)
a._mic_nome, a._sente = "iPhone di prova", False
D.permesso_microfono, vero = (lambda: "concesso"), D.permesso_microfono
a._tick(None)
controlla("dopo 8 s di zeri si ferma e dice quale microfono",
          not a.registrando and a.mic.annullato == 1 and "iPhone di prova" in a._etichetta,
          a._etichetta)
a = AppFinta()
a.registrando, a._giro_reg = True, 7
a._inizio = D.time.time() - 9                  # il cronometro di una dettatura vera
a._mic_aperto = D.time.time() - (D.MUTO_DOPO + 0.5)
a._sente = True
a._tick(None)
controlla("se è arrivato anche un solo campione vero, continua", a.registrando)
D.permesso_microfono = lambda: "negato"
a = AppFinta()
a._impostazioni_aperte = True                  # le Impostazioni non si aprono davvero
a._parti()
controlla("permesso negato: lo dice subito, non registra il nulla",
          a._etichetta == D.ERR_PERMESSO and not a.registrando)
D.permesso_microfono = vero

print("\n— la ⌘S tenuta giù —")
a = AppFinta()
a._premuto()
a._premuto()
controlla("due pressioni a pochi millisecondi: conta la prima", eventi(a) == ["premuto"])
a._ultima_pressione -= 1.0
a._premuto()
controlla("dopo un secondo conta di nuovo", eventi(a) == ["premuto"])

print("\n— la dettatura non si perde —")
voce = (np.sin(np.linspace(0, 6000, SR * 5)) * 9000).astype(np.int16)
g = groq_finto([DNS] * 4)
a = AppFinta(g)
D.App._elabora(a, voce, 5.0, "", a._lavoro())
salvate = D.da_riprovare()
ev = eventi(a)
controlla("rete morta: la dettatura resta in da-trascrivere", len(salvate) == 1,
          f"{[f.name for f in salvate]}")
controlla("e la barra lo dice", ev[-1] == (D.PRONTO, D.ERR_RETE), str(ev[-1]))
controlla("e gli appunti non vengono toccati", APPUNTI == [])

g = groq_finto([Risposta(200, "testo dettato prima"), chat("Testo dettato prima.")])
a = AppFinta(g)
D.App._riprova_a_mano(a, salvate, "già nella barra", a._lavoro())
ev = eventi(a)
controlla("«Riprova» la trascrive e la mette in coda al testo",
          APPUNTI and APPUNTI[-1] == "già nella barra\n\nTesto dettato prima.", repr(APPUNTI[-1:]))
controlla("e poi la toglie da da-trascrivere", D.da_riprovare() == [])
controlla("la barra mostra il testo intero", ev[-1][0] == D.PRONTO and len(ev[-1]) == 3)

g = groq_finto([Risposta(200, "questo è il grezzo"), DNS, DNS, DNS, DNS])
a = AppFinta(g)
D.App._elabora(a, voce, 5.0, "", a._lavoro())
controlla("pulitura impossibile: negli appunti va il grezzo, non il nulla",
          APPUNTI[-1] == "questo è il grezzo", repr(APPUNTI[-1]))
controlla("e da-trascrivere resta vuoto (Whisper l'aveva già sentita)", D.da_riprovare() == [])
storico = D.STORICO.read_text(encoding="utf-8")
controlla("lo storico dice che è grezzo", "pulitura non riuscita" in storico)

g = groq_finto([Risposta(200, " Grazie. ")])
a = AppFinta(g)
n = len(APPUNTI)
D.App._elabora(a, voce, 5.0, "", a._lavoro())
controlla("allucinazione: niente negli appunti", len(APPUNTI) == n
          and eventi(a)[-1] == (D.PRONTO, D.ERR_NIENTE))

g = groq_finto([Risposta(401, "invalid api key")])
a = AppFinta(g)
D.App._elabora(a, voce, 5.0, "", a._lavoro())
controlla("chiave rifiutata: lo dice, e la dettatura resta da parte",
          eventi(a)[-1] == (D.PRONTO, D.ERR_CHIAVE_RIFIUTATA) and len(D.da_riprovare()) == 1)
for f in D.da_riprovare():
    f.unlink()

print("\n— le dettature messe da parte tornano da sole —")
from AppKit import NSPasteboard  # noqa: E402
a = AppFinta()
a._eventi.put((D.PRONTO, D.ERR_RETE))
a._tick(None)
controlla("rete morta: il recupero si pianifica da solo",
          a._prossimo_recupero > D.time.time() + 10
          and a._appunti_al_fallimento == NSPasteboard.generalPasteboard().changeCount())
partiti = []
a._riprova_da_sola = lambda file, lavoro: partiti.append(file)
D.metti_da_parte(voce)
a._prossimo_recupero = D.time.time() - 1
a.registrando = True                            # mentre detti non si tocca niente
a._inizio = D.time.time()
a._tick(None)
controlla("mentre registri il recupero aspetta", not a._recupero_in_corso and not partiti)
a.registrando = False
a._tick(None)
D.time.sleep(0.1)
controlla("a registrazione finita parte, in silenzio", a._recupero_in_corso and len(partiti) == 1
          and a._stato == D.PRONTO)

g = groq_finto([Risposta(200, "dettato quando la rete era giù"),
                chat("Dettato quando la rete era giù.")])
a = AppFinta(g)
a._pianifica_recupero(0, copia=True)
n = len(APPUNTI)
D.App._riprova_da_sola(a, D.da_riprovare(), a._lavoro())
a._tick(None)
controlla("recuperata: negli appunti (nessuno li aveva toccati) e nella barra",
          len(APPUNTI) == n + 1 and APPUNTI[-1] == "Dettato quando la rete era giù."
          and a._pannello.aperto and a._pannello.testo == "Dettato quando la rete era giù.",
          repr(APPUNTI[-1]))
controlla("e da-trascrivere si svuota", D.da_riprovare() == [])

D.metti_da_parte(voce)
g = groq_finto([Risposta(200, "un'altra dettatura"), chat("Un'altra dettatura.")])
a = AppFinta(g)
a._pianifica_recupero(0, copia=False)          # come all'avvio: gli appunti non si toccano
n = len(APPUNTI)
D.App._riprova_da_sola(a, D.da_riprovare(), a._lavoro())
a._tick(None)
controlla("se gli appunti potrebbero essere di altri, resta solo nella barra",
          len(APPUNTI) == n and a._pannello.testo == "Un'altra dettatura.")

D.metti_da_parte(voce)
g = groq_finto([DNS] * 4)
a = AppFinta(g)
a._pianifica_recupero(D.RECUPERO_PRIMA, copia=True)
D.App._riprova_da_sola(a, D.da_riprovare(), a._lavoro())
a._tick(None)
controlla("rete ancora giù: niente errori a video, si riprova più tardi",
          not D.e_errore(a._etichetta) and a._pausa_recupero == 2 * D.RECUPERO_PRIMA
          and a._prossimo_recupero > D.time.time() + D.RECUPERO_PRIMA, f"pausa {a._pausa_recupero}s")
for f in D.da_riprovare():
    f.unlink()

print("\n— a cosa si accoda la dettatura nuova —")
a = AppFinta()
a._ultimo = "il prompt di stamattina"
a._pannello.aperto, a._pannello.testo = False, "il prompt di stamattina"
controlla("barra chiusa: si riparte da capo (niente testo vecchio negli appunti)",
          a._testo_attuale() == "")
a._pannello.aperto, a._pannello.testo = True, "corretto a mano nella barra"
controlla("barra aperta: si accoda a quello che si vede", a._testo_attuale() == "corretto a mano nella barra")

print("\n— la trascrizione avvisa SEMPRE quando finisce —")
g = groq_finto([Risposta(200, "testo qualsiasi"), chat("Testo qualsiasi.")])
a = AppFinta(g)
def consegna_rotta(*_a, **_k):
    raise RuntimeError("appunti rotti")
a._consegna = consegna_rotta
D.App._elabora(a, voce, 5.0, "", a._lavoro())
ev = eventi(a)
controlla("anche se la consegna esplode, l'app non resta su «trascrivo…»",
          ev and ev[-1] == (D.PRONTO, D.ERR_GENERICO), str(ev[-1:]))
for f in D.da_riprovare():
    f.unlink()

a = AppFinta()
a._chiudendo = True
a._t_fermata = D.time.time() - (D.ATTESA_CODA + 1)
a._giro_reg = 3
a._pezzi = []
a._tick(None)
controlla("se la fine della registrazione non arriva, si va avanti lo stesso",
          not a._chiudendo and a._etichetta == D.ERR_CORTO, a._etichetta)

print("\n— il .env scritto dal menu —")
D.ENV.write_text("# la chiave\nGROQ_API_KEY=gsk_segreta\nDETTATURA_HOTKEY=<cmd>+s\n", encoding="utf-8")
D.scrivi_env("DETTATURA_MICROFONO", "Mario Rossi’s iPhone Microphone", "il microfono")
cfg = D.carica_env()
controlla("aggiunge la riga nuova", cfg.get("DETTATURA_MICROFONO") == "Mario Rossi’s iPhone Microphone")
controlla("e non tocca la chiave né i commenti",
          cfg.get("GROQ_API_KEY") == "gsk_segreta" and "# la chiave" in D.ENV.read_text(encoding="utf-8"))
D.scrivi_env("DETTATURA_MICROFONO", "")
testo = D.ENV.read_text(encoding="utf-8")
controlla("rimetterla in automatico cambia la stessa riga, non ne aggiunge",
          testo.count("DETTATURA_MICROFONO=") == 1 and D.carica_env().get("DETTATURA_MICROFONO") == "")
controlla("resta leggibile solo da Reda (600)", oct(os.stat(D.ENV).st_mode & 0o777) == "0o600")

print()
if all(esiti):
    print(f"✅ tutti i {len(esiti)} controlli passati")
    sys.exit(0)
print(f"🔴 {esiti.count(False)} controlli falliti su {len(esiti)}")
sys.exit(1)
