# Trasloco del 20/11/2026 — percorsi vecchi → nuovi

Regola di Reda (19/11): i file di Claude stanno in `Claude/`. Il trasloco l'ha fatto la sessione del cervello.

| Prima | Oggi |
|---|---|
| CLAUDE.md | `Claude/CLAUDE.md` (caricato da `.claude/CLAUDE.md`, il rimando) |
| .scratch/ | `Claude/.scratch/` (sempre fuori dal repo: la riga `.scratch/` del `.gitignore` vale anche lì) |

Corretti: `prova-barra.py` e `prova-viva.py` salvano gli scatti in `Claude/.scratch/barra-liquid-glass/prototipo/barra-vera` (prima in `.scratch/…`, che avrebbero ricreato in radice). Il `.gitignore` tiene fuori anche `Claude/esiti/`.

Restano in radice il codice dell'app, la build, i `prova*.py` (importano i moduli accanto a sé), il README pubblico e i dati dell'app.

Gli handoff e gli inbox fuori dal repo citano ancora i percorsi di prima: sono storia, non si correggono. Anche l'ultima riga di «Dove vive il codice» in `Claude/CLAUDE.md` (la storia riscritta il 12/9) è storia.
