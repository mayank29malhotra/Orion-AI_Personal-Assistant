"""
Configuration file for Orion AI Personal Assistant
Centralized configuration management with environment variable support.
"""
import os
from dotenv import load_dotenv

load_dotenv(override=True)

# HuggingFace Spaces detection
IS_HF_SPACE = os.path.exists("/data") or os.getenv("SPACE_ID")
HF_DATA_DIR = os.getenv("ORION_DATA_DIR", "/data" if IS_HF_SPACE else "")


class Config:
    """Central configuration management"""
    
    # ============ HuggingFace Spaces ============
    IS_HF_SPACE = IS_HF_SPACE
    
    # ============ API Keys ============
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    NTFY_TOPIC = os.getenv("NTFY_TOPIC")
    SERPER_API_KEY = os.getenv("SERPER_API_KEY")
    
    # ============ Email Configuration ============
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
    IMAP_SERVER = os.getenv("IMAP_SERVER", "imap.gmail.com")
    IMAP_PORT = int(os.getenv("IMAP_PORT", "993"))
    
    # ============ Google Calendar Configuration ============
    GOOGLE_CALENDAR_CREDENTIALS = os.getenv("GOOGLE_CALENDAR_CREDENTIALS", "credentials.json")
    GOOGLE_CALENDAR_TOKEN = os.getenv("GOOGLE_CALENDAR_TOKEN", "token.json")
    
    # ============ Directories (HF-aware) ============
    _base = f"{HF_DATA_DIR}/sandbox" if IS_HF_SPACE else "sandbox"
    SANDBOX_DIR = os.getenv("SANDBOX_DIR", _base)
    NOTES_DIR = os.getenv("NOTES_DIR", f"{_base}/notes")
    TASKS_DIR = os.getenv("TASKS_DIR", f"{_base}/tasks")
    SCREENSHOTS_DIR = os.getenv("SCREENSHOTS_DIR", f"{_base}/screenshots")
    TEMP_DIR = os.getenv("TEMP_DIR", f"{_base}/temp")
    PERSISTENT_DIR = os.getenv("PERSISTENT_DIR", f"{_base}/data")
    
    # ============ Logging ============
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "orion.log")
    
    # ============ Rate Limiting ============
    MAX_REQUESTS_PER_MINUTE = int(os.getenv("MAX_REQUESTS_PER_MINUTE", "60"))
    CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))
    
    # LLM Rate Limiting (for free tier protection)
    LLM_REQUESTS_PER_MINUTE = int(os.getenv("LLM_REQUESTS_PER_MINUTE", "30"))  # Groq free tier limit
    LLM_COOLDOWN_SECONDS = float(os.getenv("LLM_COOLDOWN_SECONDS", "2.0"))  # Delay between LLM calls
    RETRY_DELAY_MINUTES = int(os.getenv("RETRY_DELAY_MINUTES", "5"))  # Delay before retry
    MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", "2"))  # Max retry attempts
    
    # ============ Memory Settings ============
    MEMORY_HISTORY_LIMIT = int(os.getenv("MEMORY_HISTORY_LIMIT", "20"))  # Messages to remember
    MEMORY_PRUNE_DAYS = int(os.getenv("MEMORY_PRUNE_DAYS", "30"))  # Days before pruning old messages
    
    # ============ Model Configuration ============
    WORKER_MODEL = os.getenv("WORKER_MODEL", "llama-3.3-70b-versatile")
    EVALUATOR_MODEL = os.getenv("EVALUATOR_MODEL", "gemini-2.5-flash-lite")
    
    # ============ Telegram Integration ============
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    TELEGRAM_ALLOWED_USER_ID = os.getenv("TELEGRAM_ALLOWED_USER_ID")  # Comma-separated for multiple
    TELEGRAM_WEBHOOK_PORT = int(os.getenv("TELEGRAM_WEBHOOK_PORT", "8000"))
    
    @classmethod
    def ensure_directories(cls):
        """Ensure all required directories exist"""
        directories = [
            cls.SANDBOX_DIR,
            cls.NOTES_DIR,
            cls.TASKS_DIR,
            cls.SCREENSHOTS_DIR,
            cls.TEMP_DIR,
            cls.PERSISTENT_DIR
        ]
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    @classmethod
    def validate(cls):
        """Validate critical configuration"""
        errors = []
        
        if not cls.GROQ_API_KEY:
            errors.append("GROQ_API_KEY not set")
        if not cls.GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY not set")
        
        return errors
    
    @classmethod
    def get_info(cls) -> str:
        """Get configuration summary (hides sensitive values)"""
        def mask(val):
            if val and len(str(val)) > 4:
                return str(val)[:4] + "****"
            return "Not set" if not val else val
        
        return f"""
🔧 Orion Configuration:
━━━━━━━━━━━━━━━━━━━━━━━
API Keys:
  GROQ_API_KEY: {mask(cls.GROQ_API_KEY)}
  GEMINI_API_KEY: {mask(cls.GEMINI_API_KEY)}
  
Models:
  Worker: {cls.WORKER_MODEL}
  Evaluator: {cls.EVALUATOR_MODEL}

Rate Limiting:
  LLM requests/min: {cls.LLM_REQUESTS_PER_MINUTE}
  Cooldown: {cls.LLM_COOLDOWN_SECONDS}s
  Retry delay: {cls.RETRY_DELAY_MINUTES} min
  Max retries: {cls.MAX_RETRY_ATTEMPTS}

Memory:
  History limit: {cls.MEMORY_HISTORY_LIMIT} messages
  Prune after: {cls.MEMORY_PRUNE_DAYS} days
  Storage: {cls.PERSISTENT_DIR}

Telegram:
  Bot Token: {mask(cls.TELEGRAM_BOT_TOKEN)}
  Allowed Users: {cls.TELEGRAM_ALLOWED_USER_ID or "All (unsafe!)"}
"""
