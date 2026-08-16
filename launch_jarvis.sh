#!/bin/bash
# Jarvis Launcher — inicia Jarvis + panel de control GUI
cd /home/ale/Proyectos/jarvis-dev
# GUI runs on system Python (GTK), jarvis on venv Python
exec python3 /home/ale/Proyectos/jarvis-dev/jarvis_gui.py "$@"
