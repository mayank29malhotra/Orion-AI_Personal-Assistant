"""
Audio/Voice Tools for Orion
Speech-to-text using Groq Whisper API.
"""

import os
import logging
import tempfile
from typing import Optional
from langchain_core.tools import tool

logger = logging.getLogger("Orion")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")


@tool
def transcribe_audio(file_path: str, language: str = "en") -> str:
    """
    Transcribe audio file to text using Whisper.
    
    Args:
        file_path: Path to the audio file (mp3, wav, ogg, m4a, webm)
        language: Language code (default: "en" for English, "hi" for Hindi, etc.)
    """
    if not GROQ_API_KEY:
        return "❌ GROQ_API_KEY not configured."
    
    try:
        import httpx
        
        if not os.path.exists(file_path):
            return f"❌ Audio file not found: {file_path}"
        
        # Read the file
        with open(file_path, 'rb') as f:
            audio_data = f.read()
        
        # Get file extension
        ext = os.path.splitext(file_path)[1].lower()
        content_types = {
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.ogg': 'audio/ogg',
            '.m4a': 'audio/mp4',
            '.webm': 'audio/webm',
            '.oga': 'audio/ogg',
        }
        content_type = content_types.get(ext, 'audio/mpeg')
        
        # Call Groq Whisper API
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        
        files = {
            'file': (os.path.basename(file_path), audio_data, content_type),
            'model': (None, 'whisper-large-v3-turbo'),
            'language': (None, language),
            'response_format': (None, 'text'),
        }
        
        response = httpx.post(
            url,
            headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
            files=files,
            timeout=60
        )
        response.raise_for_status()
        
        transcript = response.text.strip()
        logger.info(f"Audio transcribed: {len(transcript)} chars")
        
        return f"🎤 **Transcription:**\n{transcript}"
        
    except Exception as e:
        error_msg = f"Transcription failed: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}"


async def transcribe_audio_bytes(audio_bytes: bytes, filename: str = "audio.ogg", language: str = "en") -> str:
    """
    Transcribe audio bytes to text using Whisper.
    Used internally by Telegram bot for voice messages.
    
    Args:
        audio_bytes: Raw audio data
        filename: Original filename for extension detection
        language: Language code
    
    Returns:
        Transcribed text
    """
    if not GROQ_API_KEY:
        return "Audio transcription not available - GROQ_API_KEY not set"
    
    try:
        import httpx
        
        # Get content type from extension
        ext = os.path.splitext(filename)[1].lower()
        content_types = {
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.ogg': 'audio/ogg',
            '.oga': 'audio/ogg',
            '.m4a': 'audio/mp4',
            '.webm': 'audio/webm',
        }
        content_type = content_types.get(ext, 'audio/ogg')
        
        # Call Groq Whisper API
        url = "https://api.groq.com/openai/v1/audio/transcriptions"
        
        files = {
            'file': (filename, audio_bytes, content_type),
            'model': (None, 'whisper-large-v3-turbo'),
            'language': (None, language),
            'response_format': (None, 'text'),
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                files=files,
                timeout=60
            )
            response.raise_for_status()
        
        transcript = response.text.strip()
        logger.info(f"Voice message transcribed: {len(transcript)} chars")
        
        return transcript
        
    except Exception as e:
        logger.error(f"Voice transcription failed: {e}")
        return f"[Voice message - transcription failed: {str(e)}]"


# ============ TOOL EXPORTS ============

def get_audio_tools():
    """Get all audio tools."""
    return [
        transcribe_audio,
    ]
