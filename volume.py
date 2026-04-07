from gpiozero import Button
import subprocess
import time

# Hardware Setup (JP2 Block)
# The 'bounce_time' tells the Pi to ignore extra clicks for 0.3 seconds
vol_up_btn = Button(21, bounce_time=0.15)
vol_down_btn = Button(13, bounce_time=0.15)

def volume_up():
    print("🔊 Volume UP   [||||||    ] +10%")
    # '-c 0' targets your USB Audio, 'PCM' is the control name
    subprocess.run(["amixer", "-q", "-c", "0", "set", "PCM", "10%+"])

def volume_down():
    print("🔉 Volume DOWN [|||       ] -10%")
    subprocess.run(["amixer", "-q", "-c", "0", "set", "PCM", "10%-"])

# Link buttons to functions
vol_up_btn.when_pressed = volume_up
vol_down_btn.when_pressed = volume_down

print("--- Zubo Volume Control Active ---")
print("Using USB Audio Card 0 -> 'PCM'")
print("Press P21 (Bottom) or P20 (Above)")

try:
    while True:
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\nZubo is signing off...")

# speaker-test -D hw:0,0 -t sine -f 440 -c 2