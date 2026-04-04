import tkinter as tk
import os

root = tk.Tk()
root.attributes('-fullscreen', True)
root.configure(bg='black')
root.config(cursor="none")

# Create a drawing canvas
canvas = tk.Canvas(root, width=480, height=320, bg='black', highlightthickness=0)
canvas.pack(expand=True)

def draw_face(state):
    # Clear the screen
    canvas.delete("all")
    
    # Draw Eyes
    if state == "THINKING":
        canvas.create_oval(100, 90, 160, 150, fill="cyan")
        canvas.create_oval(320, 110, 380, 170, fill="cyan")
    else:
        canvas.create_rectangle(100, 100, 160, 160, fill="cyan")
        canvas.create_rectangle(320, 100, 380, 160, fill="cyan")
        
    # Draw Mouth
    if state == "SPEAKING":
        canvas.create_rectangle(180, 220, 300, 270, fill="pink")
    elif state == "THINKING":
        canvas.create_oval(220, 230, 260, 270, outline="pink", width=8)
    else: # IDLE
        canvas.create_rectangle(180, 240, 300, 250, fill="pink")

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