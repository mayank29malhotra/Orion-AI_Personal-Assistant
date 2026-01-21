"""
Configuration file for Orion AI Personal Assistant
"""
import os
from dotenv import load_dotenv

load_dotenv(override=True)


class Config:
    """Central configuration management"""
    
    # API Keys
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    PUSHOVER_TOKEN = os.getenv("PUSHOVER_TOKEN")
    PUSHOVER_USER = os.getenv("PUSHOVER_USER")
    SERPER_API_KEY = os.getenv("SERPER_API_KEY")
    
    # Email Configuration
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
    IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
    IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
    
    # Google Calendar Configuration
    GOOGLE_CALENDAR_CREDENTIALS = os.getenv("GOOGLE_CALENDAR_CREDENTIALS", "credentials.json")
    GOOGLE_CALENDAR_TOKEN = os.getenv("GOOGLE_CALENDAR_TOKEN", "token.json")
    
    # Directories
    SANDBOX_DIR = os.getenv("SANDBOX_DIR", "sandbox")
    NOTES_DIR = os.getenv("NOTES_DIR", "sandbox/notes")
    TASKS_DIR = os.getenv("TASKS_DIR", "sandbox/tasks")
    SCREENSHOTS_DIR = os.getenv("SCREENSHOTS_DIR", "sandbox/screenshots")
    TEMP_DIR = os.getenv("TEMP_DIR", "sandbox/temp")
    
    # Logging
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "orion.log")
    
    # Rate Limiting
    MAX_REQUESTS_PER_MINUTE = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "60"))
    CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))
    
    # Model Configuration
    WORKER_MODEL = os.getenv("WORKER_MODEL", "llama-3.3-70b-versatile")
    EVALUATOR_MODEL = os.getenv("EVALUATOR_MODEL", "gemini-2.5-flash-lite")
    
    @classmethod
    def ensure_directories(cls):
        """Ensure all required directories exist"""
        directories = [
            cls.SANDBOX_DIR,
            cls.NOTES_DIR,
            cls.TASKS_DIR,
            cls.SCREENSHOTS_DIR,
            cls.TEMP_DIR
        ]
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
