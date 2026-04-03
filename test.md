import os
import sys
import queue
import sounddevice as sd
import vosk
import json
import ollama
import subprocess
import time

# 1. SETUP EARS (VOSK)
vosk_model = vosk.Model("model")
q = queue.Queue()

# Match the rate your hardware is currently locked into
HW_RATE = 48000 

def callback(indata, frames, time, status):
    q.put(bytes(indata))

def speak(text):
    """Force sound through Card 2 using a robust shell pipe."""
    print(f"🤖 Chikapi: {text}")
    
    # Clean the text of apostrophes to avoid shell syntax errors
    clean_text = text.replace("'", "")
    
    # Force volume up on Card 2
    os.system("amixer -c 2 sset 'Speaker' 100% > /dev/null 2>&1")
    
    # The Pipe: espeak -> aplay (matching your successful terminal logic)
    command = f"espeak '{clean_text}' --stdout | aplay -D plughw:2,0"
    
    time.sleep(0.3)
    subprocess.run(command, shell=True)

def main():
    messages = [{"role": "system", "content": "You are Chikapi, a helpful coding tutor. Short answers."}]
    
    # Startup Greeting
    speak("Hello, Im zubo. How can I help you?")
    print("🤖 Chikapi: Local System Active on Card 2. Talk to me!")
    
    while True:
        try:
            # We open the mic at 48k to match the hardware lock
            with sd.RawInputStream(samplerate=HW_RATE, blocksize=8000, dtype='int16',
                                   channels=1, callback=callback, device=2):
                
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