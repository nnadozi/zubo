import os
import signal
import subprocess
import sys
import time
from gpiozero import Button

# Repo root so brain.py always sees model/, state.txt, and ONNX next to the scripts
# (GPIO launcher is often started from elsewhere, e.g. systemd or another cwd).
ZUBO_ROOT = os.path.dirname(os.path.abspath(__file__))
BRAIN_PY = os.path.join(ZUBO_ROOT, "brain.py")
FACE_PY = os.path.join(ZUBO_ROOT, "face.py")
VOLUME_PY = os.path.join(ZUBO_ROOT, "volume.py")


def env_for_stack():
    """Build runtime env with display + venv path for every child process."""
    env = os.environ.copy()
    if not env.get("DISPLAY"):
        env["DISPLAY"] = ":0"
    # Tk windows need XAUTHORITY when launched from SSH/systemd contexts.
    if not env.get("XAUTHORITY"):
        default_xauth = os.path.join(env.get("HOME", "/home/hello"), ".Xauthority")
        env["XAUTHORITY"] = default_xauth
    venv_bin = os.path.join(ZUBO_ROOT, "venv", "bin")
    if os.path.isdir(venv_bin):
        env["PATH"] = venv_bin + os.pathsep + env.get("PATH", "")
    return env


def start_process(script_path):
    """Start one child script in its own process group."""
    proc = subprocess.Popen(
        [sys.executable, script_path],
        cwd=ZUBO_ROOT,
        env=env_for_stack(),
        preexec_fn=os.setsid,
    )
    return proc


def stop_process(proc, name):
    """Stop one process group gracefully, then force-kill if needed."""
    if proc is None:
        return

    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        proc.wait(timeout=3)
    except ProcessLookupError:
        pass
    except subprocess.TimeoutExpired:
        print(f"[power] {name} did not exit on SIGTERM; sending SIGKILL.")
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
        except ProcessLookupError:
            pass


# Global process handles for the stack controlled by the power button.
brain_process = None
face_process = None
volume_process = None


def verify_required_files():
    """Ensure every required runtime script exists before power-on."""
    required = {
        "brain": BRAIN_PY,
        "face": FACE_PY,
        "volume": VOLUME_PY,
    }
    missing = [name for name, path in required.items() if not os.path.isfile(path)]
    if not missing:
        return True
    for name in missing:
        print(f"[power] Missing script for {name}: {required[name]}")
    return False


def refresh_process_handles():
    """Clear handles for children that already exited."""
    global brain_process, face_process, volume_process

    if brain_process is not None and brain_process.poll() is not None:
        brain_process = None
    if face_process is not None and face_process.poll() is not None:
        face_process = None
    if volume_process is not None and volume_process.poll() is not None:
        volume_process = None


def start_stack():
    """Power-on sequence: face -> volume -> brain."""
    global brain_process, face_process, volume_process

    refresh_process_handles()
    if not verify_required_files():
        return
    if stack_is_running():
        print("[power] Stack is already ON.")
        return
    if any((brain_process, face_process, volume_process)):
        # If only part of the stack is alive, reset first so ON is deterministic.
        stop_stack()

    print("[power] Power ON: starting face, volume, and brain.")
    face_process = start_process(FACE_PY)
    # Detect face launch failures quickly so display issues are obvious in logs.
    time.sleep(0.25)
    if face_process.poll() is not None:
        print(
            f"[power] face.py exited immediately (code={face_process.returncode}). "
            "Check DISPLAY/XAUTHORITY and run `python face.py` directly to inspect errors."
        )
        face_process = None
        return

    volume_process = start_process(VOLUME_PY)
    brain_process = start_process(BRAIN_PY)
    print("[power] Stack is ON.")


def stop_stack():
    """Power-off sequence: brain -> volume -> face."""
    global brain_process, face_process, volume_process

    refresh_process_handles()
    if not any((brain_process, face_process, volume_process)):
        print("[power] Stack is already OFF.")
        return

    print("[power] Power OFF: stopping brain, volume, and face.")
    stop_process(brain_process, "brain")
    stop_process(volume_process, "volume")
    stop_process(face_process, "face")
    brain_process = None
    volume_process = None
    face_process = None
    print("[power] Stack is OFF.")


def stack_is_running():
    """True when all managed child processes are alive."""
    refresh_process_handles()
    return all(
        proc is not None and proc.poll() is None
        for proc in (brain_process, face_process, volume_process)
    )


def toggle_power():
    """GPIO callback: one button toggles the entire runtime stack."""
    if stack_is_running():
        stop_stack()
    else:
        start_stack()


def main():
    try:
        power_btn = Button(27, bounce_time=0.1)
    except Exception as err:
        print(f"[power] Could not initialize GPIO 27: {err}")
        raise SystemExit(1)

    power_btn.when_pressed = toggle_power

    print("--- Zubo Power Station (GPIO 27) ---")
    print("Press power button once to turn ON all services.")
    print("Press power button again to turn OFF all services.")

    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        print("\n[power] Keyboard interrupt; shutting down stack.")
        stop_stack()


if __name__ == "__main__":
    main()