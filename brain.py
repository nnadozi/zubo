import os
import sys
import glob
import queue
import re
import shutil
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

def resolve_output_device():
    """Resolve a sounddevice output index that prefers the USB speaker card."""
    _, spk_card = find_usb_audio_cards()
    if spk_card is not None:
        tag = f"hw:{spk_card},"
        for i, d in enumerate(sd.query_devices()):
            if d["max_output_channels"] >= 1 and tag in d["name"]:
                return i
    return sd.default.device[1]

def callback(indata, frames, time, status):
    q.put(bytes(indata))


# --- LLM PERFORMANCE TUNING ---
# Keep these configurable via environment variables so we can tune speed
# on-device without changing code again.
MODEL_NAME = os.getenv("ZUBO_MODEL", "qwen2.5:0.5b")
MAX_HISTORY_TURNS = int(os.getenv("ZUBO_HISTORY_TURNS", "4"))
LLM_KEEP_ALIVE = os.getenv("ZUBO_LLM_KEEP_ALIVE", "30m")
# Brief closed-mouth gap between words to make speech animation read clearly.
MOUTH_WORD_GAP_MS = int(os.getenv("ZUBO_MOUTH_WORD_GAP_MS", "40"))
# Compensates for audio buffer + USB speaker latency so mouth animation
# doesn't start before sound is actually audible.
AUDIO_LATENCY_MS = int(os.getenv("ZUBO_AUDIO_LATENCY_MS", "1000"))


def llm_options():
    cpu_threads = os.cpu_count() or 4
    return {
        # Smaller context windows are much faster on Raspberry Pi hardware.
        "num_ctx": int(os.getenv("ZUBO_NUM_CTX", "1024")),
        # Keep responses short by default to reduce generation latency.
        "num_predict": int(os.getenv("ZUBO_NUM_PREDICT", "64")),
        # Use all available CPU threads unless overridden.
        "num_thread": int(os.getenv("ZUBO_NUM_THREAD", str(cpu_threads))),
        # Slightly lower temperature can reduce rambling output.
        "temperature": float(os.getenv("ZUBO_TEMPERATURE", "0.3")),
    }


def trim_history(messages, max_turns):
    """Keep system prompt + last N user/assistant turns for speed."""
    if len(messages) <= 1:
        return messages
    if max_turns <= 0:
        return messages[:1]
    keep_items = max_turns * 2
    return [messages[0]] + messages[-keep_items:]


def resolve_piper_exe():
    """Use venv/bin/piper next to this file; subprocess often lacks activated PATH."""
    base = os.path.dirname(os.path.abspath(__file__))
    venv_piper = os.path.join(base, "venv", "bin", "piper")
    if os.path.isfile(venv_piper):
        return venv_piper
    return shutil.which("piper")


def speak_espeak_fallback(text):
    """Last-resort TTS when piper is missing (no per-word mouth sync)."""
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe or not text.strip():
        if not exe:
            print("TTS: install piper (`pip install piper-tts`) or espeak-ng.")
        set_face("IDLE")
        return
    set_face("SPEAKING")
    try:
        subprocess.run([exe, text], check=False)
    finally:
        set_face("IDLE")


def speak(text):
    # Drive mouth updates from the real playback timeline for tighter sync.
    print(f"🤖 Chikapi: {text}")
    model_path = "en_US-lessac-medium.onnx"
    clean_text = text.replace("'", "").replace('"', "")
    if not clean_text.strip():
        set_face("IDLE")
        return

    piper_exe = resolve_piper_exe()
    if not piper_exe:
        speak_espeak_fallback(clean_text)
        return

    try:
        # First, synthesize the full utterance so we can map words across audio duration.
        tts = subprocess.run(
            [piper_exe, "--model", model_path, "--output_raw"],
            input=clean_text.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        audio_bytes = tts.stdout
        if not audio_bytes:
            set_face("IDLE")
            return

        sample_rate = 22050
        total_samples = len(audio_bytes) // 2  # int16 mono
        total_duration = total_samples / sample_rate

        words = [w for w in clean_text.split() if w]
        if not words:
            set_face("IDLE")
            return

        # Build proportional word timings, weighted by letters and punctuation.
        weights = []
        for w in words:
            letters = re.sub(r"[^A-Za-z0-9]", "", w)
            weight = max(1.0, len(letters))
            if w.endswith((",", ";", ":")):
                weight += 1.5
            if w.endswith((".", "!", "?")):
                weight += 2.5
            weights.append(weight)

        total_weight = sum(weights)

        # Build word intervals with small gaps so the mouth visibly closes
        # between words, making it look like real speech.
        gap_s = max(0.0, MOUTH_WORD_GAP_MS / 1000.0)
        if len(words) > 1 and gap_s > 0.0:
            max_total_gap = total_duration * 0.22
            gap_s = min(gap_s, max_total_gap / (len(words) - 1))
        else:
            gap_s = 0.0

        speech_budget = total_duration - gap_s * max(0, len(words) - 1)
        if speech_budget <= 0:
            speech_budget = total_duration
            gap_s = 0.0

        intervals = []
        cursor = 0.0
        for i, (word, weight) in enumerate(zip(words, weights)):
            dur = (weight / total_weight) * speech_budget
            intervals.append({"word": word, "start": cursor, "end": cursor + dur})
            cursor += dur
            if i < len(words) - 1:
                cursor += gap_s

        # Write timing data before playback starts. Add audio latency offset
        # so face.py waits until sound is actually audible from the speaker.
        playback_start = time.time() + (AUDIO_LATENCY_MS / 1000.0)
        mouth_data = json.dumps({
            "start_time": playback_start,
            "duration": total_duration,
            "intervals": intervals,
        })
        try:
            with open("mouth.json", "w") as mf:
                mf.write(mouth_data)
        except Exception:
            pass

        set_face("SPEAKING")

        out_dev = resolve_output_device()
        chunk_samples = 1024
        chunk_bytes = chunk_samples * 2

        with sd.RawOutputStream(
            samplerate=sample_rate,
            blocksize=chunk_samples,
            dtype="int16",
            channels=1,
            device=out_dev,
        ) as stream:
            byte_pos = 0
            while byte_pos < len(audio_bytes):
                chunk = audio_bytes[byte_pos:byte_pos + chunk_bytes]
                if not chunk:
                    break
                stream.write(chunk)
                byte_pos += len(chunk)

        set_face("IDLE")
    except Exception as e:
        print(f"TTS Sync Error: {e}")
        # Pipe raw PCM to aplay (no shell) if sounddevice path fails.
        set_face("SPEAKING")
        adev = playback_device()
        try:
            synth = subprocess.Popen(
                [piper_exe, "--model", model_path, "--output_raw"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            out, _ = synth.communicate(input=clean_text.encode("utf-8"), timeout=120)
            if synth.returncode == 0 and out:
                subprocess.run(
                    [
                        "aplay",
                        "-D",
                        adev,
                        "-f",
                        "S16_LE",
                        "-r",
                        "22050",
                        "-c",
                        "1",
                        "-t",
                        "raw",
                    ],
                    input=out,
                    check=False,
                )
            else:
                speak_espeak_fallback(clean_text)
        except Exception as e2:
            print(f"TTS aplay fallback: {e2}")
            speak_espeak_fallback(clean_text)
        set_face("IDLE")

def main():
    messages = [
        {
            "role": "system",
            "content": "You are Zubo, a helpful assistant. Keep answers short and direct.",
        }
    ]
    input_dev = resolve_input_device()

    # Warm the model once at startup so first real question feels snappier.
    try:
        ollama.chat(
            model=MODEL_NAME,
            messages=messages,
            options=llm_options(),
            keep_alive=LLM_KEEP_ALIVE,
        )
    except Exception as warm_err:
        print(f"LLM warmup skipped: {warm_err}")

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
            messages = trim_history(messages, MAX_HISTORY_TURNS)

            set_face("THINKING")
            try:
                t0 = time.perf_counter()
                response = ollama.chat(
                    model=MODEL_NAME,
                    messages=messages,
                    options=llm_options(),
                    keep_alive=LLM_KEEP_ALIVE,
                )
                elapsed = time.perf_counter() - t0
                print(f"LLM latency: {elapsed:.2f}s")
                ai_text = response['message']['content']
                messages.append({"role": "assistant", "content": ai_text})
                messages = trim_history(messages, MAX_HISTORY_TURNS)
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