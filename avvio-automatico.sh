#!/bin/bash
# Fa partire Dettatura da sola a ogni accesso al Mac, e la RIAPRE se muore — e
# la spegne, se cambi idea.
#
#     ./avvio-automatico.sh          accendi (e riaccendi subito)
#     ./avvio-automatico.sh spegni   spegni
#
# Perché un LaunchAgent e non un «elemento di login» dalle Impostazioni: è lo
# stesso meccanismo dei job che Reda ha già (com.reda.scout-memoria e gli
# altri), si accende e si spegne da riga di comando, e si vede con
# `launchctl list | grep reda`.
#
# 🔴 KeepAlive (11/10). Il 1/10 alle 09:55 l'app è sparita senza una riga nel
# diario — con lo swap del Mac pieno, con ogni probabilità l'ha chiusa macOS —
# e per dieci giorni ⌘S non ha fatto niente: il vecchio agente la lanciava una
# volta sola, al login, con `open -a`, e poi non sapeva più niente di lei
# (`open` finisce subito, l'app per launchd non esisteva). Adesso launchd lancia
# il programma DENTRO l'app e lo tiene d'occhio: se muore senza averlo voluto
# (crash, kill, il guardiano che esce col thread principale piantato) la
# rialza in qualche secondo. Se esci tu (menu › Esci, ⌘⇧⌥Q) esce con 0, e
# launchd la lascia stare fino al prossimo accesso.
#
# Lanciata così, senza `open`, resta un'app vera: stessa identità
# (com.reda.dettatura, quindi stesso permesso Microfono), icona nel Dock,
# barra dei menu. ProcessType Interactive: per macOS è un'app in primo piano,
# non un lavoro di sfondo da strozzare (o da chiudere per primo quando la
# memoria finisce).
set -e

ETICHETTA="com.reda.dettatura"
PLIST="$HOME/Library/LaunchAgents/$ETICHETTA.plist"
APP="/Applications/Dettatura.app"

if [ "$1" = "spegni" ]; then
  launchctl bootout "gui/$UID/$ETICHETTA" 2>/dev/null || true
  rm -f "$PLIST"
  echo "✓ spento: Dettatura non parte più da sola (e non si riapre se la chiudi)."
  echo "  (l'app resta installata, la apri quando vuoi)"
  exit 0
fi

if [ ! -x "$APP/Contents/MacOS/Dettatura" ]; then
  echo "🔴 $APP non c'è. Lancia prima ./installa.sh"
  exit 1
fi

mkdir -p "$HOME/Library/LaunchAgents"
cat > "$PLIST" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.reda.dettatura</string>
    <!-- il programma dentro l'app, NON `open -a`: con `open` launchd vede solo
         un comando che finisce subito, e non può accorgersi che l'app muore -->
    <key>ProgramArguments</key>
    <array>
        <string>/Applications/Dettatura.app/Contents/MacOS/Dettatura</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <!-- rialzala se muore senza volerlo; se esce con 0 (Esci) lasciala stare -->
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <!-- se cade appena nata, non più di una volta ogni 10 secondi -->
    <key>ThrottleInterval</key>
    <integer>10</integer>
    <key>ProcessType</key>
    <string>Interactive</string>
    <key>LimitLoadToSessionType</key>
    <string>Aqua</string>
</dict>
</plist>
EOF

# se gira una Dettatura aperta a mano (non da launchd), terrebbe il lucchetto
# e quella di launchd uscirebbe subito: la si chiude prima
launchctl bootout "gui/$UID/$ETICHETTA" 2>/dev/null || true
pkill -f "Dettatura.app/Contents/MacOS/Dettatura" 2>/dev/null || true
pkill -f "dettatura.py" 2>/dev/null || true
for _ in 1 2 3 4 5 6 7 8 9 10; do
  pgrep -f "Dettatura.app/Contents/MacOS/Dettatura" >/dev/null || break
  sleep 0.3
done
launchctl bootstrap "gui/$UID" "$PLIST"

echo "✓ acceso. Dettatura parte da sola a ogni accesso, e si riapre se muore."
echo "  per spegnerlo:  ./avvio-automatico.sh spegni"
echo
echo "→ verifica (deve comparire com.reda.dettatura con un PID):"
sleep 2
launchctl list | grep dettatura || echo "  🔴 non risulta caricato"
