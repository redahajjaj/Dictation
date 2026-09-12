# CLAUDE.md — Dettatura

> App nella barra dei menu del Mac: premi **⌘S**, parli, il testo ripulito è già negli appunti.
> Python + rumps (menu bar) + PyObjC (la barra di vetro) + Carbon via ctypes (la scorciatoia) + Groq (Whisper per la voce, un LLM per la pulitura).
> Uso quotidiano di Reda: se si rompe, si ferma il lavoro di tutti gli altri progetti.

**Stato del cantiere (aperto/trappole/chi fa cosa):**

@~/.claude/stato/dettatura.md

---

## La mappa in 30 secondi

```
 ⌘S  ──► App._da_scorciatoia ──► _parti ──► microfono (sounddevice, 16 kHz)
                                     │
                       mentre parli  ├──► _ciclo_anteprima ──► blocchi di voce ──► Whisper
                                     │                          (anteprima nella barra)
 ⌘S  ──► _ferma ──────────────────────┘
                                     ▼
                        _elabora ──► Whisper (audio intero)
                                 ──► correzioni.txt (regex) + vocabolario.txt (nomi propri)
                                 ──► LLM Groq (pulitura secondo il MODO)
                                 ──► appunti + storico.md
```

| File | Cos'è | Righe |
|---|---|---|
| `dettatura.py` | **tutto il cervello**: config, Groq, ciclo audio, menu, `--check`, diario | ~1030 |
| `scorciatoia.py` | **⌘S**: Carbon `RegisterEventHotKey` via ctypes — nessun permesso, nessun thread | 175 |
| `pannello.py` | la barra di vetro (PyObjC puro: blur, goccia, animazioni) | ~1620 |
| `installa.sh` | ricompila (PyInstaller) → firma → copia in `/Applications` → `--check` → riapre | 44 |
| `ferma.sh` | `pkill -9` (un'app `LSUIElement` non compare in «Uscita forzata») | 4 |
| `avvio-automatico.sh` | accende/spegne il LaunchAgent `com.reda.dettatura` | 66 |
| `fai-icona.py` | genera `Dettatura.icns` (Python puro, zero dipendenze) | 539 |
| `prova-*.py` | banchi di prova isolati (barra, errori, audio finto, **`prova-scorciatoia.py`: ⌘S sintetico**) | — |
| `dettatura.log` | il **diario** (gitignored, accanto allo storico): avvio, scorciatoia, ogni pressione, ogni dettatura | — |

### I punti d'ingresso di `dettatura.py`

| Riga ~ | Cosa |
|---|---|
| `_cartelle()` 80 | **risorse sigillate ≠ dati modificabili** (vedi sotto) |
| `Groq` 270 | trascrizione + scelta automatica dell'LLM (`LLM_PREFERITI`, scarta i `MAI`) |
| `_log` 344 | il diario `dettatura.log` (stderr + file): è lì che si legge se ⌘S arriva |
| `App` 411 | la classe che è l'app: menu, icona, tick, ciclo di registrazione |
| `App._avvia_ascolto` 482 | **registra ⌘S con Carbon** e legge la risposta di macOS (noErr o un errore) |
| `App._tick` 651 | battito ogni 0,1 s: icona, timer, coda degli eventi; se la scorciatoia non si è registrata apre la barra e lo dice |
| `_autodiagnosi` 934 | `Dettatura --check` |
| `_istanza_unica` 999 | lock `fcntl` su `.dettatura.lock` |

---

## Convenzioni di questo progetto

1. **Italiano ovunque**: nomi di funzioni, variabili, commenti, messaggi. `_parti`, `_ferma`, `negli_appunti`. Non introdurre nomi inglesi.
2. **I commenti spiegano il PERCHÉ**, mai il cosa — spesso con la trappola che li ha generati (vedi la firma in `installa.sh`). Se togli un commento del genere, la prossima sessione ricasca nel buco.
3. **Zero dipendenze inutili**: `fai-icona.py` disegna l'icona con Python puro. Prima di aggiungere un pacchetto, chiedi.
4. **Config fuori dal bundle.** Dentro un `.app` il codice è sigillato, quindi `vocabolario.txt`, `correzioni.txt`, `.env`, `storico.md` e `dettatura.log` vivono in `~/Progetti/dettatura/` (fallback: `~/Library/Application Support/Dettatura/`). **Si modificano senza ricompilare.** `installa.sh` serve solo dopo aver toccato `dettatura.py` o `pannello.py`.
5. **Il testo che vede Reda è prodotto**: i messaggi della barra e del menu si scrivono come frasi vere, non come errori tecnici.

## Le tre modalità (menu · «Modo»)

| Modo | Cosa fa l'LLM |
|---|---|
| `pulito` | ripulisce la trascrizione mantenendo le parole di Reda (default) |
| `prompt` | la trasforma in un'istruzione per un'AI |
| `grezzo` | non tocca niente, solo Whisper |

---

## 🔴 Trappole — lette PRIMA di toccare qualcosa

- **⌘S non passa più da pynput, e NON deve tornarci.** pynput usa un event tap in sola lettura che vuole «Monitoraggio input» (`kTCCServiceListenEvent`), un permesso DIVERSO dall'Accessibilità: senza, il tap nasce lo stesso (`is_alive()` sì, `AXIsProcessTrusted` sì) e i tasti non arrivano mai — tre sessioni perse il 12/9 a inseguire l'Accessibilità, mentre tccd diceva `authValue=0` e il README di agosto lo scriveva già. In più pynput 1.8 scarta gli eventi «iniettati»: non si può nemmeno provare da terminale. Oggi la scorciatoia è Carbon (`scorciatoia.py`): zero permessi, e scatta anche su un ⌘S sintetico. **Se «⌘S non fa niente»: prima `cat dettatura.log`** — dopo l'avvio deve dire «scorciatoia ⌘S registrata», e ogni pressione lascia «⌘S premuta». Niente «premuta» = l'app non gira (`pgrep -f Dettatura`), o un'altra app ha registrato ⌘S prima di lei.
- **Non toccare le righe `codesign` di `installa.sh`.** PyInstaller non è riproducibile: con la firma ad-hoc di serie l'identità dell'app per macOS è l'hash → ogni ricompilazione è un'app nuova → permessi da riconcedere. L'àncora all'identificatore (`designated => identifier "com.reda.dettatura"`) è ciò che li fa sopravvivere. Provato sul campo il 12/9.
- **`open -a App --stderr file` APPENDE, non sovrascrive.** Un log di diagnosi si `rm` prima, o si conta con `wc -l` prima e dopo — altrimenti rileggi errori vecchi e credi che il fix non abbia funzionato.
- **`--check` non prova che il tasto ARRIVI**: controlla solo che la combinazione del `.env` sia registrabile. La prova dell'effetto è `./ferma.sh && .venv/bin/python prova-scorciatoia.py` (⌘S sintetico, deve dire «2 volte su 2»), e sul bundle installato le righe «⌘S premuta → registro…» in `dettatura.log`.
- **macOS lascia registrare lo stesso ⌘S a due processi senza errore** (provato: `-9878` arriva solo per un doppione nello STESSO processo). Quindi il banco di prova si lancia ad app CHIUSA, e se un'altra utility prende ⌘S la nostra tace senza avvisi.
- **Istanza unica** via `fcntl` su `.dettatura.lock`: sorgente e bundle si vedono a vicenda. `open -n` la aggira → dopo i test, `./ferma.sh`.
- **macOS non ha `timeout`** (usa `curl --max-time`, o un loop con `sleep`).
- **Chiudere la finestra non chiude l'app**: è `LSUIElement`, vive solo nella barra dei menu.

## Comandi

```bash
./installa.sh                 # ricompila + firma + installa + --check + riapre
./ferma.sh                    # la uccide anche se piantata
./avvio-automatico.sh         # LaunchAgent: parte a ogni accesso (`spegni` per togliere)
/Applications/Dettatura.app/Contents/MacOS/Dettatura --check
.venv/bin/python dettatura.py # gira da sorgente (ma occupa il lock: prima ./ferma.sh)
./ferma.sh && .venv/bin/python prova-scorciatoia.py   # ⌘S arriva? (ad app chiusa, 4 s)
cat dettatura.log             # il diario: avvio, scorciatoia, pressioni, dettature
```

**Prima di dire «fatto»:** `python -m py_compile` sui file toccati → `./installa.sh` (finisce con `--check` e riapre l'app) → **⌘S sintetica sul bundle installato** (un `CGEventPost` di ⌘S dal `.venv`, oppure `prova-scorciatoia.py` ad app chiusa) → `cat dettatura.log` deve mostrare «⌘S premuta → registro…». Poi Reda la prova con le dita: è l'unica cosa che qui non si può simulare al 100%.

## 🔴 Il buco aperto

Il repo **non ha remote**: 20+ commit in una copia sola, su un Mac senza Time Machine. Serve `gh auth login` + `gh repo create dettatura --private --source=. --push` — lo fa Reda.
