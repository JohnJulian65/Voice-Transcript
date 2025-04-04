import sounddevice as sd
import numpy as np
import scipy.io.wavfile as wav
import requests
import datetime
import os
import ssl
import logging
import re
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from docx import Document
from docx.shared import Pt
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT

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
STRUCTURED_LOG_FILE = "structured_conversation_log.txt"
TEMP_AUDIO_FILE = "temp_audio.wav"
DURATION = 10  # seconds
SAMPLE_RATE = 16000  # recommended by Groq for optimal performance

HEADERS = {
    "Authorization": f"Bearer {GROQ_API_KEY}"
}

# Known roles and titles that may appear in the hearing
ROLES = [
    "chairman", "chairwoman", "chair", "ranking member", "representative",
    "senator", "ambassador", "mr.", "ms.", "mrs.", "dr.", "secretary", 
    "commissioner", "director", "administrator", "congressman", "congresswoman"
]

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

def identify_speaker(text):
    """Identify the speaker from the transcript text"""
    # Common patterns for speaker identification
    patterns = [
        # Direct identification patterns: "Chairman Smith:" or "Mr. Johnson says"
        r'(?:^|\s)((?:' + '|'.join(ROLES) + r')\s+\w+)(?:\s*:|says|\sstated)',
        # Introduction patterns: "The chair recognizes Representative Smith"
        r'(?:recognized|recognizes|welcomes|introduces|turning to)\s+((?:' + '|'.join(ROLES) + r')\s+\w+)',
        # Simple name mentions that might be speakers
        r'(?:^|\s)(\w+\s+\w+)(?:\s*:)'
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # Return the first match, capitalized appropriately
            speaker = matches[0].strip()
            # Capitalize role words
            for role in ROLES:
                if role in speaker.lower():
                    pattern = re.compile(re.escape(role), re.IGNORECASE)
                    speaker = pattern.sub(role.capitalize(), speaker)
            # Capitalize the name part
            parts = speaker.split()
            if len(parts) > 1:
                speaker = " ".join([parts[0]] + [p.capitalize() for p in parts[1:]])
            return speaker
    
    # Return a default if no speaker is identified
    return "Speaker"

def extract_question_answer(text):
    """Attempt to identify if text is a question or an answer"""
    # Question indicators
    question_patterns = [
        r'\?',
        r'^(?:what|how|why|where|when|is|are|do|does|can|could|would|should|will)',
        r'(?:can you|would you|could you)'
    ]
    
    for pattern in question_patterns:
        if re.search(pattern, text.lower()):
            return "question"
    
    return "answer"

def structure_transcript(text):
    """Structure the transcript into speaker sections"""
    # Try to identify speaker
    speaker = identify_speaker(text)
    q_or_a = extract_question_answer(text)
    
    # Format the speaker header
    if q_or_a == "question" and "Representative" not in speaker and "Chairman" not in speaker and "Member" not in speaker:
        speaker = f"Representative {speaker}"
    
    # Format the transcript
    formatted_text = f"**{speaker}:** {text}"
    
    return formatted_text

def log_transcript(text, logfile):
    """Log the raw transcript to a file"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(logfile, "a", encoding="utf-8") as log:
        log.write(f"[{timestamp}] {text}\n")
    print(f"Transcript logged at {timestamp}")

def log_structured_transcript(text, logfile):
    """Log the structured transcript to a file"""
    with open(logfile, "a", encoding="utf-8") as log:
        log.write(f"{text}\n\n")
    print("Structured transcript logged")

def create_structured_docx(input_txt_path, output_docx_path):
    """Create a structured Word document from the text file"""
    doc = Document()
    
    # Set the document style
    style = doc.styles['Normal']
    font = style.font
    font.name = 'Calibri'
    font.size = Pt(11)
    
    # Read the structured transcript
    with open(input_txt_path, "r", encoding="utf-8") as text_file:
        content = text_file.read()
    
    # Split by double newlines to separate speaker sections
    sections = content.split("\n\n")
    
    for section in sections:
        if not section.strip():
            continue
            
        paragraph = doc.add_paragraph()
        
        # Check if this is a speaker header
        speaker_match = re.search(r'^\*\*(.+?):\*\*', section)
        if speaker_match:
            # Split into speaker and text
            speaker_text = re.split(r'^\*\*(.+?):\*\*\s*', section, 1)
            if len(speaker_text) > 2:
                speaker = speaker_text[1]
                text = speaker_text[2]
                
                # Add speaker with bold formatting
                speaker_run = paragraph.add_run(f"{speaker}: ")
                speaker_run.bold = True
                
                # Add the rest of the text
                paragraph.add_run(text)
        else:
            # If no speaker format is found, just add the text
            paragraph.add_run(section)
    
    doc.save(output_docx_path)
    print(f"✅ Structured transcript saved to {output_docx_path}")

def cleanup(filename):
    """Remove temporary files"""
    if os.path.exists(filename):
        os.remove(filename)
        print(f"Cleaned up {filename}")

def main():
    print("🚀 Starting continuous transcription with structure recognition. Press Ctrl+C to stop.")
    
    # Initialize or clear the structured log file
    with open(STRUCTURED_LOG_FILE, "w", encoding="utf-8") as f:
        f.write("")
    
    try:
        while True:
            audio_data = record_audio(DURATION, SAMPLE_RATE)
            save_audio(audio_data, SAMPLE_RATE, TEMP_AUDIO_FILE)

            # Get raw transcript
            transcript = transcribe_audio(TEMP_AUDIO_FILE)
            
            # Log raw transcript (for backup)
            log_transcript(transcript, LOG_FILE)
            
            # Structure the transcript
            structured_transcript = structure_transcript(transcript)
            
            # Log structured transcript
            log_structured_transcript(structured_transcript, STRUCTURED_LOG_FILE)
            
            # Create structured Word document
            create_structured_docx(STRUCTURED_LOG_FILE, "structured_output.docx")
            
            # Optional: Clean up temporary audio file
            #cleanup(TEMP_AUDIO_FILE)

    except KeyboardInterrupt:
        print("\n❌ Transcription stopped by user.")

if __name__ == "__main__":
    main()
