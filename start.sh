#!/bin/bash

echo "🚀 Powering up Zubo..."

# 1. Activate the virtual environment
source venv/bin/activate

# 2. Start the Face in the background (using the & symbol)
# We save its Process ID ($!) so we can close it later
DISPLAY=:0 python face.py &
FACE_PID=$!

# 3. Create a "Trap"
# This listens for you pressing Ctrl+C. When it hears it, it kills the Face app cleanly.
trap "echo -e '\n🛑 Shutting down Face...'; kill $FACE_PID 2>/dev/null; exit" INT TERM

# 4. Start the Brain in the foreground
# This takes over your terminal so you can see the logs and talk to it.
python brain.py
