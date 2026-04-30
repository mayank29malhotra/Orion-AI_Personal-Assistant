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

# Optional Redis backend (Phase 6) — leave commented out for local-only mode
# REDIS_ENABLED=true
# REDIS_URL=redis://localhost:6379/0
# REDIS_NAMESPACE=orion
# REDIS_SOCKET_TIMEOUT=2.0

# Optional search cache (Phase 6.3)
# SEARCH_CACHE_ENABLED=true
# SEARCH_CACHE_TTL_SECONDS=600

# Optional Swiggy MCP integration (Phase 8 — FOOD domain) — see "Swiggy Setup" below
# Tools load automatically when SWIGGY_ACCESS_TOKEN is set (same as GITHUB_TOKEN)
# SWIGGY_ACCESS_TOKEN=eyJhbGciOiJI...
# SWIGGY_FOOD_ENABLED=true
# SWIGGY_DINEOUT_ENABLED=true
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

### 6.5. (Optional) Swiggy MCP Setup — FOOD domain

Phase 8 adds a `FOOD` category powered by [Swiggy Builders Club](https://mcp.swiggy.com/builders/) MCP servers. Orion uses Swiggy to **find and order food** (Swiggy Food, 14 tools) and to **book tables at favourite restaurants** (Swiggy Dineout, 8 tools) — 22 tools total. Tools load automatically when `SWIGGY_ACCESS_TOKEN` is set, same as `GITHUB_TOKEN` activates GitHub tools. Skip this section if you don't need food / dineout integration; Orion just logs an info message and runs without those tools. (Swiggy's Instamart grocery server is intentionally out of scope.)

1. **Apply for production access** at https://mcp.swiggy.com/builders/access/ (whitelist-only in v1). You can prototype on `http://localhost` first.
2. **Capture an OAuth bearer token** via one of:
   - Easy path: install `mcp-remote` in Claude Desktop / Cursor / VS Code Copilot, complete the in-browser OAuth flow once, then read the bearer from the MCP session log.
   - Manual path: follow the [Authenticate](https://mcp.swiggy.com/builders/docs/start/authenticate.md) guide — generate PKCE verifier/challenge, hit `/auth/authorize`, exchange the code at `/auth/token`.
3. **Add to `.env`**:
   ```env
   SWIGGY_ACCESS_TOKEN=eyJhbGciOiJI...   # 5-day bearer; re-run OAuth on 401
   ```
4. **Verify**: on next startup Orion logs `Swiggy MCP loaded: 22 tools across 2 server(s)`. Try a query like *"Find biryani restaurants near my home address on Swiggy"* — the router will classify as FOOD and the agent will call `swiggy_food_get_addresses` then `swiggy_food_search_restaurants`. Or *"Book a table for 2 at my favourite restaurant tomorrow at 8 PM"* — routes through `swiggy_dineout_*`.

**Notes**:
- Tokens expire after 5 days. Refresh-token issuance is not yet wired in Swiggy v1.0 — on 401, re-run the OAuth flow.
- Place-order / checkout / book-table tools place **real orders on your Swiggy account**. Orion's master prompt is configured to require explicit user confirmation before any of these mutating calls, but treat staging/local development carefully.
- v1.0 is COD-only on Food, with a ₹1000 cart cap.

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

### Optional Redis Backend (Phase 6)

Orion runs fully standalone with `REDIS_ENABLED=false` (the default). Enabling Redis turns on three distributed subsystems, each with an automatic in-memory fallback if Redis is unreachable or any operation fails:

| Sub-phase | What it enables |
|-----------|-----------------|
| **6.1** Distributed rate limiter | Per-user budget enforced atomically across multiple Orion instances |
| **6.2** Distributed checkpoints | LangGraph thread state survives process restarts; threads are shareable across instances (**requires Redis Stack / RediSearch**) |
| **6.3** Distributed search cache | `web_search` and `wikipedia_search` results are cached and shared across instances |

**Quick start with Docker (Redis Stack — recommended for full Phase 6):**
```bash
docker run -d --name orion-redis -p 6379:6379 redis/redis-stack-server:latest
```

**Quick start with Docker (plain Redis — 6.1 and 6.3 only; 6.2 will fall back to MemorySaver):**
```bash
docker run -d --name orion-redis -p 6379:6379 redis:7-alpine
```

Then in `.env`:
```env
REDIS_ENABLED=true
REDIS_URL=redis://localhost:6379/0
REDIS_NAMESPACE=orion
REDIS_SOCKET_TIMEOUT=2.0
```

**Verify**: hit `GET /metrics` and `GET /health` — the response includes a `redis` block (`enabled`, `connected`, `mode`, `latency_ms`) and `orion.checkpointer` should report `"redis"` when Redis Stack is reachable.

> Redis is **optional infrastructure**: a missing or broken Redis is logged as a warning, never fatal. Orion stays fully functional in local-only mode.

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
