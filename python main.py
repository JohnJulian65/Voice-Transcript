import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import requests
import datetime
import os
import ssl
import logging
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
# 🔁 Function added here
from docx import Document
def txt_to_docx(input_txt_path, output_docx_path):
    doc = Document()
    with open(input_txt_path, "r", encoding="utf-8") as text_file:
        for line in text_file:
            doc.add_paragraph(line.strip())
    doc.save(output_docx_path)
    print(f"✅ Transcription saved to {output_docx_path}")

# Set up logging
logging.basicConfig(
    filename='transcription.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

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

def create_robust_session():
    """Create a requests session with retries for older requests versions"""
    session = requests.Session()
    
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504, 429],
        allowed_methods=["POST"]
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    
    # For corporate environments, you might need this:
    session.verify = True  # Keep SSL verification on
    return session

def transcribe_audio(filename):
    try:
        with open(filename, "rb") as audio_file:
            files = {"file": (filename, audio_file, "audio/wav")}
            data = {
                "model": MODEL,
                "response_format": "json",
                "language": "en"
            }
            session = create_robust_session()
            response = session.post(
                API_ENDPOINT,
                headers=HEADERS,
                files=files,
                data=data,
                timeout=30
            )
            response.raise_for_status()
            json_data = response.json()
            print("API Response:", json_data)
            return json_data.get('text', '')
    except requests.exceptions.SSLError as ssl_err:
        print(f"❌ SSL error occurred: {ssl_err}")
        return "[SSL Error: Transcription failed]"
    except requests.exceptions.RequestException as req_err:
        print(f"❌ Request error occurred: {req_err}")
        return "[Request Error: Transcription failed]"
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return "[Unknown Error: Transcription failed]"

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
            txt_to_docx(LOG_FILE, "output.docx")
            #cleanup(TEMP_AUDIO_FILE)

    except KeyboardInterrupt:
        print("\n❌ Transcription stopped by user.")

if __name__ == "__main__":
    main()
