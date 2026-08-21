#!/usr/bin/env python3
"""
Prova la catena senza aprire il microfono: la voce di sistema del Mac detta
una frase piena di nomi che Whisper sbaglierebbe, e si guarda cosa torna.

    ./.venv/bin/python prova.py
    ./.venv/bin/python prova.py "una frase tua da far leggere al Mac"
"""
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from dettatura import Groq, applica_correzioni, carica_correzioni, carica_env, carica_vocabolario

FRASE = (
    "allora senti, per Acmelux dobbiamo chiudere i sei bloccanti trovati dalle review, "
    "poi fai il deploy sul VPS con docker compose e controlla che il webhook di Stripe "
    "risponda quattrocento e non cinquecento. per Nordvento invece ho già mandato il preventivo "
    "a Mario Rossi, quindicimila di setup e dodicimila al mese. ah e la chiave di Groq "
    "in Supabase è scaduta, quindi il poller di cattura non funziona più."
)


def main() -> int:
    cfg = carica_env()
    if not cfg.get("GROQ_API_KEY"):
        print("Manca GROQ_API_KEY in .env — generala su https://console.groq.com/keys")
        return 1

    frase = sys.argv[1] if len(sys.argv) > 1 else FRASE
    audio = Path(tempfile.gettempdir()) / "prova-dettatura.wav"
    subprocess.run(
        ["say", "-v", "Alice", "-r", "180", "--data-format=LEI16@16000", "-o", str(audio), frase],
        check=True,
    )
    print(f"audio generato: {audio.stat().st_size // 1024} KB\n")

    g = Groq(cfg["GROQ_API_KEY"], cfg.get("DETTATURA_LLM", ""))
    voc = carica_vocabolario()
    corr = carica_correzioni()

    t0 = time.time()
    grezzo = g.trascrivi(audio, "Dettatura in italiano. Termini ricorrenti: " + ", ".join(voc[:60]))
    t_stt = time.time() - t0

    corretto = applica_correzioni(grezzo, corr)

    t0 = time.time()
    pulito = applica_correzioni(g.ripulisci(corretto, "pulito", voc), corr)
    t_llm = time.time() - t0

    print(f"── GREZZO (whisper, {t_stt:.1f}s) ──\n{grezzo}\n")
    print(f"── DOPO LE CORREZIONI ──\n{corretto}\n")
    print(f"── PULITO ({g.llm()}, {t_llm:.1f}s) ──\n{pulito}\n")

    attesi = ["Acmelux", "Nordvento", "Stripe", "Groq", "Supabase", "Mario Rossi", "VPS"]
    presenti = [t for t in attesi if t.lower() in pulito.lower()]
    print(f"── NOMI SCRITTI GIUSTI: {len(presenti)}/{len(attesi)} ──")
    for t in attesi:
        print(f"  {'✓' if t in presenti else '✗'} {t}")
    print(f"\ntotale: {t_stt + t_llm:.1f}s")
    audio.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
