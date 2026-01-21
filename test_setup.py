"""
Test script to verify Orion setup and configuration
Run this before starting the main application
"""
import sys
import os
from pathlib import Path

def print_status(message, status="info"):
    """Print colored status messages"""
    colors = {
        "success": "\033[92m✓",  # Green
        "error": "\033[91m✗",    # Red
        "warning": "\033[93m⚠",  # Yellow
        "info": "\033[94mℹ",     # Blue
    }
    reset = "\033[0m"
    print(f"{colors.get(status, colors['info'])} {message}{reset}")

def check_python_version():
    """Check if Python version is compatible"""
    version = sys.version_info
    if version >= (3, 8):
        print_status(f"Python {version.major}.{version.minor}.{version.micro} - OK", "success")
        return True
    else:
        print_status(f"Python {version.major}.{version.minor} - Need 3.8 or higher", "error")
        return False

def check_imports():
    """Check if required packages are installed"""
    packages = {
        "gradio": "gradio",
        "langgraph": "langgraph",
        "langchain": "langchain-core",
        "langchain_openai": "langchain-openai",
        "langchain_google_genai": "langchain-google-genai",
        "playwright": "playwright",
        "pandas": "pandas",
        "PyPDF2": "PyPDF2",
        "PIL": "Pillow",
        "qrcode": "qrcode",
        "markdown": "markdown",
        "html2text": "html2text",
    }
    
    missing = []
    for package, install_name in packages.items():
        try:
            __import__(package)
            print_status(f"{install_name} - Installed", "success")
        except ImportError:
            print_status(f"{install_name} - Missing", "error")
            missing.append(install_name)
    
    return missing

def check_env_file():
    """Check if .env file exists"""
    if os.path.exists(".env"):
        print_status(".env file found", "success")
        
        # Check for required keys
        from dotenv import load_dotenv
        load_dotenv()
        
        required_keys = ["GROQ_API_KEY", "GEMINI_API_KEY", "SERPER_API_KEY"]
        missing_keys = []
        
        for key in required_keys:
            if os.getenv(key):
                print_status(f"  {key} - Set", "success")
            else:
                print_status(f"  {key} - Missing", "warning")
                missing_keys.append(key)
        
        return len(missing_keys) == 0
    else:
        print_status(".env file not found", "error")
        print_status("  Copy .env.example to .env and add your API keys", "info")
        return False

def check_tesseract():
    """Check if Tesseract OCR is installed"""
    try:
        import pytesseract
        from PIL import Image
        # Try to get version
        pytesseract.get_tesseract_version()
        print_status("Tesseract OCR - Installed", "success")
        return True
    except Exception as e:
        print_status("Tesseract OCR - Not found", "warning")
        print_status("  Install from: https://github.com/UB-Mannheim/tesseract/wiki", "info")
        return False

def check_directories():
    """Check if required directories exist"""
    directories = ["sandbox", "sandbox/notes", "sandbox/tasks", "sandbox/screenshots", "sandbox/temp"]
    
    for directory in directories:
        if os.path.exists(directory):
            print_status(f"{directory}/ - Exists", "success")
        else:
            os.makedirs(directory, exist_ok=True)
            print_status(f"{directory}/ - Created", "success")
    
    return True

def check_playwright_browsers():
    """Check if Playwright browsers are installed"""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            try:
                browser = p.chromium.launch(headless=True)
                browser.close()
                print_status("Playwright Chromium - Installed", "success")
                return True
            except Exception:
                print_status("Playwright Chromium - Not installed", "error")
                print_status("  Run: playwright install chromium", "info")
                return False
    except ImportError:
        print_status("Playwright - Not installed", "error")
        return False

def main():
    """Run all checks"""
    print("\n" + "="*60)
    print("🌟 ORION AI PERSONAL ASSISTANT - SETUP VERIFICATION")
    print("="*60 + "\n")
    
    print("📋 Checking Python Version...")
    python_ok = check_python_version()
    print()
    
    print("📦 Checking Python Packages...")
    missing_packages = check_imports()
    print()
    
    print("🔑 Checking Environment Configuration...")
    env_ok = check_env_file()
    print()
    
    print("📁 Checking Directories...")
    dirs_ok = check_directories()
    print()
    
    print("🔍 Checking Optional Dependencies...")
    tesseract_ok = check_tesseract()
    print()
    
    print("🌐 Checking Playwright Browsers...")
    playwright_ok = check_playwright_browsers()
    print()
    
    print("="*60)
    print("📊 SUMMARY")
    print("="*60)
    
    all_ok = True
    
    if not python_ok:
        print_status("Python version too old", "error")
        all_ok = False
    
    if missing_packages:
        print_status(f"Missing {len(missing_packages)} packages", "error")
        print(f"  Install with: pip install {' '.join(missing_packages)}")
        all_ok = False
    
    if not env_ok:
        print_status("Environment configuration incomplete", "warning")
        print("  Some features may not work")
    
    if not tesseract_ok:
        print_status("OCR features unavailable", "warning")
    
    if not playwright_ok:
        print_status("Browser automation unavailable", "error")
        print("  Run: playwright install chromium")
        all_ok = False
    
    print()
    if all_ok:
        print_status("✨ All checks passed! You're ready to run Orion!", "success")
        print("\nStart Orion with: python app.py")
    else:
        print_status("❌ Some issues found. Please fix them before running Orion.", "error")
        print("\nSee SETUP.md for detailed instructions")
    
    print()
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
