"""I file di Reda — storico, vocabolario, correzioni — letti e riscritti senza rovinarli.

Li usa la finestra delle impostazioni (impostazioni.py). Niente AppKit qui
dentro: sono funzioni pure, e prova-logica.py le prova su file finti.

**Le parole speciali.** Sono due file con due compiti:
- `vocabolario.txt` — i nomi da scrivere giusti: vanno a Whisper come contesto e
  all'LLM come elenco;
- `correzioni.txt` — come Whisper li SENTE male («acme lux») → come si scrivono
  («Acmelux»): una sostituzione secca, che non sbaglia mai.
Su 51 regole, 49 parlano di una parola che è anche nel vocabolario (misurato
l'11/10): per Reda sono la stessa cosa, «le parole con la pronuncia vaga».
Quindi la finestra li mostra come UNA lista — parola · come la sente Whisper ·
gruppo — e al salvataggio li riscrive tutti e due.

🔴 Riscriverli senza perdere niente:
- l'intestazione di ogni file (le righe di spiegazione in cima) resta com'è;
- i gruppi (`# --- persone ---`) restano, nell'ordine in cui compaiono;
- prima di scrivere, la versione vecchia va in una copia di sicurezza FUORI
  dal repo (i nomi veri non devono finire su GitHub, che è pubblico);
- si scrive accanto e poi si sostituisce: un file mezzo scritto non esiste mai.
"""
from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# le copie di sicurezza: fuori dal repo, perché dentro ci sono i nomi veri
COPIE = Path.home() / "Library" / "Application Support" / "Dettatura" / "copie-di-sicurezza"
COPIE_DA_TENERE = 20       # per file: le più vecchie si cancellano
GRUPPO_SENZA_NOME = "altro"

_GRUPPO = re.compile(r"^\s*#\s*-{2,}\s*(.*?)\s*-{2,}\s*$")


# =================================================================== storico
@dataclass
class Trascrizione:
    quando: str      # «2026-10-12 09:41»
    modo: str        # «pulito», «prompt», «pulito · pulitura non riuscita, testo grezzo»
    secondi: int
    testo: str       # quello che è andato negli appunti
    grezzo: str      # quello che ha sentito Whisper


_TESTA = re.compile(r"^## (\d{4}-\d{2}-\d{2} \d{2}:\d{2}) · (.+?) · (\d+)s\s*$")
_DETTAGLI = "<details><summary>grezzo</summary>"


def leggi_storico(percorso: Path) -> list[Trascrizione]:
    """Le dettature dello storico, dalla più recente.

    Il formato è quello di `scrivi_storico` in dettatura.py: un titolo
    `## quando · modo · Ns`, il testo, e il grezzo dentro un <details>."""
    try:
        righe = percorso.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    voci, testa, corpo = [], None, []

    def chiudi():
        if testa is not None:
            testo, grezzo = _separa("\n".join(corpo))
            voci.append(Trascrizione(testa[0], testa[1], int(testa[2]), testo, grezzo))

    for riga in righe:
        m = _TESTA.match(riga)
        if m:
            chiudi()
            testa, corpo = m.groups(), []
        elif testa is not None:
            corpo.append(riga)
    chiudi()
    voci.reverse()
    return voci


def _separa(corpo: str) -> tuple[str, str]:
    testo, _, resto = corpo.partition(_DETTAGLI)
    grezzo = resto.split("</details>")[0] if resto else ""
    return testo.strip(), grezzo.strip()


# ========================================================== parole speciali
@dataclass
class Parola:
    parola: str      # come si scrive
    varianti: str    # come la sente Whisper, separate da virgole («» = nessuna)
    gruppo: str      # «persone», «progetti e aziende»…


def _righe(percorso: Path) -> list[str]:
    try:
        return percorso.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []


def _intestazione(righe: list[str]) -> list[str]:
    """Le righe di spiegazione in cima: commenti e righe vuote prima del primo
    gruppo o della prima voce. Restano come sono, sempre."""
    testa = []
    for riga in righe:
        s = riga.strip()
        if _GRUPPO.match(riga) or (s and not s.startswith("#")):
            break
        testa.append(riga)
    while testa and not testa[-1].strip():
        testa.pop()
    return testa


def _voci_con_gruppo(righe: list[str]):
    """(gruppo, voce) per ogni riga che non è un commento."""
    gruppo = GRUPPO_SENZA_NOME
    for riga in righe:
        m = _GRUPPO.match(riga)
        if m:
            gruppo = m.group(1) or GRUPPO_SENZA_NOME
            continue
        s = riga.strip()
        if s and not s.startswith("#"):
            yield gruppo, s


def pulisci_varianti(varianti: str, parola: str = "") -> str:
    """«acme lux,  akme lux,, Acmelux» → «acme lux, akme lux»: niente vuoti,
    niente doppioni, niente variante uguale alla parola stessa."""
    viste, fuori = set(), []
    for v in varianti.split(","):
        v = " ".join(v.split())
        if not v or v.lower() == parola.lower() or v.lower() in viste:
            continue
        viste.add(v.lower())
        fuori.append(v)
    return ", ".join(fuori)


def leggi_parole(vocabolario: Path, correzioni: Path) -> list[Parola]:
    """Vocabolario e correzioni in una lista sola, nell'ordine del vocabolario.

    Le regole di correzione la cui parola non è nel vocabolario vanno in fondo,
    nel loro gruppo: non si perde niente."""
    regole: dict[str, tuple[str, str]] = {}
    for gruppo, riga in _voci_con_gruppo(_righe(correzioni)):
        if "=" not in riga:
            continue
        giusto, _, varianti = riga.partition("=")
        giusto = giusto.strip()
        if giusto:
            prima = regole.get(giusto, ("", gruppo))[0]
            regole[giusto] = (pulisci_varianti(prima + "," + varianti, giusto), gruppo)
    parole, viste = [], set()
    for gruppo, voce in _voci_con_gruppo(_righe(vocabolario)):
        if voce in viste:
            continue
        viste.add(voce)
        parole.append(Parola(voce, regole.get(voce, ("", ""))[0], gruppo))
    for giusto, (varianti, gruppo) in regole.items():
        if giusto not in viste:
            viste.add(giusto)
            parole.append(Parola(giusto, varianti, gruppo))
    return parole


def normalizza(parole: list[Parola]) -> list[Parola]:
    """Quello che si salverà davvero: niente righe senza parola, niente doppioni
    (vince la prima), spazi e virgole in ordine, un gruppo per tutti."""
    fuori, viste = [], set()
    for p in parole:
        parola = " ".join(p.parola.split())
        if not parola or "=" in parola or parola.startswith("#") or parola.lower() in viste:
            continue
        viste.add(parola.lower())
        gruppo = " ".join(p.gruppo.replace("#", " ").replace("-", " ").split()) or GRUPPO_SENZA_NOME
        fuori.append(Parola(parola, pulisci_varianti(p.varianti, parola), gruppo))
    return fuori


INTESTAZIONE_VOCABOLARIO = [
    "# Vocabolario — i nomi che Whisper sbaglierebbe.",
    "# Una voce per riga. Le righe che iniziano con # sono ignorate.",
    "# Vengono passate a Whisper come suggerimento e all'LLM come lista di correzione.",
]
INTESTAZIONE_CORREZIONI = [
    "# Come Whisper SENTE  →  come si SCRIVE.",
    "#",
    "#   forma giusta = variante, altra variante, altra ancora",
]


def testi_parole(parole: list[Parola], righe_vocabolario: list[str],
                 righe_correzioni: list[str]) -> tuple[str, str]:
    """(nuovo vocabolario.txt, nuove correzioni.txt): intestazioni di prima,
    gruppi nell'ordine in cui compaiono."""
    parole = normalizza(parole)
    gruppi: dict[str, list[Parola]] = {}
    for p in parole:
        gruppi.setdefault(p.gruppo, []).append(p)

    voc = _intestazione(righe_vocabolario) or list(INTESTAZIONE_VOCABOLARIO)
    cor = _intestazione(righe_correzioni) or list(INTESTAZIONE_CORREZIONI)
    for gruppo, membri in gruppi.items():
        voc += ["", f"# --- {gruppo} ---"] + [p.parola for p in membri]
        regole = [f"{p.parola} = {p.varianti}" for p in membri if p.varianti]
        if regole:
            cor += ["", f"# --- {gruppo} ---"] + regole
    return "\n".join(voc) + "\n", "\n".join(cor) + "\n"


def scrivi_parole(parole: list[Parola], vocabolario: Path, correzioni: Path) -> None:
    """Riscrive i due file. La versione di prima va in COPIE, e si scrive
    accanto per poi sostituire: o il file nuovo intero, o quello vecchio."""
    nuovo_voc, nuovo_cor = testi_parole(parole, _righe(vocabolario), _righe(correzioni))
    for percorso, testo in ((vocabolario, nuovo_voc), (correzioni, nuovo_cor)):
        if percorso.exists() and percorso.read_text(encoding="utf-8") == testo:
            continue
        _copia_di_sicurezza(percorso)
        accanto = percorso.with_name(f".{percorso.name}.nuovo")
        accanto.write_text(testo, encoding="utf-8")
        os.replace(accanto, percorso)


def _copia_di_sicurezza(percorso: Path) -> None:
    if not percorso.exists():
        return
    COPIE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(percorso, COPIE / f"{percorso.stem}-{datetime.now():%Y%m%d-%H%M%S}{percorso.suffix}")
    vecchie = sorted(COPIE.glob(f"{percorso.stem}-*{percorso.suffix}"))
    for f in vecchie[:-COPIE_DA_TENERE]:
        f.unlink(missing_ok=True)
