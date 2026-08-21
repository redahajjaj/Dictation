#!/bin/bash
# Uccide Dettatura anche quando è piantata.
# Serve perché un'app LSUIElement non compare nell'elenco «Uscita forzata».
pkill -9 -f "Dettatura.app/Contents/MacOS/Dettatura" && echo "✓ fermata" || echo "non era in esecuzione"
