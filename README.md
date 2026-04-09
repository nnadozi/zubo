# Zubo: Embedded AI Desktop Assistant

Zubo is a voice-controlled, hardware-integrated desktop assistant powered by a Raspberry Pi 5. It utilizes local LLMs for private, offline intelligence and a custom GPIO-driven control system for power and volume management.

## 🚀 Features

- **Local Intelligence:** Runs `Ollama` with the `Qwen2.5-0.5b` model for ultra-fast, offline responses.
- **Offline Voice Processing:** Uses `Vosk` for speech-to-text, ensuring no audio leaves the device.
- **Hardware Controls:** Dedicated physical buttons for Power (Start/Stop AI), Volume Up, and Volume Down.
- **Dynamic Face GUI:** A Tkinter-based animated face that reacts to the assistant's state (Idle, Thinking, Speaking).
- **Embedded Audio:** Integrated USB audio management with automated card detection.

## 🛠 Hardware Requirements

- **Processor:** Raspberry Pi 5 (8GB recommended for LLM performance)
- **Display:** 3.5" GPIO LCD Screen
- **Audio:** USB Audio Adapter (Speaker + Microphone)
- **Controls:** 3x Tactile Push Buttons
- **Expansion:** Blue GPIO Breakout Board (JP2 Block)

### GPIO Pin Mapping (JP2 Block)

To ensure stability and prevent electrical interference, Zubo uses an "Isolated Pin" layout:

| Function | GPIO Pin | Physical Pin | Wiring Note |
| :--- | :--- | :--- | :--- |
| **Power Toggle** | GPIO 27 | Pin 13 | High distance from power rails |
| **Volume Up** | GPIO 21 | Pin 40 | Bottom of JP2 block |
| **Volume Down** | GPIO 13 | Pin 33 | Middle of JP2 block |
| **Ground** | GND | Pin 14/20 | Use "skip-row" spacing for safety |



## 📂 Project Structure

```text
zubo/
├── brain_power.py    # Master controller for the Power Button
├── brain.py          # AI Logic: Vosk (Ear) -> Ollama (Brain) -> Piper (Voice)
├── face.py           # Tkinter GUI for animated expressions
├── volume.py         # Independent background service for hardware volume
├── start.sh          # Shell script to launch the AI environment
└── state.txt         # IPC file for sync between brain and face
```

## ⚙️ Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/zubo.git
   cd zubo
   ```

2. **Set up Virtual Environment:**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install vosk ollama sounddevice tkinter
   ```

3. **Install System Dependencies:**
   ```bash
   sudo apt-get install libportaudio2 piper-tts brightnessctl
   ```

4. **Download AI Models:**
   - Download a Vosk model to `~/zubo/model/`.
   - Pull the Ollama model: `ollama pull qwen2.5:0.5b`.

## Interaction
- **Press the Power Button (GPIO 27):** Zubo wakes up and says "Hello!"
- **Talk to Zubo:** The face will change to `THINKING` while processing and `SPEAKING` during output.
- **Adjust Volume:** Use the dedicated physical buttons to control the USB speaker level.

