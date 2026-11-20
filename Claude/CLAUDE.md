# CLAUDE.md — Dettatura

> App nella barra dei menu del Mac: premi **⌘S**, parli, il testo ripulito è già negli appunti.
> Python + rumps (menu bar) + PyObjC (la barra di vetro) + Carbon via ctypes (la scorciatoia) +
> **un processo a parte per il microfono** (PortAudio) + Groq (Whisper per la voce, un LLM per la pulitura).
> Uso quotidiano di Reda: se si rompe, si ferma il lavoro di tutti gli altri progetti.

## 📁 Dove stanno le cose (regola di Reda, 19/11/2026 — vale in tutti i progetti)

- **`Claude/` è il mondo di Claude**: questo file, `TRASLOCO.md`, `.scratch/` (prototipi, screenshot e mappe di lavoro, fuori dal repo) e, quando servono, note ed esiti (`Claude/esiti/`, fuori da git). Lo organizzi liberamente.
- **Fuori da `Claude/` ci sono le cose di Reda**: le leggi e le modifichi, ma non ci lasci file tuoi. Quello che gli serve lo riceve in chat; se vuole un file lo chiede.
- Questo file lo carica `.claude/CLAUDE.md`, un rimando di una riga: Claude Code legge le istruzioni solo dalla radice o da `.claude/`. Se lo sposti, sposta anche il rimando.
- **Codice del prodotto** (in radice: i 6 moduli `dettatura.py` `microfono.py` `pannello.py` `impostazioni.py` `archivio.py` `scorciatoia.py`, la build `Dettatura.spec` + `installa.sh`, i banchi di prova `prova*.py`, che importano i moduli accanto a sé, e il `README.md` pubblico): il codice nuovo dell'app resta lì, dove serve alla build. In `Claude/` vanno solo gli attrezzi di Claude: note, esiti, prototipi, script di lavoro (Reda 1A, 20/11).
- **I dati dell'app restano in radice** (l'app li cerca lì, tutti gitignorati): `vocabolario.txt`, `correzioni.txt`, `storico.md`, `dettatura.log`, `da-trascrivere/`.
- **Restano in radice per forza** (li cercano gli strumenti lì): `.claude/`, `.gitignore`, `.env*`, `.venv/`.
- ⚠️ Il repo è **pubblico**: al push va online anche `Claude/` (tranne `.scratch/` ed `esiti/`). Niente nomi veri, anche qui.
- Trasloco del 20/11/2026: percorsi vecchi → nuovi in `Claude/TRASLOCO.md`.

**Stato del cantiere (aperto/trappole/chi fa cosa):**

@~/.claude/stato/dettatura.md

---

## La mappa in 30 secondi

```
 launchd (KeepAlive) ──► Dettatura (l'app: AppKit, barra, menu, Groq) ──► figlio «--microfono» caldo
                                                                          (PortAudio, mai nell'app)
 ⌘S ──► _da_scorciatoia ──► _parti ──┬─► LA BARRA SI APRE SUBITO (~5-40 ms)
                                     └─► Microfono.accendi ─► il figlio rilegge i dispositivi,
                                                              apre quello scelto (▾) o il predefinito
            mentre parli: audio dal figlio ─► _arriva_audio (pezzi + onda)
 ⌘S ──► _ferma ──► Microfono.spegni ──► l'ultima parola arriva ──► _dopo_la_registrazione
                                                         │   (troppo corto? muto? si trascrive?)
                                                         ▼
     _elabora ──► metti_da_parte (da-trascrivere/) ──► Whisper (con tentativi) ──► correzioni
              ──► LLM a pezzi (se fallisce: il grezzo) ──► ripulisci_segni ──► appunti + storico
              └─► Groq giù: resta in da-trascrivere/ e si riprova DA SOLA (_pianifica_recupero)
```

| File | Cos'è | Righe |
|---|---|---|
| `dettatura.py` | **il cervello**: config, Groq (tentativi, audio a blocchi, pulitura a pezzi), registrazione, recupero, menu, diagnosi, `--check` | ~2300 |
| `microfono.py` | **il microfono in un processo a parte**: il figlio (`figlio()`) e chi lo governa (`Microfono`) | ~590 |
| `pannello.py` | la barra di vetro (PyObjC puro: blur, onda a 60 fps, animazioni, il ▾ del microfono, il ⚙) | ~1890 |
| `impostazioni.py` | la finestra del ⚙: **Chiave Groq · Storico · Parole speciali** (solo la faccia: il lavoro lo fa l'app) | ~650 |
| `archivio.py` | storico, vocabolario e correzioni letti e **riscritti senza perdere niente** (puro, niente AppKit) | ~235 |
| `scorciatoia.py` | **⌘S**: Carbon `RegisterEventHotKey` via ctypes — nessun permesso, nessun thread | 178 |
| `installa.sh` | compila (PyInstaller) → ferma la vecchia → firma → `--check` → riaccende con launchd | 64 |
| `avvio-automatico.sh` | il LaunchAgent `com.reda.dettatura`: parte al login, **si riapre se muore** | 97 |
| `ferma.sh` | toglie l'app a launchd (se no rinasce) e `pkill -9` app + figli | 15 |
| `fai-icona.py` | genera `Dettatura.icns` (Python puro, zero dipendenze) | 539 |
| `requirements.txt` | le 7 dipendenze dirette (le altre arrivano da sole) | 12 |
| `*.esempio.txt` | vocabolario e correzioni **finti**, versionati: i veri sono gitignorati | — |
| `prova-*.py` | banchi di prova (vedi «Prima di dire fatto») | — |
| `dettatura.log` | il **diario** (gitignored): avvio con versione e permesso, ogni pressione, ogni dettatura, ogni guasto | — |
| `da-trascrivere/` | l'audio delle dettature che Groq non ha trascritto (gitignored: è la voce di Reda) | — |

### I punti d'ingresso di `dettatura.py`

| Riga ~ | Cosa |
|---|---|
| `_cartelle()` 133 | **risorse sigillate ≠ dati modificabili** (vedi sotto) |
| `Groq` 410 · `_Invio` 449 · `_chiama` 501 | tentativi su rete/429/5xx, **scadenza 90 s** per chiamata; 401/400 non si riprovano |
| `Groq.trascrivi` 540 | l'audio parte **a blocchi** (`encode_multipart_formdata` + `_Invio`), mai con `files=` — vedi le trappole |
| `Groq.ripulisci` 579 | **a pezzi da 6000 caratteri** (8000 token/min), un pezzo fallito resta grezzo |
| `suggerimento_whisper` 664 | il prompt di Whisper **dentro 880 caratteri** (Groq rifiuta oltre 896) |
| `codifica` 677 | FLAC, o Opus se supera i 24 MB |
| `metti_da_parte` 696 | l'audio su disco PRIMA di Groq: si cancella solo a trascrizione riuscita |
| `negli_appunti` 770 | NSPasteboard, **mai `pbcopy`** — vedi le trappole |
| `_log` 798 | il diario (ruota da solo oltre 512 KB in `dettatura.log.1`) |
| `permesso_microfono` 839 | il permesso Microfono via AVFoundation dal runtime (caricato all'avvio) |
| `_menu_modifica` 909 | il menu Modifica: senza, ⌘C/⌘V/⌘A/⌘Z non funzionano nella barra |
| `App._stato_iniziale` 1008 | **tutto lo stato** che non parla con macOS — lo usano anche le prove |
| `App._premuto` 1172 | una pressione (scorciatoia o bottone), con il filtro dei doppi tocchi |
| `App._voci_microfoni` 1214 · `scegli_microfono_da` 1247 | il menu dei microfoni (sottomenu e ▾ nella barra) |
| `App._pianifica_recupero` 1410 | le dettature messe da parte si riprovano da sole |
| `App._testo_attuale` 1491 | a cosa si accoda la dettatura nuova: **solo alla barra aperta** |
| `App._battito` 1523 | il battito ogni 0,1 s (avvolto da `_tick`, che scrive i guasti nel diario) |
| `App._parti` 1779 · `_ferma` 1845 · `_dopo_la_registrazione` 1861 | inizio, fine, e cosa farne dell'audio |
| `App._dalla_voce_al_testo` 1894 · `_elabora` 1953 · `_recupera` 1990 | la catena, e i suoi due ingressi |
| `App.apri_impostazioni` · `prova_chiave` · `salva_chiave` · `salva_parole` | quello che la finestra del ⚙ chiede all'app (la chiave si salva solo se Groq la accetta) |
| `_autodiagnosi` 2062 | `Dettatura --check` (fa nascere un figlio e gli fa elencare i microfoni) |
| `_installa_diagnosi` 2170 · `_guardiano` 2226 | eccezioni e crash nel diario · esce se il thread principale si pianta |
| `_senza_rubare_il_fuoco` 2253 | rumps non deve attivare l'app quando parte |

### `microfono.py`

| Riga ~ | Cosa |
|---|---|
| `figlio()` 77 | il processo del microfono: caldo → «via» → registra → «basta» → consegna → `os._exit` (lo stream NON si chiude) |
| `_microfoni` 194 | PortAudio rilegge l'elenco da capo: i dispositivi di ADESSO |
| `Microfono` 293 | `accendi` · `spegni` · `annulla` · `cambia` (anche a dettatura in corso) · `aggiorna_elenco` |
| `Microfono._sorveglia` 533 | la guardia: apertura impiccata → figlio nuovo; muto da 2 s o morto → lo riprende; caldo sempre pronto |

### E in `pannello.py`

| Riga ~ | Cosa |
|---|---|
| `Bottone` 421 | i bottoni rispondono al **primo** clic (la barra non è la finestra attiva) |
| `Onda` 556 | le linee che si allargano e si stringono: 60 fps, cresta che viaggia, gradiente blu→viola |
| `Pannello._spia_clic` 1499 | il clic **fuori** dalla barra la chiude (monitor globale del mouse: nessun permesso) |
| `Pannello._mostra` 1529 | **davanti a tutto senza rubare la tastiera**: ⌘V resta di Warp |
| `Pannello.chiudi` 1613 | **dissolvenza sul posto** — non si risucchia più verso l'icona |
| `Pannello._battito` 1771 | il motorino a 60 fps dell'onda e del respiro del REC |
| `sceltaMicrofono_` 1845 | il ▾ in fondo alla nocciola (riposo, registrazione, errore) |

---

## Convenzioni di questo progetto

1. **Italiano ovunque**: nomi di funzioni, variabili, commenti, messaggi. `_parti`, `_ferma`, `negli_appunti`. Non introdurre nomi inglesi.
2. **I commenti spiegano il PERCHÉ**, mai il cosa — spesso con la trappola che li ha generati (vedi la firma in `installa.sh`). Se togli un commento del genere, la prossima sessione ricasca nel buco.
3. **Zero dipendenze inutili**: `fai-icona.py` disegna l'icona con Python puro; il permesso Microfono si legge da AVFoundation **dal runtime**, senza pyobjc-framework-AVFoundation. Prima di aggiungere un pacchetto, chiedi.
4. **Config fuori dal bundle.** Dentro un `.app` il codice è sigillato, quindi `vocabolario.txt`, `correzioni.txt`, `.env`, `storico.md`, `dettatura.log` e `da-trascrivere/` vivono in `~/Progetti/dettatura/` (fallback: `~/Library/Application Support/Dettatura/`). **Si modificano senza ricompilare e senza riavviare**: l'app li rilegge da sola ogni 2 s se cambiano (`_ricarica_se_cambiata`). `installa.sh` serve solo dopo aver toccato il codice. I primi tre **non sono nel repo**: `_primo_avvio()` li semina dai `.esempio` (e `.env` vuoto) alla prima accensione.
5. **Il testo che vede Reda è prodotto**: i messaggi della barra e del menu si scrivono come frasi vere, non come errori tecnici. Gli errori sono `Errore(...)` (pannello.py): la barra li dipinge d'arancione da sé, anche quelli col nome del microfono dentro.
6. **Ogni thread di lavoro manda SEMPRE l'ultimo avviso** (`finally`): se muore zitto, l'app resta su «trascrivo…» per sempre.

## Le tre modalità (menu · «Modo»)

| Modo | Cosa fa l'LLM |
|---|---|
| `pulito` | ripulisce la trascrizione mantenendo le parole di Reda (default) |
| `prompt` | la trasforma in un'istruzione per un'AI |
| `grezzo` | non tocca niente, solo Whisper |

---

## 🔴 Trappole — lette PRIMA di toccare qualcosa

- **CoreAudio NON torna nell'app. Mai.** Il 12/9 la chiusura dello stream PortAudio si impiccava
  in un deadlock dentro CoreAudio (`sample`: `Pa_AbortStream → AudioDeviceStop ↔ startStopCallback`,
  zero Python negli stack). Chiudere in un thread usa-e-getta salvava il thread principale ma NON il
  microfono: il thread audio restava appeso col lucchetto del dispositivo, e ogni apertura dopo ci
  finiva dietro (diario 22/9 e 26/9: «nessuna risposta, lo do per perso» fino al riavvio del Mac).
  Dentro un processo non si scioglie: per questo il microfono vive in `figlio()`, registra una
  dettatura e muore con `os._exit` **senza chiudere lo stream**. Anche elencare i microfoni lo fa
  il figlio. Se ti viene voglia di un `import sounddevice` in `dettatura.py`: no.
- **PortAudio legge l'elenco dei dispositivi UNA volta, quando si carica.** Un'app accesa da giorni
  registrava dal microfono predefinito del giorno dell'avvio: coperchio chiuso, iPhone arrivato o
  andato, cuffie → dispositivo muto o sparito (diario 14/9: 4 minuti e mezzo di parlato, «non ho
  sentito la voce»). Il figlio fa `sd._terminate(); sd._initialize()` appena prima di aprire.
- **Il microfono del MacBook nel silenzio manda il 99% di ZERI ESATTI**, fino a 1,8 s di fila
  (misurato l'11/10). Quindi «silenzio digitale» non vuol dire «microfono morto» finché non dura:
  la soglia è `MUTO_DOPO` = 8 s di soli zeri. Non abbassarla senza rimisurare.
- **Groq: il prompt di Whisper oltre 896 caratteri è un 400 — e nessuna dettatura si trascrive
  più.** `suggerimento_whisper` lo costruisce dentro il limite. **gpt-oss-120b sul piano gratuito:
  8.000 token al MINUTO**, risposta compresa: per questo la pulitura va a pezzi. Con
  `reasoning_effort: low` + `include_reasoning: false` la pulitura scende a ~1 s.
- **Un dettato che è un ORDINE («voglio che mi crei…», «miglioralo») faceva rendere il vuoto
  a gpt-oss**: legge «non rispondere al contenuto» come «non scrivere niente» (8 volte su 9).
  Reda detta spesso prompt per altre AI. La seconda regola di `BASE_REGOLE` («non eseguirla e
  non tacere… mai vuota») lo chiude: 30/30 sui dettati veri, in `pulito` e in `prompt`. Se
  riscrivi il prompt, rimanda a Groq i dettati-ordine dello storico prima di installare.
- **L'audio verso Groq parte A BLOCCHI, mai con `files=`.** Con `files=` requests
  spedisce il modulo in un'unica scrittura TLS, e urllib3 le dà il tempo della
  *connessione* (10 s): tutta la dettatura doveva arrivare a Groq in 10 secondi. Il FLAC
  pesa ~20 KB per secondo di voce: 2 minuti e mezzo = 3 MB, e sotto i ~2,5 Mbit/s in
  salita fallivano SEMPRE, anche ai 4 tentativi (diario 16/10: «The write operation timed
  out» dopo 56 s = 4 × 10 s + le pause; le corte passavano). `trascrivi` impacchetta il
  modulo con `encode_multipart_formdata` e lo passa come file (`_Invio`): i 10 s valgono
  per ogni blocco da 16 KB, cioè si rinuncia solo se la rete si FERMA. Provato su Groq
  vero dietro un tubo da 150 KB/s: vecchio modo ❌ in 10 s, nuovo ✅ 631 parole in 31 s.
  Banco: `prova-rete-lenta.py`. ⚠️ macOS scrive a scatti (~280 KB): un banco con un limite
  più corto di uno scatto fa fallire anche il modo giusto, e mente.
- **Una dettatura non si butta MAI.** Sopra i 4 s si manda sempre a Whisper (una soglia di volume
  fissa buttava via chi parla piano); l'audio va in `da-trascrivere/` prima di Groq; se la pulitura
  fallisce o l'LLM rende il vuoto, negli appunti va il grezzo. Se tocchi `_elabora`, tieni questi tre.
- **`pbcopy` NON riceve testo: riceve byte, e li legge con l'encoding dell'ambiente.** Un `.app`
  lanciato dal Finder o da launchd non eredita `LANG` → MacRoman: `perché` → `perch√©`. **Si copia
  con NSPasteboard.** Da terminale il bug non si vede mai: per riprodurlo,
  `env -i HOME=$HOME PATH=/usr/bin:/bin __CF_USER_TEXT_ENCODING=0x1F5:0x0:0x0 …`.
- **La barra non deve diventare la finestra attiva.** Con `makeKeyAndOrderFront_` +
  `activateIgnoringOtherApps_` ⌘V finiva a Dettatura e in Warp non arrivava niente finché Reda non
  cliccava. `Pannello._mostra` usa `orderFrontRegardless`; i bottoni hanno `acceptsFirstMouse_`. E
  rumps all'avvio attiverebbe l'app (`_senza_rubare_il_fuoco` lo spegne): con launchd che la rialza,
  i tasti di Reda finivano nel vuoto a metà frase.
- **La barra dei menu di Reda si nasconde da sola** (`_HIHideMenuBar = 1`) e Warp è a tutto
  schermo: l'icona in alto quasi non si vede, e la barra esce in alto al centro (ripiego di `_casa`).
  Quello che conta va messo **nella barra** (il ▾ del microfono) o deve funzionare da solo (il
  recupero delle dettature), non solo nel menu.
- **launchd con `open -a` non sorveglia niente**: `open` finisce subito e per launchd l'app non
  esiste. Il 1/10 l'app è sparita (con lo swap pieno: probabilmente l'ha chiusa macOS) e per 10 giorni
  ⌘S è stata muta. Il plist lancia il binario dentro l'app con `KeepAlive SuccessfulExit=false`:
  muore da sola → rinasce in 1 s (provato con `kill -9`); esce con 0 (Esci, ⌘⇧⌥Q, istanza doppia)
  → resta giù.
- **Per fermarla davvero serve `./ferma.sh`** (fa `launchctl bootout`): un `pkill` e basta la fa
  rinascere. Per riaccenderla: `./avvio-automatico.sh`.
- **Niente `rumps.alert`** (e niente NSAlert): in un'app senza finestre un modale nasce dietro a
  tutto e sembra un blocco. Gli avvisi si dicono nella barra. Anche l'avviso di PyObjC per le
  eccezioni nel run loop è spento (`AppHelper.unexpectedErrorAlertPanel`, in `_installa_diagnosi`).
- **⌘S non passa più da pynput, e NON deve tornarci.** pynput vuole «Monitoraggio input»
  (`kTCCServiceListenEvent`): senza, il tap nasce e i tasti non arrivano mai — tre sessioni perse
  il 12/9 a inseguire l'Accessibilità. Carbon (`scorciatoia.py`) non chiede permessi, scatta anche
  su un ⌘S sintetico e **una volta sola per pressione** anche tenendo giù il tasto (provato l'11/10).
- **Non toccare le righe `codesign` di `installa.sh`.** L'àncora all'identificatore
  (`designated => identifier "com.reda.dettatura"`) fa sopravvivere il permesso Microfono alle
  ricompilazioni. Il figlio del microfono è lo stesso eseguibile: stesso permesso.
- **`soundfile` su un `BytesIO`: la dimensione si prende da `getvalue()`, non da `tell()`** — finito
  di scrivere un FLAC libsndfile torna in cima a riscrivere l'intestazione (tell() ≈ 40 byte).
- **Le parole speciali sono DUE file mostrati come UNA lista** (49 regole su 51 sono di parole
  già nel vocabolario): `archivio.scrivi_parole` li riscrive tenendo intestazione e gruppi, ma i
  gruppi di `correzioni.txt` diventano quelli del vocabolario. Prima di scrivere la versione vecchia
  va in `~/Library/Application Support/Dettatura/copie-di-sicurezza/` — FUORI dal repo, che è
  pubblico. Provato sui file veri: 51 regole identiche, nessuna voce persa, secondo giro identico.
- **La tabella delle parole è a celle** (`NSTableView` senza `viewForTableColumn`): API vecchia ma
  funzionante su macOS 26, e tre metodi bastano per modificare. Se un macOS futuro la togliesse,
  il sintomo è una tabella vuota: si passa alle viste.
- **La prima lettura del permesso carica AVFoundation: 0,5 s da solo, 3 s dentro l'app viva.**
  Per questo si fa all'avvio: alla prima ⌘S si mangiava la prima frase.
- **Le prove col microfono vero prendono la stanza**: con gente che parla, Whisper trascrive sul
  serio e il testo finisce negli appunti e in `storico.md`. Prima di un giro con `prova-bundle.py`:
  salva gli appunti e la dimensione dello storico, e rimettili dopo.
- **`open -a App --stderr file` APPENDE, non sovrascrive.** Un log di diagnosi si `rm` prima.
- **macOS lascia registrare lo stesso ⌘S a due processi senza errore**: `prova-scorciatoia.py` si
  lancia ad app CHIUSA (`./ferma.sh`), poi `./avvio-automatico.sh`.
- **Istanza unica** via `fcntl` su `.dettatura.lock`: sorgente e bundle si vedono a vicenda.
- **macOS non ha `timeout`** (usa `curl --max-time`, o un loop con `sleep`).

## Comandi

```bash
./installa.sh                 # ricompila + ferma la vecchia + firma + --check + riaccende con launchd
./ferma.sh                    # la ferma davvero (anche piantata): launchd non la riapre
./avvio-automatico.sh         # LaunchAgent con KeepAlive: parte ora e a ogni accesso (`spegni` per togliere)
launchctl kickstart -k gui/$UID/com.reda.dettatura    # riavvio pulito
/Applications/Dettatura.app/Contents/MacOS/Dettatura --check
.venv/bin/python dettatura.py # da sorgente (ma occupa il lock: prima ./ferma.sh)
cat dettatura.log             # il diario: avvio (versione, permesso), pressioni, microfoni, dettature, guasti
```

**Come si guarda la barra dell'app VIVA**: la capsula è una finestra vera, quindi si misura con
`CGWindowListCopyWindowInfo` filtrando `kCGWindowOwnerName == "Dettatura"` e `Height >= 35`.
L'icona nella barra dei menu da fuori NON si vede in `CGWindowList` (su macOS 26 la ospita il sistema).

**Prima di dire «fatto»:**
1. `py_compile` + pyflakes sui file toccati (pyflakes non è nel venv: `pip install --target` in uno scratch)
2. `prova-logica.py` (niente rete né microfono) · `prova-errore.py` · `prova-barra.py` ·
   `prova-impostazioni.py` (la finestra del ⚙ su file finti; `scatti` per le foto) ·
   `prova-rete-lenta.py` se hai toccato Groq o la rete (~45 s, finto Groq locale)
3. `prova-microfono.py` se hai toccato `microfono.py` (usa il microfono vero per ~30 s)
4. `./installa.sh` (finisce con `--check`, che fa nascere un figlio dal bundle vero)
5. `prova-bundle.py` (8 dettature sull'app installata) · `prova-clic.py`
6. Una dettatura vera e uno screenshot. Poi Reda la prova con le dita.

## 🔴 Dove vive il codice — ed è PUBBLICO

`git@github.com:redahajjaj/Dictation.git`, pubblico dal 12/9. Tre conseguenze che
non si possono dimenticare:

- **`vocabolario.txt` e `correzioni.txt` sono gitignorati.** Contengono i nomi veri
  (clienti, colleghi, progetti): erano la rubrica di Reda in chiaro. Nel repo ci
  sono solo `vocabolario.esempio.txt` e `correzioni.esempio.txt`, con nomi finti —
  `_primo_avvio()` ne fa la copia vera alla prima accensione. **Se scrivi un nome
  vero dentro un file versionato (README, prova-*.py, commenti), finisce online** —
  compresi i nomi dei microfoni (l'iPhone porta il nome del proprietario): negli
  esempi si usa «Mario Rossi».
- **`Claude/.scratch/` e `da-trascrivere/` sono fuori dal repo**: prototipi e screenshot
  la prima, la voce di Reda la seconda.
- **La storia è stata riscritta** il 12/9 (`filter-branch`) per togliere nomi e
  `.scratch` da tutti i commit. Chi avesse un vecchio clone deve ri-clonare.
