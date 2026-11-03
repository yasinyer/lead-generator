#!/bin/bash
# Dubbelklik dit bestand op een Mac om de Lead Generator te starten.
cd "$(dirname "$0")" || exit 1

pause_and_exit() {
  echo
  read -r -p "  Druk op Enter om dit venster te sluiten..." _
  exit 1
}

if [ ! -x .venv/bin/python ]; then
  PY=""
  for c in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$c" >/dev/null 2>&1 && \
       "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      PY="$c"
      break
    fi
  done
  if [ -z "$PY" ]; then
    echo
    echo "  Python 3.10 of nieuwer is niet gevonden."
    echo "  1. Installeer Python via de pagina die nu opent (knop 'Download Python')."
    echo "  2. Dubbelklik daarna opnieuw op dit bestand."
    open "https://www.python.org/downloads/" 2>/dev/null || xdg-open "https://www.python.org/downloads/" 2>/dev/null
    pause_and_exit
  fi
  echo
  echo "  Eerste keer opstarten: Lead Generator wordt geïnstalleerd..."
  "$PY" -m venv .venv || pause_and_exit
fi

.venv/bin/python -m leadgen.bootstrap || pause_and_exit
