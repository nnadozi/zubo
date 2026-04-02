# 🤖 Zubo: AI Desktop Assisstant
**Platform**: Raspberry Pi 5 (8GB)
**OS**: Debian Bookworm (6.12.75+rpt)
**Environment**: Python 3.11+ with `venv`

## 🛠 Hardware Configuration (Verified)
* **Microphone**: USB PnP Gooseneck Mic
    * **ALSA Address**: `hw:2,0`
    * **Settings**: Mono, 16-bit LE, 44100Hz
* **Speaker**: USB UACDemoV1.0
    * **ALSA Address**: `hw:3,0`
* **Camera**: Arducam OV5647 (5MP)
    * **Connection**: 22-pin to 15-pin adapter
    * **Driver**: `dtoverlay=ov5647` (Manual override in `config.txt`)
* **Display**: I2C LED Screen (Pending wiring)

## 📁 System Files
**`/etc/asound.conf`** is configured to map `pcm.!default` to:
* **Capture**: `mic` (plugged to `hw:2,0`)
* **Playback**: `speaker` (plugged to `hw:3,0`)

---

## 🎯 Copilot Instructions (The "Prompt")
*Use the following prompt when you start chatting with Copilot in VS Code:*

> "I am building **Zubo**, an AI desktop assistant. I am using a Raspberry Pi 5. My audio is already configured at the system level (`asound.conf`). 
> 
> **Goal 1**: Create a `voice.py` script that uses `SpeechRecognition` to record audio from the default mic, saves it as a `.wav`, and then uses `google-generativeai` (Gemini API) to get a text response.
> 
> **Goal 2**: Use `espeak` via the `subprocess` library to play the AI's response through the USB speaker.
> 
> **Goal 3**: Ensure all code uses the python interpreter in my `./venv/` folder."

