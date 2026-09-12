# Dettatura

Icona nella barra dei menu. **⌘S** per iniziare, **⌘S** per finire: il testo ripulito
è già negli appunti, pronto per ⌘V in Warp.

```
        🎙  ← un clic sull'icona
        │
   ╭──────────────────────╮
   │ ■  ▂▅█▂▇▃▅  0:14     │   ← mentre parli: onda e cronometro, niente altro
   ╰──────────────────────╯

        🎙
        │
   ╭──────────────────────────────────────────────────────────╮
   │ 🎙  Per Acmelux dobbiamo ancora decidere il corriere     │
   │                            7 parole      ⌫    ⧉    •••   │
   ╰──────────────────────────────────────────────────────────╯
        ↑ quando c'è testo, la barra si distende
```

Una capsula di vetro che **esce da sotto l'icona**. Ha due taglie: piccola
mentre parli, lunga quando c'è qualcosa da leggere — e la larghezza si adatta
alla frase, l'altezza alle dettature che si accodano.

**Clic sull'icona** = apre la barra. **Clic destro** = il menu.

La barra **resta dove la metti**: si trascina da qualsiasi punto, sta sopra le
altre e non sparisce quando passi a Warp. Tienila di fianco al terminale. Per
rimandarla sotto l'icona basta chiudere e riaprire l'app.
Il microfono a sinistra e ⌘S fanno la stessa cosa: partire e fermarsi.

## Mentre parli si vede l'onda, non le parole

L'onda segue la tua voce — serve a vedere a colpo d'occhio che il microfono sta
prendendo davvero qualcosa. Se smetti di parlare **si appiattisce in una riga**.
Il testo arriva tutto insieme alla fine, quando la barra si distende: leggere
parole che si riscrivono da sole mentre parli fa solo muovere la barra.

Groq non trascrive in streaming: quando fermi la registrazione l'audio viene
mandato a Whisper **per intero**, ed è più preciso di quanto sarebbe pezzo per
pezzo. In una prova su 16 secondi di parlato: a blocchi 4 nomi giusti su 6,
tutto insieme 6 su 6.

### «Grazie a tutti» e altre frasi mai dette

Su audio muto Whisper non risponde «niente»: **inventa**. Restituisce frasi dei
sottotitoli su cui è stato addestrato — *Grazie a tutti*, *Sottotitoli a cura di
QTSS*, *Thank you*. Tre guardie lo impediscono:

1. un blocco si manda solo se contiene almeno **0,35 secondi di parlato vero**;
2. se la trascrizione è **soltanto** una di quelle frasi, si butta;
3. se in tutta la registrazione non c'è voce, l'app lo dice invece di trascrivere.

Il filtro guarda il testo intero: «Grazie a tutti» da solo viene scartato,
«Grazie a tutti per il lavoro su Acmelux» resta.

⚠️ Il menu ha ancora *Anteprima mentre parli*, acceso: manda a Whisper i pezzi già
pronunciati ogni 1-5 secondi. Da quando il testo non si legge più mentre parli
**non si vede da nessuna parte** — sono solo chiamate. Spegnilo dal menu.

A fine dettatura il testo compare nella barra: lo leggi, lo correggi se serve, e
**Copia** (o Invio) manda negli appunti la versione che vedi. È già negli appunti
comunque.

L'icona **Copia** diventa una spunta verde per un secondo e la barra **resta
aperta**: puoi copiare, incollare, e continuare a dettare senza riaprire niente.

**Le dettature si accumulano**: la seconda va in coda alla prima, separata da una
riga vuota — puoi dettare un pensiero, fermarti, pensare, e riprendere. Negli
appunti finisce sempre il testo completo. **Svuota** ricomincia da capo.

## Installare — 5 minuti

Serve **macOS 12+**, **Python 3.11+** e una chiave Groq (gratuita, su
[console.groq.com/keys](https://console.groq.com/keys)).

```bash
git clone git@github.com:redahajjaj/Dictation.git dettatura && cd dettatura
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python dettatura.py     # primo avvio: crea .env, vocabolario e correzioni
```

1. Apri `.env` e incolla la chiave: `GROQ_API_KEY=gsk_...` (⌃C per fermare il primo avvio)
2. `./installa.sh` — compila l'app, la mette in **/Applications** e la apre
3. Alla prima dettatura macOS chiede il **Microfono**: concedilo
4. **⌘S**, parli, **⌘S**. Il testo è già negli appunti.

Il vocabolario e le correzioni nascono da `vocabolario.esempio.txt` e
`correzioni.esempio.txt`: le copie che l'app crea sono tue, git le ignora.
Mettici i nomi che detti spesso — è quello che fa la differenza fra
«by tea lux» e «Acmelux».

## Accendere

Una volta installata: doppio clic su **/Applications/Dettatura.app** e compare 🎙
in alto a destra.

Il permesso — Impostazioni di Sistema → Privacy e sicurezza:

| Permesso | Serve a | Se lo neghi |
|---|---|---|
| **Microfono** | registrare | non funziona niente |

La scorciatoia ⌘S **non chiede permessi** (dal 12/9 è registrata con Carbon, come fanno
Alfred e Raycast): niente Accessibilità, niente Monitoraggio input.

Per averla sempre pronta: Impostazioni → Generali → Elementi login → **+** → Dettatura.

### Se qualcosa sembra non partire

```bash
/Applications/Dettatura.app/Contents/MacOS/Dettatura --check
```
Dice in cinque righe dove sta guardando, quante regole ha caricato, se la chiave è valida
e quale modello userà. È il primo comando da lanciare quando qualcosa non torna.

## Le tre modalità

| Modalità | Cosa fa | Quando |
|---|---|---|
| **Testo pulito** | punteggiatura, paragrafi, via gli «ehm», nomi giusti | il default |
| **Istruzione per l'agente** | riordina il dettato come richiesta a Claude Code | prompt lunghi per una sessione |
| **Grezzo** | solo Whisper, nessun LLM | quando vuoi le parole esatte, o sei offline dall'LLM |

## Perché scrive «Acmelux» e non «by tea lux»

`vocabolario.txt` contiene i tuoi nomi. Finisce in due posti: come contesto per Whisper
(che così tende alla grafia giusta invece che al suono) e come elenco di correzione per l'LLM.

**Se sbaglia un nome, aggiungilo lì** (menu → *Apri il vocabolario*) e riparte corretto dalla volta dopo.
Nessun riavvio: il file viene riletto all'avvio dell'app.

## Modificare vocabolario e correzioni

Vivono **fuori** dal bundle — nella cartella del repo, o in
`~/Library/Application Support/Dettatura/` se il repo non c'è — quindi si toccano
senza ricompilare: salvi il file e riparte corretto al prossimo avvio dell'app.

Si ricompila solo dopo aver cambiato `dettatura.py`:
```bash
./installa.sh
```

## Provare senza microfono

```bash
./.venv/bin/python prova.py
```
La voce di sistema detta una frase piena di nomi difficili e ti mostra grezzo, pulito
e quanti nomi ha azzeccato. Utile dopo aver toccato il vocabolario o le istruzioni.

## Dove finisce quello che detti

- **Appunti** — il testo pulito
- **`storico.md`** — ogni dettatura con data, versione pulita e grezza in un `<details>`.
  Se sovrascrivi gli appunti per sbaglio, il testo è lì (menu → *Apri lo storico*)
- L'audio è un file temporaneo, **cancellato subito dopo la trascrizione**
- Fuori dal Mac va solo l'audio a Groq (trascrizione) e il testo grezzo (pulitura)

## Cambiare la scorciatoia

In `.env` (modificatori fra parentesi angolari, più un tasto: lettere, cifre, `<space>`, `<f1>`…):
```
DETTATURA_HOTKEY=<cmd>+s
```
Poi riavvia l'app. Per provare che la combinazione arriva davvero, ad app chiusa:
```bash
./ferma.sh && ./.venv/bin/python prova-scorciatoia.py
```

## Se si blocca

**⌘⇧⌥Q la chiude** finché il suo thread principale risponde. Se è piantata
del tutto, da terminale: `./ferma.sh` dalla cartella del repo — serve perché un'app
della barra dei menu **non compare nell'elenco «Uscita forzata»**.

## Se qualcosa non va

| Sintomo | Causa |
|---|---|
| ⚠️ nella barra | lancia `--check` (sopra): quasi sempre è la chiave Groq scaduta |
| Non vedo l'icona 🎙 | la barra è piena e macOS la nasconde: togli qualche icona, o su Mac col notch riduci gli elementi. `pgrep -f Dettatura` dice se sta girando |
| La scorciatoia non fa niente | guarda `dettatura.log` (accanto allo storico): l'ultima riga deve dire «scorciatoia ⌘S registrata», e ogni pressione lascia «⌘S premuta». Se non c'è «premuta», l'app non sta girando (`pgrep -f Dettatura`) o un'altra app ha preso ⌘S prima di lei |
| «Microfono non disponibile» | manca il permesso Microfono, o un'altra app lo tiene occupato |
| Trascrive in inglese | il dettato era troppo corto: Whisper indovina la lingua sui primi secondi |
| Si blocca fermando la registrazione | non dovrebbe più: lo stream audio si chiude fuori dal thread principale. Se succede, ⌘⇧⌥Q e scrivimi cosa stavi facendo |

## Costi

Groq `whisper-large-v3-turbo` sta nel piano gratuito: un dettato di un minuto costa
frazioni di centesimo e torna in ~1-2 secondi. La pulitura è qualche centinaio di token.
