import os
import sys
import glob
import queue
import sounddevice as sd
import vosk
import json
import ollama
import subprocess
import time

# --- FACE COMMUNICATION ---
def set_face(state):
    """Writes the current state to a text file for the separate face app to read."""
    try:
        with open("state.txt", "w") as f:
            f.write(state)
    except Exception as e:
        print(f"Face Error: {e}")

# Set initial state when booting up
set_face("IDLE")

# --- EXISTING AUDIO LOGIC ---
vosk_model = vosk.Model("model")
q = queue.Queue()
HW_RATE = 48000

def find_usb_audio_cards():
    mic_card, spk_card = None, None
    for card_dir in sorted(glob.glob("/sys/class/sound/card[0-9]*")):
        dev_link = os.path.join(card_dir, "device")
        if not os.path.islink(dev_link): continue
        real = os.path.realpath(dev_link)
        card_num = int(os.path.basename(card_dir).replace("card", ""))
        if "xhci-hcd.1" in real: mic_card = card_num
        elif "xhci-hcd.0" in real: spk_card = card_num
    return mic_card, spk_card

def resolve_input_device():
    mic_card, _ = find_usb_audio_cards()
    if mic_card is not None:
        tag = f"hw:{mic_card},"
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] >= 1 and tag in d["name"]: return i
    return sd.default.device[0]

def playback_device():
    _, spk_card = find_usb_audio_cards()
    return f"plughw:{spk_card},0" if spk_card is not None else "default"

def callback(indata, frames, time, status):
    q.put(bytes(indata))

def speak(text):
    set_face("SPEAKING")
    print(f"🤖 Chikapi: {text}")
    model_path = "en_US-lessac-medium.onnx"
    clean_text = text.replace("'", "").replace('"', "")
    adev = playback_device()

    command = f'echo "{clean_text}" | piper --model {model_path} --output_raw | aplay -D {adev} -f S16_LE -r 22050'
    subprocess.run(command, shell=True)

    set_face("IDLE")

def main():
    messages = [{"role": "system", "content": "You are Zubo, a helpful assistant. Short answers."}]
    input_dev = resolve_input_device()

    speak("Hello, Im Zubo. How can I help you?")

    while True:
        try:
            with sd.RawInputStream(samplerate=HW_RATE, blocksize=8000, dtype='int16',
                                   channels=1, callback=callback, device=input_dev):
                rec = vosk.KaldiRecognizer(vosk_model, HW_RATE)
                user_text = ""
                while True:
                    data = q.get()
                    if rec.AcceptWaveform(data):
                        result = json.loads(rec.Result())
                        user_text = result.get("text", "")
                        if user_text: break
        except Exception:
            time.sleep(1)
            continue

        if user_text:
            print(f"👤 You: {user_text}")
            messages.append({"role": "user", "content": user_text})

            set_face("THINKING")
            try:
                response = ollama.chat(model='qwen2.5:0.5b', messages=messages)
                ai_text = response['message']['content']
                messages.append({"role": "assistant", "content": ai_text})
                speak(ai_text)
            except Exception as e:
                print(f"Brain Error: {e}")
                set_face("IDLE")

            while not q.empty():
                try: q.get_nowait()
                except queue.Empty: break

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # Gracefully set the face offline before closing
        set_face("OFFLINE")
        print("\n👋 System Offline.")