#!/bin/bash
# Ferma Dettatura anche quando è piantata — e fa sì che launchd non la riapra.
# Serve perché un'app della barra dei menu non sempre compare in «Uscita forzata».
#
# launchd (vedi avvio-automatico.sh) riapre l'app se muore: con un `pkill` e
# basta tornerebbe su in un attimo. Quindi prima la si toglie a launchd
# (bootout), poi si uccide quello che resta — app e processi del microfono.
# Per riaccenderla: ./avvio-automatico.sh (o aprila dal Finder).
launchctl bootout "gui/$UID/com.reda.dettatura" 2>/dev/null
if pkill -9 -f "Dettatura.app/Contents/MacOS/Dettatura"; then
  echo "✓ fermata (per riaccenderla: ./avvio-automatico.sh)"
else
  echo "non era in esecuzione"
fi
pkill -9 -f "dettatura.py --microfono" 2>/dev/null || true
