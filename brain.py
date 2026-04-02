from google import genai
from google.genai import types
import speech_recognition as sr
import subprocess
import os
import wave
from dotenv import load_dotenv  

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

TEXT_MODEL = "gemini-2.5-flash"
TTS_MODEL = "gemini-2.5-flash-preview-tts"

def save_wave_file(filename, pcm_data):
    """Saves raw audio bytes into a playable file."""
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(1)          
        wf.setsampwidth(2)          
        wf.setframerate(24000)      
        wf.writeframes(pcm_data)

def speak(text):
    """Generates the AI voice and plays it through the USB Speaker."""
    print(f"\n🤖 Chikapi: {text}")
    try:
        response = client.models.generate_content(
            model=TTS_MODEL,
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name="Puck")
                    )
                )
            )
        )

        audio_bytes = response.candidates[0].content.parts[0].inline_data.data
        save_wave_file("response.wav", audio_bytes)
        
        # PLAYBACK: Force to Card 3 (USB Speaker)
        subprocess.run(["aplay", "-D", "plughw:3,0", "response.wav"])
    except Exception as e:
        print(f"Voice Error: {e}")

def listen():
    """Records from the auto-detected USB Mic."""
    r = sr.Recognizer()
    r.dynamic_energy_threshold = False
    r.energy_threshold = 300 
    
    try:
        with sr.Microphone(sample_rate=44100) as source:
            print("\n👂 Listening... (Talk now)")
            r.adjust_for_ambient_noise(source, duration=0.2)
            audio = r.listen(source, timeout=3, phrase_time_limit=5)
        
        print("🧠 Thinking...")
        query = r.recognize_google(audio)
        print(f"👤 You: {query}")
        return query
        
    except sr.WaitTimeoutError:
        return None
    except sr.UnknownValueError:
        return None
    except Exception as e:
        print(f"Debug Mic Error: {e}")
        return None

if __name__ == "__main__":
    speak("System rebooted. I am listening.")
    
    while True:
        user_input = listen()
        if user_input:
            if any(word in user_input.lower() for word in ["exit", "stop", "goodbye"]):
                speak("Goodbye!")
                break
                
            try:
                res = client.models.generate_content(model=TEXT_MODEL, contents=user_input)
                speak(res.text)
            except Exception as e:
                print(f"AI Error: {e}")