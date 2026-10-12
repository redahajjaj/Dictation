# Dettatura

Icona nella barra dei menu. **⌘S** per iniziare, **⌘S** per finire: il testo ripulito
è già negli appunti, pronto per ⌘V in Warp — Warp resta l'app attiva, quindi ⌘V
funziona subito, senza un clic in mezzo.

```
   ╭────────────────────────────╮
   │ ■  ▂▅█▂▇▃▅  0:14        ▾  │   ← mentre parli: onda, cronometro, e ▾ per il microfono
   ╰────────────────────────────╯

   ╭──────────────────────────────────────────────────────────╮
   │ 🎙  Per Acmelux dobbiamo ancora decidere il corriere     │
   │                            7 parole      ⌫    ⧉    •••   │
   ╰──────────────────────────────────────────────────────────╯
        ↑ quando c'è testo, la barra si distende
```

Una capsula di vetro che **esce da sotto l'icona** (o in alto al centro, se la
barra dei menu è nascosta). Ha due taglie: piccola mentre parli, lunga quando
c'è qualcosa da leggere — e la larghezza si adatta alla frase, l'altezza alle
dettature che si accodano.

**Clic sull'icona** (o sull'icona nel Dock) = apre la barra. **Clic destro** = il menu.

La barra **resta dove la metti**: si trascina da qualsiasi punto, sta sopra le
altre e non sparisce quando passi a Warp. Tienila di fianco al terminale. Per
rimandarla sotto l'icona basta chiudere e riaprire l'app. **Un clic fuori la
chiude** (la registrazione, se c'è, continua). Il microfono a sinistra e ⌘S
fanno la stessa cosa: partire e fermarsi.

## Scegliere il microfono

Il **▾** in fondo alla barra apre l'elenco dei microfoni collegati, con la
spunta su quello in uso:

- **Automatico (…)** — il microfono predefinito del Mac, *quello di adesso*: se
  colleghi le cuffie o arriva l'iPhone, la dettatura dopo usa il nuovo;
- oppure uno preciso, che resta scelto anche dopo un riavvio (finisce nel `.env`
  come `DETTATURA_MICROFONO=`).

Si può cambiare **anche mentre parli**: il microfono si riapre al volo e il
cronometro non si ferma. Se quello scelto non è collegato, si registra dal
predefinito (il diario lo dice). Lo stesso elenco sta nel menu, alla voce
**Microfono**.

## Le impostazioni: il ⚙

Il **⚙** nella barra (a riposo e sugli errori), o il menu **•••**, apre una
finestra con tre schede:

| Scheda | Cosa ci fai |
|---|---|
| **Chiave Groq** | vedi quella in uso (mascherata) e se funziona; ne incolli una nuova e premi **Prova e salva**: si salva solo se Groq la accetta. Scegli anche il modello che pulisce il testo |
| **Storico** | tutte le dettature, dalla più recente, con la ricerca; il testo pulito o quello grezzo di Whisper, e **Copia** |
| **Parole speciali** | i nomi da scrivere giusti e, accanto, come Whisper li sente male («acme lux» → «Acmelux»). Doppio clic su una cella per scrivere, **+** e **−** per aggiungere e togliere, **Salva** |

Le parole sono i due file di sempre (`vocabolario.txt` e `correzioni.txt`),
mostrati come una lista sola: al salvataggio si riscrivono tenendo intestazione
e gruppi, e la versione di prima finisce in
`~/Library/Application Support/Dettatura/copie-di-sicurezza/`. Valgono dalla
dettatura dopo. Se la chiave manca o Groq la rifiuta, la finestra si apre da
sola sulla scheda giusta.

## Mentre parli si vede l'onda, non le parole

L'onda segue la tua voce: serve a vedere a colpo d'occhio che il microfono sta
prendendo davvero qualcosa. Il testo arriva tutto insieme alla fine, quando la
barra si distende: leggere parole che si riscrivono da sole mentre parli fa
solo muovere la barra.

Groq non trascrive in streaming: quando fermi la registrazione l'audio viene
mandato a Whisper **per intero**, ed è più preciso di quanto sarebbe pezzo per
pezzo. In una prova su 16 secondi di parlato: a blocchi 4 nomi giusti su 6,
tutto insieme 6 su 6.

**Se il microfono non manda suono** — permesso negato, coperchio chiuso,
l'iPhone in tasca — dopo 8 secondi di silenzio assoluto la barra lo dice, col
nome del microfono: «"iPhone" non manda suono». Il ▾ è lì accanto per
sceglierne un altro.

### «Grazie a tutti» e altre frasi mai dette

Su audio muto Whisper non risponde «niente»: **inventa**. Restituisce frasi dei
sottotitoli su cui è stato addestrato — *Grazie a tutti*, *Sottotitoli a cura di
QTSS*, *Thank you*. Due guardie lo impediscono:

1. una dettatura **corta** (sotto i 4 secondi) senza voce non si manda nemmeno;
2. se la trascrizione è **soltanto** una di quelle frasi, si butta.

Il filtro guarda il testo intero: «Grazie a tutti» da solo viene scartato,
«Grazie a tutti per il lavoro su Acmelux» resta. Sopra i 4 secondi l'audio va
sempre a Whisper: una soglia di volume fissa sbaglia quando parli piano o
lontano dal microfono, e buttava via dettature intere.

## Il testo nella barra

A fine dettatura il testo compare nella barra: lo leggi, e se serve **ci clicchi
e lo correggi** (⌘A, ⌘C, ⌘V, ⌘Z funzionano); **Copia** (o Invio) manda negli
appunti la versione che vedi. È già negli appunti comunque.

L'icona **Copia** diventa una spunta verde per un secondo e la barra **resta
aperta**.

**Le dettature si accumulano finché la barra è aperta**: la seconda va in coda
alla prima, separata da una riga vuota — puoi dettare un pensiero, fermarti,
pensare, e riprendere. Negli appunti finisce sempre il testo completo.
**Svuota** ricomincia da capo, e così una barra chiusa: la dettatura dopo parte
pulita (la vecchia resta nello storico, e un clic sull'icona la rimette nella
barra).

## Una dettatura non si perde

- **Rete assente o Groq giù**: si riprova da soli per ~15 secondi. Se non
  basta, l'audio resta in `da-trascrivere/` e il menu offre **Riprova le
  dettature non trascritte** — quando la rete torna, un clic e il testo arriva
  negli appunti.
- **La pulitura non riesce** (rete, limiti di Groq): negli appunti va il testo
  grezzo di Whisper, invece di niente. Le dettature lunghe si puliscono a pezzi,
  così stanno nei limiti del piano gratuito.
- **L'app muore** (crash, macOS che la chiude perché la memoria è finita):
  launchd la riapre in un secondo. Se si pianta, si accorge da sola e riparte.
- **Il microfono si impunta o sparisce a metà** (cuffie spente, iPhone andato
  via): il microfono vive in un processo a parte, che si butta e si sostituisce
  da solo; la registrazione continua.

## Installare — 5 minuti

Serve **macOS 12+**, **Python 3.11+** e una chiave Groq (gratuita, su
[console.groq.com/keys](https://console.groq.com/keys)).

```bash
git clone git@github.com:redahajjaj/Dictation.git dettatura && cd dettatura
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python dettatura.py     # primo avvio: crea .env, vocabolario e correzioni
```

1. `./installa.sh` — compila l'app, la mette in **/Applications** e la apre
2. Alla prima ⌘S si apre la scheda **Chiave Groq**: incolla la chiave, **Prova e salva**
3. `./avvio-automatico.sh` — parte da sola a ogni accesso, e si riapre se muore
4. Alla prima dettatura macOS chiede il **Microfono**: concedilo
5. **⌘S**, parli, **⌘S**. Il testo è già negli appunti.

Il vocabolario e le correzioni nascono da `vocabolario.esempio.txt` e
`correzioni.esempio.txt`: le copie che l'app crea sono tue, git le ignora.
Mettici i nomi che detti spesso — è quello che fa la differenza fra
«by tea lux» e «Acmelux».

## Il permesso

Impostazioni di Sistema → Privacy e sicurezza:

| Permesso | Serve a | Se lo neghi |
|---|---|---|
| **Microfono** | registrare | la barra lo dice e apre lei il pannello giusto |

La scorciatoia ⌘S **non chiede permessi** (dal 12/9 è registrata con Carbon, come fanno
Alfred e Raycast): niente Accessibilità, niente Monitoraggio input.

### Se qualcosa sembra non partire

```bash
/Applications/Dettatura.app/Contents/MacOS/Dettatura --check
```
Dice dove sta guardando, quante regole ha caricato, se la chiave è valida, quale
modello userà e quali microfoni vede. È il primo comando da lanciare quando
qualcosa non torna. Il secondo è il **diario**: menu → *Apri il diario*.

## Le tre modalità

| Modalità | Cosa fa | Quando |
|---|---|---|
| **Testo pulito** | punteggiatura, paragrafi, via gli «ehm», nomi giusti | il default |
| **Istruzione per l'agente** | riordina il dettato come richiesta a Claude Code | prompt lunghi per una sessione |
| **Grezzo** | solo Whisper, nessun LLM | quando vuoi le parole esatte, o sei offline dall'LLM |

## Perché scrive «Acmelux» e non «by tea lux»

`vocabolario.txt` contiene i tuoi nomi. Finisce in due posti: come contesto per Whisper
(che così tende alla grafia giusta invece che al suono) e come elenco di correzione per l'LLM.

**Se sbaglia un nome, aggiungilo** in **⚙ → Parole speciali**, e scrivi accanto come
l'ha sentito: vale dalla dettatura dopo, senza riavviare niente. Si possono anche
modificare i file a mano: l'app si accorge da sola che sono cambiati (lo stesso
per il `.env`: chiave, scorciatoia).

## Ricompilare

Si ricompila solo dopo aver cambiato il codice (`dettatura.py`, `microfono.py`,
`pannello.py`):
```bash
./installa.sh
```

## Provare

```bash
./.venv/bin/python prova-logica.py      # le regole: tentativi, dettature da parte, pulitura (niente rete)
./.venv/bin/python prova-microfono.py   # il microfono in un processo a parte (usa il microfono vero)
./.venv/bin/python prova-barra.py       # la barra nei suoi stati
./.venv/bin/python prova.py             # la catena vera: la voce del Mac detta, Groq trascrive
```

## Dove finisce quello che detti

- **Appunti** — il testo pulito
- **`storico.md`** — ogni dettatura con data, versione pulita e grezza in un `<details>`.
  Se sovrascrivi gli appunti per sbaglio, il testo è lì: **⚙ → Storico**, cerca, Copia
- **L'audio** si salva in `da-trascrivere/` solo il tempo di mandarlo a Groq, e si
  cancella appena è trascritto; resta solo se la trascrizione non è riuscita
- Fuori dal Mac va solo l'audio a Groq (trascrizione) e il testo grezzo (pulitura)

## Cambiare la scorciatoia

In `.env` (modificatori fra parentesi angolari, più un tasto: lettere, cifre, `<space>`, `<f1>`…):
```
DETTATURA_HOTKEY=<cmd>+s
```
Vale subito, senza riavviare. Per provare che la combinazione arriva davvero, ad app chiusa:
```bash
./ferma.sh && ./.venv/bin/python prova-scorciatoia.py; ./avvio-automatico.sh
```

## Se si blocca

**⌘⇧⌥Q la chiude** finché il suo thread principale risponde. Se è piantata del
tutto, si accorge da sola entro un minuto e riparte. Se vuoi farlo tu, dalla
cartella del repo:

```bash
./ferma.sh && ./avvio-automatico.sh     # ferma (anche piantata) e riaccende
```

`./ferma.sh` da solo la ferma e basta: launchd non la riapre finché non lanci
`./avvio-automatico.sh` (o non la apri dal Finder).

## Se qualcosa non va

| Sintomo | Causa |
|---|---|
| ⚠️ nella barra | leggi il messaggio: dice cosa è successo e, per il microfono, quale |
| «Manca la chiave Groq» / «Groq rifiuta la chiave» | si apre da sola **⚙ → Chiave Groq**: incolla quella nuova e **Prova e salva** |
| «Groq non risponde: dettatura messa da parte» | rete o Groq giù: quando torna, menu → *Riprova le dettature non trascritte* |
| «"…" non manda suono» | quel microfono manda silenzio assoluto: ▾ e scegline un altro |
| «Manca il permesso del Microfono» | la barra apre le Impostazioni al posto giusto: accendi Dettatura |
| La scorciatoia non fa niente | guarda il diario (menu → *Apri il diario*): ogni pressione lascia «⌘S premuta». Se non c'è, l'app non sta girando (`pgrep -f Dettatura`) o un'altra app ha preso ⌘S prima di lei |
| Non vedo l'icona | la barra dei menu è nascosta o piena: il ▾ nella barra e l'icona nel Dock fanno tutto lo stesso |
| Trascrive in inglese | il dettato era troppo corto: Whisper indovina la lingua sui primi secondi |

## Costi

Groq `whisper-large-v3-turbo` sta nel piano gratuito: un dettato di un minuto costa
frazioni di centesimo e torna in ~1-2 secondi. La pulitura è qualche centinaio di token.
