#!/bin/bash
# Ricompila il bundle e lo reinstalla in /Applications.
# Serve solo dopo aver toccato dettatura.py o pannello.py — vocabolario,
# correzioni e .env vivono fuori dal bundle e si modificano senza ricompilare.
set -e
cd "$(dirname "$0")"

# se gira da sorgente, il lock impedirebbe al bundle nuovo di partire
pkill -f "Dettatura.app/Contents/MacOS/Dettatura" 2>/dev/null || true
pkill -f "dettatura.py" 2>/dev/null || true

# l'icona: la rigenera solo se manca, o se lo script è più recente
if [ ! -f Dettatura.icns ] || [ fai-icona.py -nt Dettatura.icns ]; then
  echo "→ rigenero l'icona"
  ./.venv/bin/python fai-icona.py >/dev/null
fi

./.venv/bin/pyinstaller --noconfirm --clean Dettatura.spec
rm -rf /Applications/Dettatura.app
cp -R dist/Dettatura.app /Applications/

# 🔴 LA FIRMA STABILE, e senza questa riga i permessi si perdono a ogni giro.
# PyInstaller non è riproducibile: a sorgente identico produce un bundle con
# un hash diverso ogni volta (cambiano l'eseguibile, base_library.zip e la
# firma di conseguenza). Con la firma ad-hoc di serie l'identità dell'app PER
# macOS È QUELL'HASH — «designated => cdhash H"…"» — quindi ogni ricompilazione
# è un'app nuova, e il Microfono va riconcesso da capo (la scorciatoia no:
# dal 12/9 è Carbon e non chiede permessi).
# Ancorando il requisito all'identificatore invece che all'hash, l'identità
# resta la stessa attraverso le build.
codesign --force --deep -s - --identifier com.reda.dettatura \
  -r '=designated => identifier "com.reda.dettatura"' \
  /Applications/Dettatura.app

# verifica dell'EFFETTO, non del silenzio: deve stampare l'identifier, non un cdhash
echo "→ identità dell'app per macOS:"
codesign -d -r- /Applications/Dettatura.app 2>&1 | grep -E "designated" || true

# la copia gemella in dist/ ha lo stesso identificatore e un path diverso:
# lasciata lì, Spotlight ne trova DUE e si può aprire quella sbagliata
rm -rf dist/Dettatura.app

echo "✓ installata. Controllo:"
/Applications/Dettatura.app/Contents/MacOS/Dettatura --check
open -a Dettatura
