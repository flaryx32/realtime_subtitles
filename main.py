import soundcard as sc
import sounddevice as sd
import numpy as np
import wave
import threading
import queue
import requests
import time
from datetime import datetime
import os
import json
import tkinter as tk
import warnings
from typing import Optional
from googletrans import Translator
import deepl
from langdetect import detect

# Custom warning handler to suppress specific warnings
warnings.filterwarnings("ignore", category=sc.mediafoundation.SoundcardRuntimeWarning)

DEFAULT_CONFIG = {
    "font_name": "Comic Sans MS",
    "font_size": 24,
    "font_color": "yellow",
    "translation": False,
    "deepl_api": "",
    "language": "english",
    "audio_threshold": 0.01,  # Minimum audio level to trigger processing
    "text_expiry": 3.0,      # How long to show text before fading
    "window_opacity": 0.8    # Window transparency
}

class ConfigManager:
    def __init__(self):
        self.config_file = "config.json"
        self.config = self.load_config()
    
    def load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults for any missing keys
                    return {**DEFAULT_CONFIG, **config}
            else:
                # Create default config if doesn't exist
                with open(self.config_file, 'w') as f:
                    json.dump(DEFAULT_CONFIG, f, indent=4)
                return DEFAULT_CONFIG
        except Exception as e:
            print(f"Error loading config: {e}")
            return DEFAULT_CONFIG

class SubtitleOverlay(tk.Tk):
    def __init__(self, config):
        super().__init__()
        self.config = config

        # Make window transparent
        self.attributes('-alpha', self.config['window_opacity'])
        self.attributes('-topmost', True)
        
        # Remove window decorations
        self.overrideredirect(True)
        
        # Set window size to screen size
        self.screen_width = self.winfo_screenwidth()
        self.screen_height = self.winfo_screenheight()
        self.geometry(f'{self.screen_width}x{self.screen_height}')
        
        # Make window click-through
        self.attributes('-transparentcolor', 'black')
        self.configure(bg='black')
        
        # Create label for subtitles
        self.subtitle_label = tk.Label(
            self,
            text="",
            font=(self.config['font_name'], self.config['font_size'], 'bold italic'),
            fg=self.config['font_color'],
            bg='black',
            wraplength=self.screen_width * 0.8
        )
        self.subtitle_label.place(
            relx=0.5,
            rely=0.8,
            anchor='center'
        )
        
    def update_text(self, text: str):
        self.subtitle_label.config(text=text)

# Previous imports remain the same...

class TranslationManager:
    def __init__(self, config):
        self.config = config
        self.google_translator = Translator()
        self.deepl_translator = None
        self.language_map = {
            "english": "EN-US",
            "spanish": "ES",
            "french": "FR",
            "german": "DE",
            "italian": "IT",
            "portuguese": "PT-PT",
            "dutch": "NL",
            "polish": "PL",
            "russian": "RU",
            "japanese": "JA",
            "chinese": "ZH",
            "korean": "KO"
        }
        
        if config['translation'] and config['deepl_api']:
            try:
                self.deepl_translator = deepl.Translator(config['deepl_api'])
            except Exception as e:
                print(f"Error initializing DeepL: {e}")

    def get_target_language_code(self):
        """Convert config language to proper DeepL/Google language code"""
        target_lang = self.config['language'].lower()
        return self.language_map.get(target_lang, "EN-US")

    def translate(self, text: str) -> str:
        """Translate text if needed, return original text if translation fails or isn't needed"""
        if not self.config['translation']:
            return text
            
        try:
            # Detect source language
            source_lang = detect(text)
            target_code = self.get_target_language_code()
            
            # Don't translate if already in English and target is English
            if source_lang == 'en' and target_code.startswith('EN'):
                return text
            
            if self.deepl_translator and self.config['deepl_api']:
                # Use DeepL
                try:
                    result = self.deepl_translator.translate_text(
                        text,
                        target_lang=target_code
                    )
                    return result.text
                except Exception as e:
                    print(f"DeepL translation error: {e}")
                    # Fallback to Google Translate
                    return self._google_translate(text, target_code)
            else:
                return self._google_translate(text, target_code)
                
        except Exception as e:
            print(f"Translation error: {e}")
            return text  # Return original text if translation fails
            
    def _google_translate(self, text: str, target_code: str) -> str:
        """Fallback Google translation"""
        try:
            # Convert DeepL style codes to Google style
            google_code = target_code.split('-')[0].lower()
            result = self.google_translator.translate(
                text,
                dest=google_code
            )
            return result.text
        except Exception as e:
            print(f"Google translation error: {e}")
            return text

class SystemAudioTranscriber:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.config = self.config_manager.config
        
        self.sample_rate = 16000
        self.chunk_duration = 2
        self.chunk_size = int(self.sample_rate * self.chunk_duration)
        self.audio_queue = queue.Queue()
        self.whisper_url = "http://localhost:9000/asr"
        self.is_running = False
        
        # Initialize translation manager
        self.translator = TranslationManager(self.config)
        
        # Initialize the subtitle overlay
        self.overlay = SubtitleOverlay(self.config)
        
        try:
            # Get system audio devices
            self.mics = sc.all_microphones(include_loopback=True)
            self.default_speaker = sc.default_speaker()
            self.recording_device = self.mics[1]
            
            print("Available recording devices:")
            for i, mic in enumerate(self.mics):
                print(f"{i}: {mic.name}")
            print(f"\nUsing recording device: {self.recording_device.name}")
            
        except Exception as e:
            print(f"Error initializing audio devices: {e}")
            raise
        
        self.output_dir = "audio_chunks"
        os.makedirs(self.output_dir, exist_ok=True)
        
        self.recent_text = ""
        self.last_update = time.time()

    def is_audio_above_threshold(self, audio_data):
        """Check if audio level is above threshold"""
        return np.abs(audio_data).mean() > self.config['audio_threshold']

    def update_gui(self):
        """Update the GUI if it's still running"""
        if self.is_running:
            if time.time() - self.last_update > self.config['text_expiry']:
                self.recent_text = ""
                self.overlay.update_text("")
            self.overlay.after(100, self.update_gui)

    def capture_audio(self):
        """Continuously capture system audio"""
        while self.is_running:
            try:
                with self.recording_device.recorder(samplerate=self.sample_rate) as mic:
                    while self.is_running:
                        try:
                            data = mic.record(numframes=self.chunk_size)
                            if len(data.shape) > 1:
                                data = np.mean(data, axis=1)
                            
                            # Only process if audio is above threshold
                            if self.is_audio_above_threshold(data):
                                data = (data * 32767).astype(np.int16)
                                self.audio_queue.put(data)
                            
                        except Exception as e:
                            print(f"Error during recording: {e}")
                            time.sleep(0.1)
            except Exception as e:
                print(f"Error with recording device: {e}")
                time.sleep(1)

    def process_audio_queue(self):
        while self.is_running:
            try:
                audio_data = self.audio_queue.get(timeout=1)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                filename = f"{self.output_dir}/chunk_{timestamp}.wav"
                
                try:
                    with wave.open(filename, 'wb') as wf:
                        wf.setnchannels(1)
                        wf.setsampwidth(2)
                        wf.setframerate(self.sample_rate)
                        wf.writeframes(audio_data.tobytes())

                    with open(filename, 'rb') as audio_file:
                        files = {'audio_file': ('audio.wav', audio_file, 'audio/wav')}
                        params = {
                            'task': 'transcribe',
                            'output': 'json',
                            'encode': True,
                            'word_timestamps': False
                        }
                        
                        response = requests.post(
                            self.whisper_url,
                            files=files,
                            params=params,
                            timeout=5
                        )
                        
                        if response.status_code == 200:
                            try:
                                result = json.loads(response.content)
                                text = result.get('text', '').strip()
                                if text:
                                    # Always show original text first
                                    self.recent_text = text
                                    self.last_update = time.time()
                                    self.overlay.update_text(text)
                                    
                                    # Then attempt translation if needed
                                    if self.config['translation']:
                                        translated_text = self.translator.translate(text)
                                        if translated_text != text:  # Only update if translation is different
                                            self.recent_text = translated_text
                                            self.last_update = time.time()
                                            self.overlay.update_text(translated_text)
                                    
                                    print(f"Transcription: {self.recent_text}")
                                    
                            except json.JSONDecodeError as e:
                                print(f"Error parsing JSON response: {e}")
                        
                except requests.exceptions.RequestException as e:
                    print(f"Request error: {e}")
                except Exception as e:
                    print(f"Error processing audio chunk: {e}")
                finally:
                    if os.path.exists(filename):
                        try:
                            os.remove(filename)
                        except Exception as e:
                            print(f"Error removing temporary file: {e}")
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in audio processing loop: {e}")

    def start(self):
        try:
            self.is_running = True
            
            self.capture_thread = threading.Thread(target=self.capture_audio)
            self.capture_thread.daemon = True
            self.capture_thread.start()
            
            self.process_thread = threading.Thread(target=self.process_audio_queue)
            self.process_thread.daemon = True
            self.process_thread.start()
            
            print("Started system audio capture. Press Ctrl+C to stop.")
            
            self.update_gui()
            self.overlay.mainloop()
            
        except Exception as e:
            print(f"Error starting audio capture: {e}")
            self.stop()

    def stop(self):
        self.is_running = False
        if hasattr(self, 'capture_thread'):
            self.capture_thread.join()
        if hasattr(self, 'process_thread'):
            self.process_thread.join()
        self.overlay.destroy()
        print("Stopped audio capture and processing.")

if __name__ == "__main__":
    transcriber = SystemAudioTranscriber()
    try:
        transcriber.start()
    except KeyboardInterrupt:
        transcriber.stop()
