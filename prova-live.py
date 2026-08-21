#!/usr/bin/env python3
"""
Prova l'anteprima: spezza un audio nelle pause come fa la registrazione dal vivo
e trascrive blocco per blocco, per vedere se il testo che si forma sta in piedi.

    ./.venv/bin/python prova-live.py
"""
import sys
import tempfile
import time
from pathlib import Path

import numpy as np
import soundfile as sf

from dettatura import (
    BLOCCO_MAX, BLOCCO_MIN, FREQUENZA, PAUSA, SILENZIO,
    Groq, applica_correzioni, carica_correzioni, carica_env, carica_vocabolario,
)

FRASE = (
    "Allora, per Acmelux dobbiamo chiudere i sei bloccanti trovati dalle review. "
    "Poi fai il deploy sul VPS con docker compose. "
    "Per Nordvento invece ho già mandato il preventivo a Mario Rossi, "
    "quindicimila di setup e dodicimila al mese. "
    "Ah, e la chiave di Groq su Supabase è scaduta."
)
BLOCCO = 512  # frame per pezzo, come li consegna il microfono


def spezza(dati: np.ndarray) -> list[np.ndarray]:
    """Rifà la stessa scelta del ciclo dal vivo: si taglia dove c'è silenzio."""
    pezzi = [dati[i:i + BLOCCO] for i in range(0, len(dati), BLOCCO)]
    blocchi, corrente, muto_da = [], [], 0.0
    for p in pezzi:
        corrente.append(p)
        livello = min(1.0, float(np.sqrt(np.mean(p.astype(np.float32) ** 2))) / 4000.0)
        durata_pezzo = len(p) / FREQUENZA
        muto_da = 0.0 if livello > SILENZIO else muto_da + durata_pezzo
        durata = sum(len(c) for c in corrente) / FREQUENZA
        if durata >= BLOCCO_MIN and (muto_da > PAUSA or durata >= BLOCCO_MAX):
            blocchi.append(np.concatenate(corrente))
            corrente, muto_da = [], 0.0
    if corrente:
        blocchi.append(np.concatenate(corrente))
    return blocchi


def main() -> int:
    cfg = carica_env()
    if not cfg.get("GROQ_API_KEY"):
        print("manca GROQ_API_KEY in .env")
        return 1

    grezzo = Path(tempfile.gettempdir()) / "prova-live.wav"
    import subprocess
    subprocess.run(
        ["say", "-v", "Alice", "-r", "175", "--data-format=LEI16@16000", "-o", str(grezzo), FRASE],
        check=True,
    )
    dati, _ = sf.read(grezzo, dtype="int16")
    print(f"audio: {len(dati) / FREQUENZA:.1f}s")

    blocchi = spezza(dati)
    print(f"spezzato in {len(blocchi)} blocchi: "
          f"{', '.join(f'{len(b) / FREQUENZA:.1f}s' for b in blocchi)}\n")

    g = Groq(cfg["GROQ_API_KEY"], cfg.get("DETTATURA_LLM", ""))
    corr = carica_correzioni()
    voc = carica_vocabolario()

    anteprima = ""
    inizio = time.time()
    for n, blocco in enumerate(blocchi, 1):
        f = Path(tempfile.gettempdir()) / f"blocco-{n}.flac"
        sf.write(f, blocco, FREQUENZA, format="FLAC")
        t0 = time.time()
        contesto = anteprima[-260:] if anteprima else ", ".join(voc[:40])
        pezzo = applica_correzioni(g.trascrivi(f, contesto).strip(), corr)
        anteprima = (anteprima + " " + pezzo).strip()
        f.unlink(missing_ok=True)
        print(f"  blocco {n} (+{time.time() - t0:.1f}s) → …{anteprima[-70:]}")

    print(f"\n── QUELLO CHE VEDI MENTRE PARLI ({time.time() - inizio:.1f}s in tutto) ──")
    print(anteprima)

    t0 = time.time()
    intero = applica_correzioni(g.trascrivi(grezzo, ", ".join(voc[:40])), corr)
    finale = applica_correzioni(g.ripulisci(intero, "pulito", voc), corr)
    print(f"\n── QUELLO CHE RESTA, A FINE DETTATURA ({time.time() - t0:.1f}s) ──")
    print(finale)

    attesi = ["Acmelux", "Nordvento", "VPS", "Groq", "Supabase", "Mario Rossi"]
    print("\nnomi giusti — anteprima: "
          f"{sum(a in anteprima for a in attesi)}/{len(attesi)}"
          f"   ·   definitivo: {sum(a in finale for a in attesi)}/{len(attesi)}")
    grezzo.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
