# 🚀 Quick Setup Guide for Orion AI Personal Assistant

## Step-by-Step Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Playwright Browsers

```bash
playwright install chromium
```

### 3. Install Tesseract OCR (for OCR functionality)

#### Windows:
1. Download installer from: https://github.com/UB-Mannheim/tesseract/wiki
2. Install to default location (usually `C:\Program Files\Tesseract-OCR`)
3. Add to PATH or set environment variable:
   ```
   TESSDATA_PREFIX=C:\Program Files\Tesseract-OCR\tessdata
   ```

#### Linux (Ubuntu/Debian):
```bash
sudo apt-get update
sudo apt-get install tesseract-ocr
```

#### macOS:
```bash
brew install tesseract
```

### 4. Configure Environment Variables

1. Copy the example environment file:
```bash
cp .env.example .env
```

2. Edit `.env` and add your API keys:

**Required Keys:**
```env
GROQ_API_KEY=your_groq_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
SERPER_API_KEY=your_serper_api_key_here
```

**Optional (for specific features):**
```env
# Email
EMAIL_ADDRESS=your_email@gmail.com
EMAIL_PASSWORD=your_app_password

# NTFY
NTFY_TOPIC=your_unique_topic_name
```

### 5. Get API Keys

#### Groq API (Required)
1. Visit: https://console.groq.com/
2. Sign up / Log in
3. Go to API Keys section
4. Create new API key
5. Copy and paste into `.env`

#### Google Gemini API (Required)
1. Visit: https://makersuite.google.com/app/apikey
2. Sign in with Google account
3. Click "Create API Key"
4. Copy and paste into `.env`

#### Serper API (Required for web search)
1. Visit: https://serper.dev/
2. Sign up for free account
3. Get your API key from dashboard
4. Copy and paste into `.env`

#### Gmail App Password (Optional - for email features)
1. Enable 2-factor authentication on your Google account
2. Visit: https://myaccount.google.com/apppasswords
3. Generate an app password for "Mail"
4. Copy the 16-character password into `.env`

#### Google Calendar (Optional - for calendar features)
1. Visit: https://console.cloud.google.com/
2. Create a new project or select existing
3. Enable Google Calendar API
4. Create OAuth2 credentials (Desktop app)
5. Download `credentials.json` to project root
6. First use will prompt for authentication in browser

### 6. Create Required Directories

The app will auto-create these, but you can create them manually:
```bash
mkdir -p sandbox/notes sandbox/tasks sandbox/screenshots sandbox/temp
```

### 7. Run Orion!

```bash
python app.py
```

The Gradio interface will automatically open in your browser at:
```
http://localhost:7860
```

## 🎉 First Steps

Once running, try these commands to test features:

1. **Basic Query**: "What is the capital of France?"
2. **Web Search**: "Search for the latest news about AI"
3. **Create Task**: "Create a task 'Buy groceries' with high priority due tomorrow"
4. **Take Screenshot**: "Take a screenshot"
5. **Python Execution**: "Calculate the square root of 144"

## ⚙️ Optional Configuration

### Proxy Settings (for corporate networks)
Add to `.env`:
```env
HTTP_PROXY=http://proxy.example.com:8080
HTTPS_PROXY=https://proxy.example.com:8080
```

### Custom Directories
Add to `.env`:
```env
SANDBOX_DIR=custom/sandbox
NOTES_DIR=custom/notes
```

### Model Selection
Change AI models in `.env`:
```env
WORKER_MODEL=llama-3.3-70b-versatile
EVALUATOR_MODEL=gemini-2.5-flash-lite
```

## 🐛 Troubleshooting

### "Module not found" errors
```bash
pip install -r requirements.txt --upgrade
```

### Playwright issues
```bash
playwright install chromium --force
```

### Tesseract not found
- Ensure Tesseract is installed and in PATH
- On Windows, add to PATH: `C:\Program Files\Tesseract-OCR`

### Email authentication fails
- Use App Password for Gmail, not regular password
- Check SMTP settings match your email provider

### Google Calendar not working
- Delete `token.json` and try again
- Ensure Google Calendar API is enabled in Cloud Console
- Check `credentials.json` is in project root

## 📚 Need Help?

Check the main [README.md](README.md) for detailed documentation.

## 🎊 You're All Set!

Enjoy your enhanced AI personal assistant with 35+ powerful tools! 🚀
