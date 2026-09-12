# CLAUDE.md — Dettatura

> App nella barra dei menu del Mac: premi **⌘S**, parli, il testo ripulito è già negli appunti.
> Python + rumps (menu bar) + PyObjC (la barra di vetro) + Carbon via ctypes (la scorciatoia) + Groq (Whisper per la voce, un LLM per la pulitura).
> Uso quotidiano di Reda: se si rompe, si ferma il lavoro di tutti gli altri progetti.

**Stato del cantiere (aperto/trappole/chi fa cosa):**

@~/.claude/stato/dettatura.md

---

## La mappa in 30 secondi

```
 ⌘S  ──► App._da_scorciatoia ──► _parti ──┬─► LA BARRA SI APRE SUBITO (~250 ms)
                                     │    └─► Microfono.accendi  → thread suo
                       mentre parli  ├──► _ciclo_anteprima ──► blocchi di voce ──► Whisper
                                     │                          (non si vede: la barra
 ⌘S  ──► _ferma ──────────────────────┘                          resta una nocciola)
                                     ▼
                        _elabora ──► Whisper (audio intero)
                                 ──► correzioni.txt (regex) + vocabolario.txt (nomi propri)
                                 ──► LLM Groq (pulitura secondo il MODO)
                                 ──► ripulisci_segni ──► appunti (NSPasteboard) + storico.md
```

| File | Cos'è | Righe |
|---|---|---|
| `dettatura.py` | **tutto il cervello**: config, Groq, `Microfono`, menu, `--check`, diario | ~1130 |
| `scorciatoia.py` | **⌘S**: Carbon `RegisterEventHotKey` via ctypes — nessun permesso, nessun thread | 175 |
| `pannello.py` | la barra di vetro (PyObjC puro: blur, onda a 60 fps, animazioni) | ~1680 |
| `installa.sh` | ricompila (PyInstaller) → firma → copia in `/Applications` → `--check` → riapre | 44 |
| `ferma.sh` | `pkill -9` (un'app `LSUIElement` non compare in «Uscita forzata») | 4 |
| `avvio-automatico.sh` | accende/spegne il LaunchAgent `com.reda.dettatura` | 66 |
| `fai-icona.py` | genera `Dettatura.icns` (Python puro, zero dipendenze) | 539 |
| `prova-*.py` | banchi di prova isolati (barra, errori, audio finto, **`prova-scorciatoia.py`: ⌘S sintetico**) | — |
| `dettatura.log` | il **diario** (gitignored, accanto allo storico): avvio, scorciatoia, ogni pressione, ogni dettatura | — |

### I punti d'ingresso di `dettatura.py`

| Riga ~ | Cosa |
|---|---|
| `_cartelle()` 86 | **risorse sigillate ≠ dati modificabili** (vedi sotto) |
| `Groq` 276 | trascrizione + scelta automatica dell'LLM (`LLM_PREFERITI`, scarta i `MAI`) |
| `ripulisci_segni` 368 | toglie virgolette curve, trattini lunghi e spazi invisibili · **gli accenti NON si toccano** |
| `negli_appunti` 384 | NSPasteboard, **mai `pbcopy`** — vedi le trappole |
| `_log` 408 | il diario `dettatura.log` (stderr + file): è lì che si legge se ⌘S arriva |
| `Microfono` 428 | **CoreAudio fuori dal thread principale**, e la chiusura fuori da tutto: è la difesa dal deadlock di PortAudio |
| `App` 564 | la classe che è l'app: menu, icona, tick, ciclo di registrazione |
| `App._avvia_ascolto` 638 | **registra ⌘S con Carbon** e legge la risposta di macOS (noErr o un errore) |
| `App._tick` 809 | battito ogni 0,1 s: icona, cronometro, coda degli eventi, il picco del volume all'onda |
| `App._parti` 956 | apre **prima la barra**, poi chiede il microfono |
| `_autodiagnosi` 1145 | `Dettatura --check` |
| `_istanza_unica` 1210 | lock `fcntl` su `.dettatura.lock` |

### E in `pannello.py`

| Riga ~ | Cosa |
|---|---|
| `Onda` 514 | le linee che si allargano e si stringono: 60 fps, cresta che viaggia, gradiente blu→viola |
| `Pannello._spia_clic` 1435 | il clic **fuori** dalla barra la chiude (monitor globale del mouse: nessun permesso) |
| `Pannello.chiudi` 1536 | **dissolvenza sul posto** — non si risucchia più verso l'icona |
| `Pannello._battito` 1700 | il motorino a 60 fps dell'onda e del respiro del REC |

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

- **`pbcopy` NON riceve testo: riceve byte, e li legge con l'encoding dell'ambiente.** Un `.app`
  lanciato dal Finder o da un LaunchAgent non eredita `LANG` da nessuna shell → CoreFoundation
  ripiega su **MacRoman** (`ps eww <pid>` sul processo: `__CF_USER_TEXT_ENCODING=0x1F5:0x0:0x0`,
  quel `0x0` è MacRoman). Risultato: `perché` incollato diventa `perch√©`, `più` → `pi√π`, le
  virgolette curve → `‚Äú`. La barra mostrava il testo giusto e l'incolla no, perché in mezzo
  c'era un cambio di alfabeto — tre mesi di dettature sporche. **Si copia con NSPasteboard, che
  prende una stringa.** Da terminale il bug non si vede mai (lì `LANG` c'è): per riprodurlo,
  `env -i HOME=$HOME PATH=/usr/bin:/bin __CF_USER_TEXT_ENCODING=0x1F5:0x0:0x0 …`.
- **Il freeze con la rotellina era un deadlock di PortAudio, non un bug nostro.** Fotografato con
  `sample` il 12/9: il thread che chiude fa `Pa_AbortStream → AudioDeviceStop → HALB_Mutex::Lock`
  e aspetta; il thread audio di CoreAudio esegue `startStopCallback` (di PortAudio) →
  `AudioUnitGetProperty` e aspetta un altro mutex. **Nessuna riga di Python nei due stack.**
  Succede ogni tanto e non si può impedire con PortAudio 19.7 (12 giri isolati non lo riproducono,
  l'app viva sì). Si può solo decidere chi resta appeso: **la chiusura dello stream va in un thread
  usa-e-getta** (se sta in coda, blocca tutte le accensioni dopo di lei — sintomo: «registro…» nel
  diario senza nessun «microfono aperto», e ⌘S che non registra più in silenzio) e **il thread
  principale non tocca mai CoreAudio** (se si impicca lui, è la rotellina e il force quit).
  🔴 Non rimettere `sd.InputStream()` in `_parti`: è da lì che veniva il freeze.
- **Niente `rumps.alert` in un'app senza icona nel Dock.** Un NSAlert modale può nascere DIETRO a
  tutto: non lo vedi, il run loop entra in modal mode, e da fuori l'app sembra piantata. Gli
  avvisi si dicono nella barra (`ERR_MIC`, `ERR_CHIAVE`).
- **La barra si apre in `_parti`, prima del microfono.** Fino al 12/9 non la apriva nessuno:
  compariva quando tornava il primo blocco di anteprima da Whisper, cioè **dieci secondi dopo**
  ⌘S. Il microfono, misurato, ci mette 0,39 s: non era lui. Se qualcuno toglie quella `p.apri()`,
  il ritardo torna e sembrerà di nuovo colpa dell'audio.
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
.venv/bin/python prova-barra.py scatti   # i 10 stati della barra + 10 screenshot
cat dettatura.log             # il diario: avvio, scorciatoia, pressioni, dettature
```

**Come si guarda la barra dell'app VIVA** (non il banco di prova): la capsula è una finestra
vera, quindi si misura con `CGWindowListCopyWindowInfo` filtrando `kCGWindowOwnerName ==
"Dettatura"` e `Height >= 35` (sotto c'è l'icona nella barra dei menu, che è un'altra finestra
sua). È così che si prova che la barra compare **subito** dopo ⌘S: si manda un ⌘S sintetico e si
conta quanto ci mette a esistere.

**Prima di dire «fatto»:** `python -m py_compile` sui file toccati → `./installa.sh` (finisce con `--check` e riapre l'app) → **⌘S sintetica sul bundle installato** (un `CGEventPost` di ⌘S dal `.venv`, oppure `prova-scorciatoia.py` ad app chiusa) → `cat dettatura.log` deve mostrare «⌘S premuta → registro…». Poi Reda la prova con le dita: è l'unica cosa che qui non si può simulare al 100%.

## 🔴 Il buco aperto

Il repo **non ha remote**: 20+ commit in una copia sola, su un Mac senza Time Machine. Serve `gh auth login` + `gh repo create dettatura --private --source=. --push` — lo fa Reda.
