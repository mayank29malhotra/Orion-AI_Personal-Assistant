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
    USER_REQUESTS_PER_MINUTE = int(os.getenv("USER_REQUESTS_PER_MINUTE", "10"))  # Per-user fairness limit
    RETRY_DELAY_MINUTES = int(os.getenv("RETRY_DELAY_MINUTES", "5"))  # Delay before retry
    MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", "2"))  # Max retry attempts
    
    # ============ Memory Settings ============
    MEMORY_HISTORY_LIMIT = int(os.getenv("MEMORY_HISTORY_LIMIT", "20"))  # Messages to remember
    MEMORY_PRUNE_DAYS = int(os.getenv("MEMORY_PRUNE_DAYS", "30"))  # Days before pruning old messages
    
    # ============ Model Configuration ============
    # Using Llama 4 Scout - newest model with 30K context, best value
    WORKER_MODEL = os.getenv("WORKER_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
    EVALUATOR_MODEL = os.getenv("EVALUATOR_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
    # Router model: lightweight 8B for intent classification
    # llama-3.1-8b-instant chosen for 14,400 RPD (vs 1K for others) — separate quota from worker
    ROUTER_MODEL = os.getenv("ROUTER_MODEL", "llama-3.1-8b-instant")
    
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
        """Validate critical configuration.
        
        Returns a list of error strings. Empty list = valid config.
        Checks: required API keys, numeric bounds, model names.
        """
        errors = []
        
        # --- Critical: required API keys ---
        if not cls.GROQ_API_KEY:
            errors.append("GROQ_API_KEY not set (required for LLM calls)")
        if not cls.GEMINI_API_KEY:
            errors.append("GEMINI_API_KEY not set (required for fallback)")
        
        # --- Numeric bounds ---
        if cls.LLM_REQUESTS_PER_MINUTE <= 0:
            errors.append(f"LLM_REQUESTS_PER_MINUTE must be > 0, got {cls.LLM_REQUESTS_PER_MINUTE}")
        if cls.USER_REQUESTS_PER_MINUTE <= 0:
            errors.append(f"USER_REQUESTS_PER_MINUTE must be > 0, got {cls.USER_REQUESTS_PER_MINUTE}")
        if cls.LLM_COOLDOWN_SECONDS < 0:
            errors.append(f"LLM_COOLDOWN_SECONDS must be >= 0, got {cls.LLM_COOLDOWN_SECONDS}")
        if cls.MEMORY_HISTORY_LIMIT <= 0:
            errors.append(f"MEMORY_HISTORY_LIMIT must be > 0, got {cls.MEMORY_HISTORY_LIMIT}")
        if cls.MAX_RETRY_ATTEMPTS < 0:
            errors.append(f"MAX_RETRY_ATTEMPTS must be >= 0, got {cls.MAX_RETRY_ATTEMPTS}")
        if cls.RETRY_DELAY_MINUTES < 0:
            errors.append(f"RETRY_DELAY_MINUTES must be >= 0, got {cls.RETRY_DELAY_MINUTES}")
        
        # --- Model names must be non-empty ---
        if not cls.WORKER_MODEL:
            errors.append("WORKER_MODEL is empty (required for LLM calls)")
        if not cls.EVALUATOR_MODEL:
            errors.append("EVALUATOR_MODEL is empty (required for evaluation)")
        if not cls.ROUTER_MODEL:
            errors.append("ROUTER_MODEL is empty (required for intent classification)")
        
        # --- SMTP port sanity ---
        if cls.SMTP_PORT <= 0 or cls.SMTP_PORT > 65535:
            errors.append(f"SMTP_PORT must be 1-65535, got {cls.SMTP_PORT}")
        if cls.IMAP_PORT <= 0 or cls.IMAP_PORT > 65535:
            errors.append(f"IMAP_PORT must be 1-65535, got {cls.IMAP_PORT}")
        
        return errors
    
    @classmethod
    def validate_or_fail(cls):
        """Validate config and raise if any critical errors found.
        
        Call this at startup to fail fast instead of discovering bad config
        mid-request. Non-critical warnings are logged but don't cause failure.
        """
        errors = cls.validate()
        
        # Separate critical (block startup) from warnings (log but continue)
        critical = [e for e in errors if "not set" in e or "empty" in e or "must be" in e]
        
        # API keys are critical only if GROQ is missing (Gemini is fallback)
        # For startup, GROQ_API_KEY is the true blocker
        hard_blockers = [e for e in critical if "GROQ_API_KEY" in e]
        
        if hard_blockers:
            raise ConfigValidationError(
                f"Orion cannot start: {'; '.join(hard_blockers)}"
            )
        
        # Log all other issues as warnings (non-blocking)
        for error in errors:
            if error not in hard_blockers:
                import logging
                logging.getLogger("Orion").warning(f"Config warning: {error}")
        
        return errors


class ConfigValidationError(Exception):
    """Raised when critical config is missing or invalid at startup."""
    pass
    
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
  User requests/min: {cls.USER_REQUESTS_PER_MINUTE}
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
