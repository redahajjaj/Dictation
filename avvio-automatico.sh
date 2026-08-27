#!/bin/bash
# Fa partire Dettatura da sola a ogni accesso al Mac — e la spegne, se cambi idea.
#
#     ./avvio-automatico.sh          accendi
#     ./avvio-automatico.sh spegni   spegni
#
# Perché un LaunchAgent e non un «elemento di login» dalle Impostazioni: è lo
# stesso meccanismo dei 4 job che Reda ha già (com.reda.scout-memoria e gli
# altri), si accende e si spegne da riga di comando, e si vede con
# `launchctl list | grep reda`. Verificato: l'app parte, macOS la riconosce come
# com.reda.dettatura, e il lock a istanza singola continua a funzionare.
#
# 🔴 PRIMA di accenderlo serve l'Accessibilità, o al risveglio del Mac ti
# ritrovi l'app aperta con la scorciatoia morta. Come si controlla:
#     open -a Dettatura --stderr /tmp/d.err ; sleep 3 ; cat /tmp/d.err
#   vuoto = a posto · «This process is not trusted» = manca il permesso
set -e

ETICHETTA="com.reda.dettatura"
PLIST="$HOME/Library/LaunchAgents/$ETICHETTA.plist"

if [ "$1" = "spegni" ]; then
  launchctl bootout "gui/$UID/$ETICHETTA" 2>/dev/null || true
  rm -f "$PLIST"
  echo "✓ spento: Dettatura non parte più da sola."
  echo "  (l'app resta installata, la apri quando vuoi)"
  exit 0
fi

if [ ! -d /Applications/Dettatura.app ]; then
  echo "🔴 /Applications/Dettatura.app non c'è. Lancia prima ./installa.sh"
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
    <!-- `open -a` e non il binario diretto: così l'app parte come applicazione
         vera, con la sua identità e la sua icona nel Dock. Lanciando
         l'eseguibile a mano, macOS la tratta come un processo qualsiasi. -->
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/open</string>
        <string>-a</string>
        <string>/Applications/Dettatura.app</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
EOF

launchctl bootout "gui/$UID/$ETICHETTA" 2>/dev/null || true
launchctl bootstrap "gui/$UID" "$PLIST"

echo "✓ acceso. Dettatura parte da sola a ogni accesso."
echo "  per spegnerlo:  ./avvio-automatico.sh spegni"
echo
echo "→ verifica (deve comparire com.reda.dettatura):"
launchctl list | grep dettatura || echo "  🔴 non risulta caricato"
