import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import requests
import datetime
import time
import os

# Configuration
GROQ_API_KEY = "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"
API_ENDPOINT = "https://api.groq.com/openai/v1/audio/transcriptions"
MODEL = "whisper-large-v3-turbo"
LOG_FILE = "conversation_log.txt"
TEMP_AUDIO_FILE = "temp_audio.wav"
DURATION = 30  # seconds
SAMPLE_RATE = 16000  # recommended by Groq for optimal performance

HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}"
}

def record_audio(duration, sample_rate):
    print(f"Recording audio for {duration} seconds...")
    audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype='int16', device=1)
    sd.wait()
    return audio

def save_audio(audio_data, sample_rate, filename):
    wav.write(filename, sample_rate, audio_data)
    print(f"Audio segment saved as {filename}")

def transcribe_audio(filename):
    with open(filename, "rb") as audio_file:
        files = {"file": (filename, audio_file, "audio/wav")}
        data = {
            "model": MODEL,
            "response_format": "json",
            "language": "en"  # Change or remove if multilingual
        }
        response = requests.post(API_ENDPOINT, headers=HEADERS, files=files, data=data)
        
        if response.status_code == 200:  # Make sure this line is indented with spaces, not a tab
            print("API Response:", response.json())  # This will print the full API response in PowerShell
            return response.json().get('text', '')
        else:
            print("API Error:", response.text)
            return "[Error in transcription]"

def log_transcript(text, logfile):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(logfile, "a", encoding="utf-8") as log:
        log.write(f"[{timestamp}] {text}\n")
    print(f"Transcript logged at {timestamp}")

def cleanup(filename):
    if os.path.exists(filename):
        os.remove(filename)
        print(f"Cleaned up {filename}")

def main():
    print("🚀 Starting continuous transcription. Press Ctrl+C to stop.")
    try:
        while True:
            audio_data = record_audio(DURATION, SAMPLE_RATE)
            save_audio(audio_data, SAMPLE_RATE, TEMP_AUDIO_FILE)

            transcript = transcribe_audio(TEMP_AUDIO_FILE)
            log_transcript(transcript, LOG_FILE)

            #cleanup(TEMP_AUDIO_FILE)

    except KeyboardInterrupt:
        print("\n❌ Transcription stopped by user.")

if __name__ == "__main__":
    main()
