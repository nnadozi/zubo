from gpiozero import Button
import re
import subprocess
import time

# Hardware Setup (JP2 Block)
# The bounce_time prevents repeated trigger noise from one physical press.
vol_up_btn = Button(21, bounce_time=0.15)
vol_down_btn = Button(13, bounce_time=0.15)


def parse_volume_status(amixer_output):
    """Extract volume percent and mute state from amixer output."""
    percents = re.findall(r"\[(\d{1,3})%\]", amixer_output)
    switches = re.findall(r"\[(on|off)\]", amixer_output)
    if not percents:
        return "unknown volume"

    volume_percent = percents[-1]
    mute_state = switches[-1] if switches else "unknown"
    if mute_state == "on":
        return f"{volume_percent}% (unmuted)"
    if mute_state == "off":
        return f"{volume_percent}% (muted)"
    return f"{volume_percent}%"


def run_amixer(args):
    """Run amixer and return output for status parsing."""
    completed = subprocess.run(
        ["amixer", "-c", "0", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or "unknown amixer error"
        return None, stderr
    return completed.stdout, None


def read_current_volume():
    """Read current mixer level as a user-friendly status string."""
    output, error = run_amixer(["sget", "PCM"])
    if error:
        return f"error reading volume: {error}"
    return parse_volume_status(output)


def volume_up():
    # Apply change first, then print the real current volume.
    output, error = run_amixer(["set", "PCM", "10%+"])
    if error:
        print(f"[volume] UP failed: {error}", flush=True)
        return
    status = parse_volume_status(output) if output else read_current_volume()
    print(f"[volume] UP pressed -> current volume: {status}", flush=True)


def volume_down():
    # Apply change first, then print the real current volume.
    output, error = run_amixer(["set", "PCM", "10%-"])
    if error:
        print(f"[volume] DOWN failed: {error}", flush=True)
        return
    status = parse_volume_status(output) if output else read_current_volume()
    print(f"[volume] DOWN pressed -> current volume: {status}", flush=True)


# Link buttons to functions
vol_up_btn.when_pressed = volume_up
vol_down_btn.when_pressed = volume_down

print("--- Zubo Volume Control Active ---", flush=True)
print("Using USB Audio Card 0 -> PCM", flush=True)
print("Buttons: Volume Up on GPIO 21, Volume Down on GPIO 13", flush=True)
print(f"Current volume: {read_current_volume()}", flush=True)

try:
    while True:
        time.sleep(0.1)
except KeyboardInterrupt:
    print("[volume] volume helper is signing off...", flush=True)