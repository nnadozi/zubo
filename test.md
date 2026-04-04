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

vosk_model = vosk.Model("model")
q = queue.Queue()

HW_RATE = 48000

# RPi 5 blue USB 3.0 ports map to two xHCI controllers:
#   Top port  → xhci-hcd.1 → mic (input)
#   Bottom port → xhci-hcd.0 → speaker (output)
# ALSA card numbers can shift across reboots, so we resolve by physical port.

def find_usb_audio_cards():
    """Return (mic_alsa_card, speaker_alsa_card) by matching physical USB port paths."""
    mic_card = None
    spk_card = None

    for card_dir in sorted(glob.glob("/sys/class/sound/card[0-9]*")):
        dev_link = os.path.join(card_dir, "device")
        if not os.path.islink(dev_link):
            continue
        real = os.path.realpath(dev_link)
        card_num = int(os.path.basename(card_dir).replace("card", ""))
        if "xhci-hcd.1" in real:   # top blue port → mic
            mic_card = card_num
        elif "xhci-hcd.0" in real: # bottom blue port → speaker
            spk_card = card_num

    return mic_card, spk_card


def resolve_input_device():
    """PortAudio index matching the mic's ALSA card (top blue USB port)."""
    override = os.environ.get("ZUBO_INPUT_DEVICE")
    if override is not None:
        return int(override)

    mic_card, _ = find_usb_audio_cards()
    if mic_card is not None:
        # ALSA hw name looks like "hw:N,0" inside PortAudio device names
        tag = f"hw:{mic_card},"
        for i, d in enumerate(sd.query_devices()):
            if d["max_input_channels"] >= 1 and tag in d["name"]:
                return i

    # Fallback: first USB-ish capture device
    for i, d in enumerate(sd.query_devices()):
        if d["max_input_channels"] < 1:
            continue
        if any(k in d["name"].lower() for k in ("usb", "mic", "pnp")):
            return i
    return sd.default.device[0]


def playback_device():
    """ALSA device string for aplay, resolved from the bottom blue USB port."""
    override = os.environ.get("ZUBO_APLAY_DEVICE")
    if override:
        return override

    _, spk_card = find_usb_audio_cards()
    if spk_card is not None:
        return f"plughw:{spk_card},0"

    return "default"


def callback(indata, frames, time, status):
    q.put(bytes(indata))

def speak(text):
    """Uses Piper for TTS, piped to aplay on the configured playback device."""
    print(f"🤖 Chikapi: {text}")

    model_path = "en_US-lessac-medium.onnx"
    
    clean_text = text.replace("'", "").replace('"', "")
    
    adev = playback_device()
    command = f'echo "{clean_text}" | piper --model {model_path} --output_raw | aplay -D {adev} -f S16_LE -r 22050'
    
    # Optional: set speaker volume on the same logical card as playback (override with ZUBO_AMIXER_CARD).
    mixer = os.environ.get("ZUBO_AMIXER_CARD", "default")
    os.system(f"amixer -D {mixer} sset 'Speaker' 100% > /dev/null 2>&1")
    
    time.sleep(0.3)
    subprocess.run(command, shell=True)

def main():
    messages = [{"role": "system", "content": "You are Zubo, a helpful assistant. Short answers."}]
    
    input_dev = resolve_input_device()
    in_info = sd.query_devices(input_dev)
    # Startup Greeting
    speak("Hello, Im Zubo. How can I help you?")
    print(
        f"🤖 Zubo: Listening on device {input_dev} ({in_info['name']}). "
        f"Playback: {playback_device()}. Talk to me!"
    )
    
    while True:
        try:
            # We open the mic at 48k to match the hardware lock
            with sd.RawInputStream(samplerate=HW_RATE, blocksize=8000, dtype='int16',
                                   channels=1, callback=callback, device=input_dev):
                
                # Vosk handles the 48k stream internally
                rec = vosk.KaldiRecognizer(vosk_model, HW_RATE)
                user_text = ""
                
                while True:
                    data = q.get()
                    if rec.AcceptWaveform(data):
                        result = json.loads(rec.Result())
                        user_text = result.get("text", "")
                        if user_text:
                            break 
        except Exception as e:
            print(f"❌ Mic Error: {e}")
            time.sleep(1)
            continue
            
        if user_text:
            print(f"👤 You: {user_text}")
            messages.append({"role": "user", "content": user_text})
            
            print("🧠 Thinking...")
            try:
                response = ollama.chat(model='qwen2.5:0.5b', messages=messages)
                ai_text = response['message']['content']
                messages.append({"role": "assistant", "content": ai_text})
                
                speak(ai_text)
                
            except Exception as e:
                print(f"Brain Error: {e}")
            
            while not q.empty():
                try: q.get_nowait()
                except: break

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 System Offline.")