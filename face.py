import tkinter as tk
import os

root = tk.Tk()
root.attributes('-fullscreen', True)
root.configure(bg='black')
root.config(cursor="none")

# Create a drawing canvas
canvas = tk.Canvas(root, width=480, height=320, bg='black', highlightthickness=0)
canvas.pack(expand=True)

def parse_state(raw_state):
    """Supports payloads like SPEAKING:hello for per-word mouth animation."""
    if ":" in raw_state:
        state, payload = raw_state.split(":", 1)
        return state, payload.strip()
    return raw_state.strip(), ""

def speaking_mouth_height(word):
    """Estimate how open the mouth should be for a spoken word."""
    cleaned = "".join(ch for ch in word.lower() if ch.isalpha())
    if not cleaned:
        return 20
    vowels = sum(1 for ch in cleaned if ch in "aeiouy")
    base = 14 + min(4, vowels) * 6
    if cleaned.endswith(("m", "p", "b")):
        base -= 8
    return max(10, min(base, 44))

def draw_face(raw_state):
    # Clear the screen
    canvas.delete("all")

    state, payload = parse_state(raw_state)

    # Entire screen remains black; only white facial features are drawn.

    if state == "THINKING":
        # Lopsided brow + frown gives a clearer "thinking/skeptical" emotion.
        canvas.create_oval(122, 112, 170, 156, fill="white", outline="white")
        canvas.create_oval(310, 114, 358, 158, fill="white", outline="white")
        canvas.create_line(110, 82, 182, 96, fill="white", width=7, capstyle=tk.ROUND)   # raised left brow
        canvas.create_line(300, 90, 370, 84, fill="white", width=7, capstyle=tk.ROUND)   # flatter right brow
        canvas.create_arc(188, 226, 292, 266, start=35, extent=110, style=tk.ARC, outline="white", width=8)
    elif state == "SPEAKING":
        # Raised brows make speech feel more expressive and energetic.
        canvas.create_oval(118, 106, 172, 154, fill="white", outline="white")
        canvas.create_oval(308, 106, 362, 154, fill="white", outline="white")
        canvas.create_line(108, 84, 182, 76, fill="white", width=7, capstyle=tk.ROUND)
        canvas.create_line(298, 76, 372, 84, fill="white", width=7, capstyle=tk.ROUND)
        mouth_h = speaking_mouth_height(payload)
        canvas.create_oval(190, 245 - mouth_h, 290, 245, fill="white", outline="white")
    else:  # IDLE / OFFLINE / unknown
        canvas.create_oval(118, 110, 172, 158, fill="white", outline="white")
        canvas.create_oval(308, 110, 362, 158, fill="white", outline="white")
        canvas.create_line(110, 92, 180, 92, fill="white", width=7, capstyle=tk.ROUND)
        canvas.create_line(300, 92, 370, 92, fill="white", width=7, capstyle=tk.ROUND)
        canvas.create_rectangle(192, 236, 288, 244, fill="white", outline="white")

# Keep track of the state so we only redraw when it changes
current_state = ""

def check_state():
    global current_state
    try:
        if os.path.exists("state.txt"):
            with open("state.txt", "r") as f:
                new_state = f.read().strip()
                
            # Only redraw if the brain told us to change expressions
            if new_state != current_state:
                draw_face(new_state)
                current_state = new_state
    except:
        pass
    
    # Check the text file every 100 milliseconds
    root.after(100, check_state)

# Start with an Idle face
draw_face("IDLE")
check_state()
root.mainloop()