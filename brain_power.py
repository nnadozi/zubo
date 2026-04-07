from gpiozero import Button
import subprocess
import os
import signal
import time

# Repo root so brain.py always sees model/, state.txt, and ONNX next to the scripts
# (GPIO launcher is often started from elsewhere, e.g. systemd or another cwd).
ZUBO_ROOT = os.path.dirname(os.path.abspath(__file__))
START_SH = os.path.join(ZUBO_ROOT, "start.sh")


def env_for_brain_stack():
    """DISPLAY for Tk face; PATH leads with venv/bin so brain.py subprocesses (e.g. piper) resolve."""
    env = os.environ.copy()
    if not env.get("DISPLAY"):
        env["DISPLAY"] = ":0"
    venv_bin = os.path.join(ZUBO_ROOT, "venv", "bin")
    if os.path.isdir(venv_bin):
        env["PATH"] = venv_bin + os.pathsep + env.get("PATH", "")
    return env


# Switching to 27 - usually ignored by LCD drivers
try:
    power_btn = Button(27, bounce_time=0.2)
except Exception as e:
    print(f"❌ Could not grab Pin 27: {e}")
    print("Try running: pkill -9 python")
    exit()

brain_process = None


def toggle_brain():
    global brain_process
    if brain_process is None:
        if not os.path.isfile(START_SH):
            print(f"❌ Missing {START_SH}")
            return
        print("🚀 BRAIN ACTIVATED!")
        # start.sh: face.py (background) + brain.py (foreground) with venv activated
        brain_process = subprocess.Popen(
            ["/bin/bash", START_SH],
            cwd=ZUBO_ROOT,
            env=env_for_brain_stack(),
            preexec_fn=os.setsid,
        )
    else:
        print("🛑 BRAIN DEACTIVATED.")
        try:
            os.killpg(os.getpgid(brain_process.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        brain_process = None


power_btn.when_pressed = toggle_brain

print("--- Zubo Power Station (GPIO 27) ---")
print("Wires: P27 and GND (Skip one row between them!)")

try:
    while True:
        time.sleep(0.1)
except KeyboardInterrupt:
    if brain_process:
        try:
            os.killpg(os.getpgid(brain_process.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass