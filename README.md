# Dettatura

Icona nella barra dei menu. **⌘⇧D** per iniziare, **⌘⇧D** per finire: il testo ripulito
è già negli appunti, pronto per ⌘V in Warp.

```
🎙  ⌘⇧D  →  🔴 0:42  ⌘⇧D  →  ⏳  →  ✅ 137 parole  →  ⌘V
     registra              Groq Whisper + pulitura      appunti
```

## Accendere

L'app è già installata in **/Applications/Dettatura.app**. Doppio clic: compare 🎙
in alto a destra, e basta.

Alla prima dettatura macOS chiede due permessi — Impostazioni di Sistema → Privacy e sicurezza:

| Permesso | Serve a | Se lo neghi |
|---|---|---|
| **Microfono** | registrare | non funziona niente |
| **Monitoraggio input** | la scorciatoia ⌘⇧D | usi il menu 🎙 → *Inizia a dettare* |

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

Vivono **fuori** dal bundle, in `~/Progetti/dettatura/`, quindi si toccano senza ricompilare:
salvi il file e riparte corretto al prossimo avvio dell'app.

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
  Se sovrascrivi gli appunti per sbaglio, il testo è lì (o menu → *Ricopia l'ultimo*)
- L'audio è un file temporaneo, **cancellato subito dopo la trascrizione**
- Fuori dal Mac va solo l'audio a Groq (trascrizione) e il testo grezzo (pulitura)

## Cambiare la scorciatoia

In `.env`, sintassi pynput:
```
DETTATURA_HOTKEY=<ctrl>+<alt>+d
```

## Se qualcosa non va

| Sintomo | Causa |
|---|---|
| ⚠️ nella barra | lancia `--check` (sopra): quasi sempre è la chiave Groq scaduta |
| Non vedo l'icona 🎙 | la barra è piena e macOS la nasconde: togli qualche icona, o su Mac col notch riduci gli elementi. `pgrep -f Dettatura` dice se sta girando |
| La scorciatoia non fa niente | manca *Monitoraggio input*. Intanto usa il menu → *Inizia a dettare* |
| «Microfono non disponibile» | manca il permesso Microfono, o un'altra app lo tiene occupato |
| Trascrive in inglese | il dettato era troppo corto: Whisper indovina la lingua sui primi secondi |

## Costi

Groq `whisper-large-v3-turbo` sta nel piano gratuito: un dettato di un minuto costa
frazioni di centesimo e torna in ~1-2 secondi. La pulitura è qualche centinaio di token.
