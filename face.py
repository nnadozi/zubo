import tkinter as tk
import os
import math
import time
import random
import json

# Allow standalone runs from SSH/TTY shells where GUI vars are absent.
os.environ.setdefault("DISPLAY", ":0")
os.environ.setdefault("XAUTHORITY", os.path.join(os.path.expanduser("~"), ".Xauthority"))

# Build the window with defensive settings so it reliably appears on Raspberry Pi desktops.
try:
    root = tk.Tk()
except tk.TclError as err:
    print(
        "[face] Tk failed to open display: "
        f"{err}. DISPLAY={os.environ.get('DISPLAY')} "
        f"XAUTHORITY={os.environ.get('XAUTHORITY')}"
    )
    raise

screen_w = root.winfo_screenwidth()
screen_h = root.winfo_screenheight()
root.title("Zubo Face")
root.geometry(f"{screen_w}x{screen_h}+0+0")
root.attributes("-fullscreen", True)
root.attributes("-topmost", True)
root.configure(bg="black")
root.config(cursor="none")
root.focus_force()
root.lift()


def keep_window_visible():
    root.lift()
    root.after(2000, keep_window_visible)


canvas = tk.Canvas(root, width=480, height=320, bg="black", highlightthickness=0)
canvas.pack(expand=True)


# --- MOUTH TIMING (clock-based) ---
# brain.py writes mouth.json with wall-clock start_time and word intervals.
# We read it once when SPEAKING begins, then use time.time() each frame
# to figure out exactly which word is active — no file-poll lag.
cached_mouth_data = None
cached_mouth_mtime = 0.0


def load_mouth_data():
    """Reload mouth.json only when it changes on disk."""
    global cached_mouth_data, cached_mouth_mtime
    try:
        st = os.stat("mouth.json")
        if st.st_mtime != cached_mouth_mtime:
            cached_mouth_mtime = st.st_mtime
            with open("mouth.json", "r") as f:
                cached_mouth_data = json.load(f)
    except Exception:
        pass
    return cached_mouth_data


def get_current_mouth(now):
    """
    Returns (word, is_open) based on wall-clock time and mouth.json intervals.
    This is the core of the sync fix: face.py independently computes the
    correct mouth position at any instant from real time.
    """
    data = load_mouth_data()
    if not data:
        return "", False

    elapsed = now - data.get("start_time", now)
    duration = data.get("duration", 0)
    intervals = data.get("intervals", [])

    if elapsed < 0 or elapsed > duration or not intervals:
        return "", False

    for iv in intervals:
        if iv["start"] <= elapsed < iv["end"]:
            return iv["word"], True

    # Between words (in a gap).
    for i, iv in enumerate(intervals):
        if elapsed < iv["start"]:
            return iv["word"], False
    return intervals[-1]["word"], False


# --- BLINK ---
next_blink_at = time.time() + random.uniform(4.0, 5.0)
blink_end_at = 0.0
BLINK_DUR = 0.15


def blink_factor(now):
    """Return eye openness multiplier from scheduled blinks."""
    global next_blink_at, blink_end_at

    if now >= next_blink_at and now >= blink_end_at:
        blink_end_at = now + BLINK_DUR
        next_blink_at = now + random.uniform(4.0, 5.0)

    if now < blink_end_at:
        progress = 1.0 - ((blink_end_at - now) / BLINK_DUR)
        if progress < 0.5:
            return max(0.15, 1.0 - (progress * 1.7))
        return max(0.15, 0.15 + ((progress - 0.5) * 1.7))

    return 1.0


# --- DRAWING HELPERS ---


def lerp(a, b, t):
    return a + (b - a) * t


def speaking_mouth_height(word):
    """Estimate how open the mouth should be based on the word's sounds."""
    cleaned = "".join(ch for ch in word.lower() if ch.isalpha())
    if not cleaned:
        return 20
    vowels = sum(1 for ch in cleaned if ch in "aeiouy")
    base = 14 + min(4, vowels) * 6
    if cleaned.endswith(("m", "p", "b")):
        base -= 8
    return max(10, min(base, 44))


def draw_eye(cx, cy, open_amount, pupil_offset_x=0, pupil_offset_y=0):
    """Draw a clean eye with pupil."""
    eye_w = 54
    eye_h = int(lerp(6, 42, open_amount))
    top = cy - eye_h // 2
    bot = cy + eye_h // 2

    canvas.create_oval(
        cx - eye_w // 2, top, cx + eye_w // 2, bot,
        fill="white", outline="white",
    )

    px = cx + max(-8, min(8, pupil_offset_x))
    py = cy + max(-5, min(5, pupil_offset_y))
    pupil_r = max(4, int(lerp(4, 7, open_amount)))
    canvas.create_oval(
        px - pupil_r, py - pupil_r, px + pupil_r, py + pupil_r,
        fill="black", outline="black",
    )


# --- FACE STATES ---


def draw_face(raw_state):
    canvas.delete("all")

    state = raw_state.strip()
    if ":" in state:
        state = state.split(":", 1)[0]

    cw = max(1, canvas.winfo_width())
    ch = max(1, canvas.winfo_height())
    cx = cw // 2
    cy = ch // 2
    now = time.time()
    blink = blink_factor(now)

    if state == "THINKING":
        # 🤔 look: one eyebrow raised, hand on chin.
        left_open = 0.92 * blink   # wide (raised-brow side)
        right_open = 0.55 * blink  # slightly squinted
        draw_eye(cx - 96, cy - 42, left_open, pupil_offset_x=4, pupil_offset_y=-2)
        draw_eye(cx + 96, cy - 42, right_open, pupil_offset_x=4, pupil_offset_y=-2)
        # Left brow raised high, right brow flat/lowered.
        canvas.create_line(
            cx - 132, cy - 96, cx - 58, cy - 86,
            fill="white", width=6, capstyle=tk.ROUND,
        )
        canvas.create_line(
            cx + 58, cy - 72, cx + 132, cy - 72,
            fill="white", width=6, capstyle=tk.ROUND,
        )
        # Small neutral mouth
        canvas.create_arc(
            cx - 36, cy + 56, cx + 36, cy + 80,
            start=200, extent=140, style=tk.ARC, outline="white", width=5,
        )

    elif state == "SPEAKING":
        left_open = 0.95 * blink
        right_open = 0.95 * blink
        jit = int(2 * math.sin(now * 3.1))
        draw_eye(cx - 96, cy - 44, left_open, pupil_offset_x=jit, pupil_offset_y=0)
        draw_eye(cx + 96, cy - 44, right_open, pupil_offset_x=-jit, pupil_offset_y=0)
        canvas.create_line(
            cx - 132, cy - 86, cx - 58, cy - 92,
            fill="white", width=6, capstyle=tk.ROUND,
        )
        canvas.create_line(
            cx + 58, cy - 92, cx + 132, cy - 86,
            fill="white", width=6, capstyle=tk.ROUND,
        )

        # Clock-based mouth: face.py decides open/closed from real time.
        word, is_open = get_current_mouth(now)

        if is_open and word:
            mouth_h = speaking_mouth_height(word)
            phase_flap = 0.7 + 0.3 * math.sin(now * 5.0)
            mouth_open = max(8, int(mouth_h * phase_flap))
            canvas.create_oval(
                cx - 48, cy + 44 - mouth_open, cx + 48, cy + 44 + mouth_open,
                outline="white", width=4,
            )
            canvas.create_oval(
                cx - 42, cy + 48 - mouth_open, cx + 42, cy + 40 + mouth_open,
                fill="black", outline="black",
            )
            if mouth_open > 14:
                canvas.create_line(
                    cx - 28, cy + 36, cx + 28, cy + 36,
                    fill="white", width=2,
                )
        else:
            # Closed mouth between words.
            canvas.create_line(
                cx - 36, cy + 60, cx + 36, cy + 60,
                fill="white", width=5, capstyle=tk.ROUND,
            )

    else:  # IDLE / OFFLINE / unknown
        left_open = 0.82 * blink
        right_open = 0.82 * blink
        draw_eye(cx - 96, cy - 40, left_open)
        draw_eye(cx + 96, cy - 40, right_open)
        canvas.create_line(
            cx - 130, cy - 76, cx - 62, cy - 76,
            fill="white", width=6, capstyle=tk.ROUND,
        )
        canvas.create_line(
            cx + 62, cy - 76, cx + 130, cy - 76,
            fill="white", width=6, capstyle=tk.ROUND,
        )
        canvas.create_arc(
            cx - 46, cy + 58, cx + 46, cy + 84,
            start=200, extent=140, style=tk.ARC, outline="white", width=6,
        )


# --- MAIN LOOP ---
current_state = ""


def check_state():
    global current_state
    try:
        if os.path.exists("state.txt"):
            with open("state.txt", "r") as f:
                new_state = f.read().strip()
            if new_state:
                current_state = new_state
    except Exception:
        pass

    draw_face(current_state or "IDLE")
    root.after(33, check_state)


draw_face("IDLE")
check_state()
keep_window_visible()
root.mainloop()
