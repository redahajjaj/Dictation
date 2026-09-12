# CLAUDE.md — Dettatura

> App nella barra dei menu del Mac: premi **⌘S**, parli, il testo ripulito è già negli appunti.
> Python + rumps (menu bar) + PyObjC (la barra di vetro) + Groq (Whisper per la voce, un LLM per la pulitura).
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
| `dettatura.py` | **tutto il cervello**: config, Groq, ciclo audio, menu, `--check` | ~1050 |
| `pannello.py` | la barra di vetro (PyObjC puro: blur, goccia, animazioni) | ~1620 |
| `installa.sh` | ricompila (PyInstaller) → firma → copia in `/Applications` → `--check` → riapre | 44 |
| `ferma.sh` | `pkill -9` (un'app `LSUIElement` non compare in «Uscita forzata») | 4 |
| `avvio-automatico.sh` | accende/spegne il LaunchAgent `com.reda.dettatura` | 66 |
| `fai-icona.py` | genera `Dettatura.icns` (Python puro, zero dipendenze) | 539 |
| `prova-*.py` | banchi di prova isolati (barra, errori, audio finto) | — |

### I punti d'ingresso di `dettatura.py`

| Riga ~ | Cosa |
|---|---|
| `_cartelle()` 80 | **risorse sigillate ≠ dati modificabili** (vedi sotto) |
| `Groq` 269 | trascrizione + scelta automatica dell'LLM (`LLM_PREFERITI`, scarta i `MAI`) |
| `App` 427 | la classe che è l'app: menu, icona, tick, ciclo di registrazione |
| `App._avvia_ascolto` 499 | **la scorciatoia** — verifica l'effetto, non l'assenza di eccezioni |
| `App._tick` 685 | battito ogni 2 s: icona, timer, e **riprova l'ascolto se il permesso arriva a caldo** |
| `_autodiagnosi` 971 | `Dettatura --check` |
| `_istanza_unica` 1031 | lock `fcntl` su `.dettatura.lock` |

---

## Convenzioni di questo progetto

1. **Italiano ovunque**: nomi di funzioni, variabili, commenti, messaggi. `_parti`, `_ferma`, `negli_appunti`. Non introdurre nomi inglesi.
2. **I commenti spiegano il PERCHÉ**, mai il cosa — spesso con la trappola che li ha generati (vedi la firma in `installa.sh`). Se togli un commento del genere, la prossima sessione ricasca nel buco.
3. **Zero dipendenze inutili**: `fai-icona.py` disegna l'icona con Python puro. Prima di aggiungere un pacchetto, chiedi.
4. **Config fuori dal bundle.** Dentro un `.app` il codice è sigillato, quindi `vocabolario.txt`, `correzioni.txt`, `.env` e `storico.md` vivono in `~/Progetti/dettatura/` (fallback: `~/Library/Application Support/Dettatura/`). **Si modificano senza ricompilare.** `installa.sh` serve solo dopo aver toccato `dettatura.py` o `pannello.py`.
5. **Il testo che vede Reda è prodotto**: i messaggi della barra e del menu si scrivono come frasi vere, non come errori tecnici.

## Le tre modalità (menu · «Modo»)

| Modo | Cosa fa l'LLM |
|---|---|
| `pulito` | ripulisce la trascrizione mantenendo le parole di Reda (default) |
| `prompt` | la trasforma in un'istruzione per un'AI |
| `grezzo` | non tocca niente, solo Whisper |

---

## 🔴 Trappole — lette PRIMA di toccare qualcosa

- **La scorciatoia globale può essere morta e MUTA.** Senza il permesso di Accessibilità `pynput` non solleva niente: `start()` ritorna a posto e il thread del tap esce in silenzio. La prova è `listener.is_alive()` + `AXIsProcessTrusted`, mai «non è esploso». Se la spunta c'è ma non funziona: `tccutil reset Accessibility com.reda.dettatura`, poi riaccendere.
- **Non toccare le righe `codesign` di `installa.sh`.** PyInstaller non è riproducibile: con la firma ad-hoc di serie l'identità dell'app per macOS è l'hash → ogni ricompilazione è un'app nuova → permessi da riconcedere. L'àncora all'identificatore (`designated => identifier "com.reda.dettatura"`) è ciò che li fa sopravvivere. Provato sul campo il 12/9.
- **`open -a App --stderr file` APPENDE, non sovrascrive.** Un log di diagnosi si `rm` prima, o si conta con `wc -l` prima e dopo — altrimenti rileggi errori vecchi e credi che il fix non abbia funzionato.
- **`--check` lanciato dal terminale eredita il permesso del terminale** → falso positivo. La prova vera:
  `open -n -a Dettatura --stdout /tmp/o --stderr /tmp/e --args --check` (gli `--args` per **ultimi**, `-n` se l'app gira già).
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
```

**Prima di dire «fatto»:** `python -m py_compile` sui file toccati → `./installa.sh` (che finisce con `--check`) → **e l'ultima prova la fa Reda premendo ⌘S**, perché una scorciatoia globale non si può provare da qui.

## 🔴 Il buco aperto

Il repo **non ha remote**: 20+ commit in una copia sola, su un Mac senza Time Machine. Serve `gh auth login` + `gh repo create dettatura --private --source=. --push` — lo fa Reda.
