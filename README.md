
# Realtime Subtitles

**Realtime Subtitles** is a Python-based script that captures system audio in real-time, transcribes it using OpenAI Whisper, and optionally translates the transcribed text. The subtitles are displayed in an overlay window on your desktop.

## Features

- Captures system audio using loopback devices.
- Transcribes audio in real-time using OpenAI Whisper.
- Supports optional translations using Google Translate or DeepL.
- Customizable subtitle overlay with font, color, size, and transparency options.

## How It Works

1. Captures system audio using Python libraries (`soundcard` and `sounddevice`).
2. Sends audio chunks to an OpenAI Whisper API running in a Docker container.
3. Displays the transcription as subtitles in a transparent overlay window.
4. Optionally translates the transcription using Google Translate or DeepL.

## Requirements

- Python 3.8+
- NVIDIA GPU for running Whisper API (optional for GPU acceleration)
- Docker (for hosting the Whisper API)

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/<your_username>/realtime_subtitles.git
   cd realtime_subtitles
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up and run the Whisper API:
   - Install Docker if not already installed.
   - Create and start the Whisper service:
     ```bash
     docker-compose up -d
     ```

4. Run the script:
   ```bash
   python main.py
   ```

## Configuration

The `config.json` file allows you to customize the following:

- `font_name`: Font used for subtitles (default: `Comic Sans MS`).
- `font_size`: Font size (default: 24).
- `font_color`: Subtitle text color (default: `yellow`).
- `translation`: Enable/disable translation (default: `False`).
- `deepl_api`: API key for DeepL translation (if enabled).
- `language`: Target language for translation (default: `english`).
- `audio_threshold`: Minimum audio level to trigger transcription (default: `0.01`).
- `text_expiry`: Time in seconds before the subtitles fade (default: `3.0`).
- `window_opacity`: Transparency of the subtitle window (default: `0.8`).

## Docker Compose

The `docker-compose.yml` file is included for setting up the Whisper transcription service with GPU support. It uses the `onerahmet/openai-whisper-asr-webservice` Docker image.

## Dependencies

The following Python libraries are required:
- `soundcard`
- `sounddevice`
- `numpy`
- `wave`
- `requests`
- `googletrans==4.0.0rc1`
- `deepl`
- `langdetect`
- `tkinter`

## Contributing

Feel free to fork the repository and make your own changes! Contributions are always welcome.

## Disclaimer

This is my shot at this and migth not work perfectly, i invite you to make pull requests and contribute to make this better.
(I am kind of a beginner and i was not able to fix that the sometimes it skips audio)

## License

MIT License
