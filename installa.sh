#!/bin/bash
# Ricompila il bundle e lo reinstalla in /Applications.
# Serve solo dopo aver toccato dettatura.py — vocabolario e correzioni
# vivono fuori dal bundle e si modificano senza ricompilare niente.
set -e
cd "$(dirname "$0")"
pkill -f "Dettatura.app/Contents/MacOS/Dettatura" 2>/dev/null || true
./.venv/bin/pyinstaller --noconfirm --clean Dettatura.spec
rm -rf /Applications/Dettatura.app
cp -R dist/Dettatura.app /Applications/
echo "✓ installata. Controllo:"
/Applications/Dettatura.app/Contents/MacOS/Dettatura --check
open -a Dettatura
