# 🌟 Orion AI Personal Assistant

An advanced AI-powered personal assistant with **60 tools** across **9 intelligent categories**, **production-grade reliability** (circuit breaker, rate limiting, graceful shutdown), **full observability** (structured logging, correlation IDs, metrics endpoint), and multi-channel access (Telegram, Gradio, Email, Scheduler). Features an **LLM-based intent router** that classifies queries and selects only the relevant tools per request.

> **For detailed technical documentation, see [ARCHITECTURE.md](ARCHITECTURE.md)**

## ✨ Features

### 🎯 Core Capabilities
- **LLM-Based Intent Router**: Queries are classified into 9 categories (TRAVEL, COMMUNICATION, PRODUCTIVITY, DEVELOPER, MEDIA, RESEARCH, SYSTEM, BROWSER, GENERAL) using a dedicated Groq LLM (`llama-3.1-8b-instant`) with keyword-based fallback
- **Focused Tool Selection**: Only category-relevant tools (+ research tools) are given to the LLM per query — reducing token usage by 60-87%
- **Confidence-Based Routing**: Router returns a confidence score (0.0–1.0); low-confidence queries fall back to the full 60-tool set
- **Intelligent Task Execution**: Uses LangGraph workflow with worker-evaluator pattern
- **Persistent Memory**: Remembers conversations across sessions (SQLite-based)
- **Per-User Thread Isolation**: Each user × channel combination gets its own conversation thread
- **Circuit Breaker**: Fails fast when Groq LLM is down (5 failures → 60s recovery → probe → resume). Prevents cascading failures and gives users immediate feedback
- **Per-User Rate Limiting**: Each user gets 10 requests/minute (configurable). Prevents one user from exhausting the shared API quota
- **Health Check Endpoint**: `GET /health` returns subsystem status (200 healthy / 503 degraded). Load-balancer and monitoring compatible
- **Structured Logging**: Dual-output — human-readable console + JSON file (`orion_structured.log`). Every log call accepts `**context` kwargs for structured data
- **Correlation IDs**: Every request gets a unique `request_id` (8-char UUID) traced through worker → tools → evaluator for end-to-end debugging
- **Metrics Endpoint**: `GET /metrics` exposes request counts, latency percentiles (p50/p90/p99), circuit breaker state, and queue depths
- **Input Validation**: All incoming messages validated via Pydantic `ChatRequest` model before any LLM call — saves tokens on bad input
- **Config Validation**: `Config.validate_or_fail()` at startup catches missing API keys, invalid numeric bounds, bad port ranges — fail fast before heavy initialization
- **Graceful Shutdown**: In-flight request tracking, drain timeout (30s default), and clean resource cleanup on shutdown
- **Rate Limiting**: Smart cooldowns to protect free tier API limits (global + per-user)
- **Auto-Retry**: Failed requests automatically retry with notifications
- **Error Handling**: Robust retry logic and comprehensive error reporting
- **Tool Usage Tracking**: Monitor AI's tool usage in real-time
- **Export Conversations**: Save your chat history in JSON format

### 🛡️ Production-Grade Reliability & Observability
- **🧠 LLM Intent Router**: Dual-path classification (LLM-first + keyword fallback) with Pydantic structured output
- **🔒 Circuit Breaker**: CLOSED → OPEN → HALF_OPEN state machine for LLM calls (thread-safe)
- **👤 Per-User Rate Limiting**: Independent rate limit buckets per user (10 req/min default)
- **💓 Health Check**: `/health` with subsystem checks + circuit breaker state (200/503)
- **📊 Metrics Endpoint**: `/metrics` with request counts, latency percentiles, CB state, queue depths
- **📝 Structured Logging**: Dual-output logger (console + JSON) with `**context` kwargs
- **🔗 Correlation IDs**: 8-char UUID per request traced end-to-end (worker → tools → evaluator)
- **📏 Latency Tracking**: Rolling window (100 samples) with p50/p90/p99 percentile computation
- **✅ Input Validation**: Pydantic `ChatRequest` model (message length, channel chars, whitespace)
- **⚙️ Config Validation**: 11 validation checks at startup with critical/warning separation
- **🛑 Graceful Shutdown**: `_shutting_down` flag, in-flight counter, drain-then-cleanup pattern
- **🔄 Auto-Retry Queue**: Failed requests retry automatically (2 attempts, 5 min apart)
- **📢 Multi-Channel Notifications**: Get notified on all channels if something fails
- **☁️ Cloud Ready**: Deploy anywhere (Oracle Cloud Free, Docker, VPS)
- **📋 Pending Request Queue**: Queries are saved when bot is down, processed when back online
- **💓 Keep-Alive System**: Built-in self-ping for always-on deployment

### 🔧 60 Powerful Tools (9 Categories)

#### 📧 Email Management
- **Send Emails**: Send emails with attachments via SMTP
- **Read Emails**: Fetch and read recent emails via IMAP
- Supports Gmail, Outlook, and other email providers

#### 📅 Calendar Integration
- **Google Calendar Integration**: Create and manage calendar events
- **List Upcoming Events**: View your schedule for the next N days
- OAuth2 authentication for secure access

#### ✅ Task & Reminder Management

> **New:** tasks and notes support attachments, and tasks with a due date now automatically create a calendar event for reminders (30/15/5 min alerts via proactive module).

#### ✅ Task & Reminder Management
- **Create Tasks**: Add tasks with due dates and priorities
- **List Tasks**: View pending and completed tasks
- **Complete Tasks**: Mark tasks as done
- Persistent storage in JSON format

#### 📝 Note-Taking
- **Create Notes**: Save notes in Markdown format with tags
- **Search Notes**: Find notes by keyword search
- Organized storage with timestamps

#### 📸 Screenshot Capture
- **Take Screenshots**: Capture full-screen screenshots
- Automatic timestamping and organized storage

#### 📄 PDF Processing
- **Read PDF**: Extract text from PDF files (specific pages or all)
- **Create PDF**: Generate PDFs from text content
- Page-specific extraction support

#### 🔍 OCR (Optical Character Recognition)
- **Extract Text from Images**: Convert images to text
- Supports common image formats (PNG, JPG, JPEG)
- Powered by Tesseract OCR

#### 📊 Data File Handling
- **CSV Reader**: Read and analyze CSV files
- **Excel Reader**: Process Excel files with sheet selection
- **JSON Handler**: Read and write JSON files with pretty formatting
- **CSV to JSON Converter**: Convert between formats
- Built on pandas for powerful data manipulation

#### 📝 Markdown Tools
- **Markdown to HTML**: Convert Markdown to HTML
- **HTML to Markdown**: Convert HTML to Markdown
- Useful for content formatting and conversion

#### 🔲 QR Code Generator
- **Generate QR Codes**: Create QR codes from any text/URL
- Customizable and saved as PNG images

#### 🌐 Web & Information Tools
- **Web Search**: Search the web using Google Serper API
- **Wikipedia**: Query Wikipedia for information
- **Browser Automation**: Full Playwright integration for web interaction
- **Navigate & Scrape**: Extract content from websites

#### 🐍 Python Execution
- **Python REPL**: Execute Python code dynamically
- Useful for calculations, data processing, and more

#### 📁 File Management
- **Full File Operations**: Read, write, copy, move, delete files
- Sandboxed environment for safety

#### 📱 Communication
- **Push Notifications**: Send notifications via NTFY
- Real-time alerts for important updates

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- Tesseract OCR (for OCR functionality)
  - **Windows**: Download from [here](https://github.com/UB-Mannheim/tesseract/wiki)
  - **Linux**: `sudo apt-get install tesseract-ocr`
  - **Mac**: `brew install tesseract`

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd Orion-AI_Personal-Assistant
```

2. **Install dependencies**
```bash
pip install -r requirements.txt
```

3. **Install Playwright browsers**
```bash
playwright install chromium
```

4. **Configure environment variables**
```bash
cp .env.example .env
# Edit .env and add your API keys
```

### Required API Keys

#### Essential (Required for basic functionality):
1. **Groq API Key**: Get from [Groq Console](https://console.groq.com/)
2. **Google Gemini API Key**: Get from [Google AI Studio](https://makersuite.google.com/app/apikey)
3. **Serper API Key**: Get from [Serper.dev](https://serper.dev/)

#### Optional (For specific features):
- **Email**: Gmail App Password or SMTP credentials
- **Google Calendar**: OAuth2 credentials from [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
- **Push Notifications**: NTFY topic from [NTFY.sh](https://ntfy.sh/)

### Running Orion

See the **Running Orion** section above in the Architecture section.

```bash
# Quick start with Telegram
python main.py telegram
```

## 📖 Usage Examples

### Example 1: Email Management
```
User: "Send an email to john@example.com with subject 'Meeting Tomorrow' and body 'Let's meet at 3 PM'"

Orion: ✅ Email sent successfully to john@example.com
```

### Example 2: Calendar Events
```
User: "Create a calendar event 'Team Meeting' tomorrow at 2 PM for 1 hour"

Orion: ✅ Calendar event created: Team Meeting
🔗 Link: [Google Calendar Link]
```

### Example 3: PDF Processing
```
User: "Read the first 5 pages of document.pdf in the sandbox folder"

Orion: [Extracts and displays text from pages 1-5]
```

### Example 4: Data Analysis
```
User: "Read sales_data.csv and show me the first 10 rows"

Orion: 📊 CSV File: sales_data.csv
📏 Shape: 100 rows × 5 columns
[Displays data preview]
```

### Example 5: Task Management
```
User: "Create a high-priority task 'Finish project report' due on 2026-01-25"

Orion: ✅ Task #1 created: Finish project report
📅 Due: 2026-01-25
⚡ Priority: high
```

## 🎨 UI Features

### Enhanced Gradio Interface
- **Modern Design**: Clean, professional interface with purple theme
- **Session Statistics**: Track messages sent and tools used
- **File Upload**: Attach files directly in the chat
- **Export Conversations**: Save chat history as JSON
- **Tool List**: Visual reference of available tools
- **Status Indicators**: Real-time feedback on system status

## 🏗️ Architecture

### Code Structure
```
Orion/
├── main.py                    # 🚀 Single entry point for all modes
├── requirements.txt           # Python dependencies
├── .env                       # Environment variables (not in git)
├── ARCHITECTURE.md            # 📐 Detailed HLD/LLD technical docs
├── SDE2_UPGRADE_PLAN.md       # 📋 Phased upgrade roadmap
│
├── core/                      # 🧠 Core application logic
│   ├── __init__.py           # Package exports with lazy loading
│   ├── config.py             # Config class, ROUTER_MODEL, validate_or_fail(), ConfigValidationError
│   ├── models.py             # Pydantic models: ChatRequest, HealthResponse, MetricsResponse
│   ├── utils.py              # Logger (dual-output), Cache, RateLimiter, CircuitBreaker
│   ├── memory.py             # ConversationMemory, FailedRequestQueue, NotificationManager
│   └── agent.py              # Orion class: LangGraph workflow, router, metrics, graceful shutdown
│
├── agents/                    # 🤖 Intent classification & routing
│   ├── __init__.py           # Package exports
│   ├── base_agent.py         # AgentCategory enum (9 categories)
│   ├── router.py             # LLM + keyword intent classifier, TOOL_CATEGORIES mapping
│   ├── communication_agent.py
│   ├── developer_agent.py
│   ├── media_agent.py
│   ├── productivity_agent.py
│   ├── research_agent.py
│   ├── system_agent.py
│   └── travel_agent.py
│
├── tools/                     # 🔧 All 60 tools organized by category
│   ├── __init__.py           # Package exports
│   ├── loader.py             # Tool aggregator (get_all_tools)
│   ├── browser.py            # Playwright web automation (lazy import)
│   ├── calendar.py           # Google Calendar CRUD operations
│   ├── documents.py          # PDF, OCR, CSV, Excel, JSON, Markdown, QR
│   ├── email_tools.py        # Send/receive emails via SMTP/IMAP
│   ├── flights.py            # Flight status lookups
│   ├── github.py             # GitHub repo/issue/PR tools
│   ├── indian_railways.py    # PNR status, train search
│   ├── search.py             # Web search, Wikipedia, Python REPL
│   ├── tasks_notes.py        # Task and note management
│   ├── youtube.py            # YouTube search and info
│   └── utils.py              # Screenshot, notifications, file ops
│
├── integrations/              # 🔌 Multi-channel integrations
│   ├── __init__.py           # Package exports
│   ├── telegram.py           # Telegram bot integration
│   ├── gradio_ui.py          # Gradio web interface
│   ├── email_bot.py          # Email-based interaction
│   ├── proactive.py          # Proactive assistant features
│   └── scheduler.py          # Background task scheduler
│
├── tests/                     # ✅ Test suite (82 tests across 4 phases)
│   ├── __init__.py           # Package marker
│   ├── test_phase1.py        # 7 tests: router, tool index, thread isolation, LLM
│   ├── test_phase2.py        # 7 tests: circuit breaker, rate limiter, health check
│   ├── test_phase3.py        # 36 tests: logging, metrics, latency, correlation IDs
│   ├── test_phase4.py        # 32 tests: input validation, config, shutdown
│   ├── test_setup.py         # Setup verification tests
│   └── test_local.py         # Interactive CLI tester
│
├── google_cred/               # 🔐 Google OAuth credentials
│   ├── credentials.json      # OAuth client credentials
│   └── token.json            # Generated access tokens
│
└── sandbox/                   # 📁 Working directory for files
    ├── data/                 # Persistent data (SQLite databases)
    │   ├── orion_memory.db   # Conversation memory
    │   └── orion_retry_queue.db  # Failed request queue
    ├── notes/                # Stored notes
    ├── tasks/                # Task storage
    ├── screenshots/          # Screenshot storage
    └── temp/                 # Temporary files
```

### Running Orion

```bash
# Start with Telegram bot (recommended)
python main.py telegram

# Start Gradio web UI
python main.py gradio

# Start background scheduler
python main.py scheduler

# Run connection test
python main.py test

# Show configuration info
python main.py info
```

### Workflow Architecture
1. **Input Validation**: `ChatRequest` Pydantic model validates message (1-10000 chars, non-blank), channel (alphanumeric), and user_id before any processing
2. **Shutdown Check**: If `_shutting_down` flag is set, reject immediately with friendly message
3. **Per-User Rate Limit**: Check user's request bucket (10/min default). If exceeded, return wait time
4. **Intent Router** (LLM-first): Classifies query → category + confidence using `llama-3.1-8b-instant` (14,400 req/day free tier, separate quota from worker). Falls back to keyword scoring on error
5. **Circuit Breaker Check**: If circuit is OPEN, fail fast with "service unavailable" message
6. **Focused Tool Selection**: Category-specific tools + research tools are bound to the worker LLM (e.g., TRAVEL query gets 18 tools instead of 60)
7. **Worker Agent**: Uses `llama-4-scout-17b-16e-instruct` with focused tools to execute tasks
8. **Tool Node**: Executes selected tools
9. **Evaluator Agent**: Assesses completion and provides feedback
10. **Memory System**: Persists conversation state per user×channel thread
11. **Metrics**: Records latency (e2e + worker), increments success/failure counters, logs structured events with correlation ID

## 🔧 Configuration

### Email Setup (Gmail)
1. Enable 2-factor authentication
2. Generate an App Password: [Google App Passwords](https://myaccount.google.com/apppasswords)
3. Add to `.env`:
```env
EMAIL_ADDRESS=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
```

### Google Calendar Setup
1. Create a project in [Google Cloud Console](https://console.cloud.google.com/)
2. Enable Google Calendar API
3. Create OAuth2 credentials
4. Download `credentials.json` to project root
5. First use will prompt for authentication

### Custom Configuration
Edit `config.py` to customize:
- Directory locations
- Model selection (`MODEL_NAME` for worker/evaluator, `ROUTER_MODEL` for intent classifier)
- Rate limiting
- Cache TTL
- Logging level

### Running Tests
```bash
# Run all 82 tests
python -m pytest tests/ -v

# Run by phase
python -m pytest tests/test_phase1.py -v   # Router + thread isolation (7 tests)
python -m pytest tests/test_phase2.py -v   # Circuit breaker + rate limiter + health (7 tests)
python -m pytest tests/test_phase3.py -v   # Logging + metrics + latency + correlation IDs (36 tests)
python -m pytest tests/test_phase4.py -v   # Input validation + config + graceful shutdown (32 tests)
```

**82 automated tests** across 4 phases covering:
- **Phase 1** (7): keyword/LLM classification, delegation, tool index (60 tools × 9 categories), focused selection, thread isolation
- **Phase 2** (7): circuit breaker state transitions (CLOSED→OPEN→HALF_OPEN→CLOSED), fail-fast, probe failure, per-user rate limiter, health check JSON
- **Phase 3** (36): structured logging with `**context`, JSON output validation, metrics attributes, `get_metrics()`, latency rolling windows (100-cap, percentiles), `/metrics` endpoint, correlation IDs, worker/evaluator instrumentation
- **Phase 4** (32): `ChatRequest` model (valid/invalid inputs, defaults, length limits, channel chars, whitespace), config validation (numeric bounds, model names, ports, `validate_or_fail`, `ConfigValidationError`), graceful shutdown (flags, counters, locks, async method, result dict), metrics shutdown fields, in-flight tracking, lifespan integration

## 🛡️ Security & Best Practices

- **Sandboxed Environment**: File operations restricted to sandbox directory
- **API Key Protection**: Never commit `.env` file
- **Input Validation**: All inputs validated via Pydantic before reaching LLM (message length, channel chars, user ID sanitization)
- **Config Validation**: Startup validation of all config values — fail fast on missing critical keys
- **Circuit Breaker**: LLM calls wrapped in circuit breaker to prevent cascading failures
- **Per-User Rate Limiting**: Independent per-user buckets (10 req/min) + global API key protection
- **Graceful Shutdown**: In-flight requests drain cleanly before process exit (30s timeout)
- **Error Handling**: Comprehensive try-catch blocks with structured logging and correlation IDs
- **SSL Verification**: Configurable for corporate proxies

## 📊 Monitoring & Observability

### Structured Logging (Dual-Output)
- **Console + orion.log**: Human-readable format for development
- **orion_structured.log**: JSON-structured logs with correlation IDs, latency, and context fields
- All log methods accept `**context` kwargs: `logger.info("event", request_id="abc", latency_ms=120)`
- Backward compatible — `logger.info("msg")` works unchanged

### Correlation IDs
- Every request gets a unique `request_id` (8-char UUID prefix)
- Traced through: `superstep_start` → `worker_llm_call` → `worker_tool_calls` → `evaluator_complete` → `superstep_complete`
- Filter with: `grep request_id=a1b2c3d4 orion_structured.log`

### Metrics Endpoint (`GET /metrics`)
```json
{
  "timestamp": "2026-02-23T10:00:00",
  "orion": {
    "requests": {"total": 150, "successful": 140, "failed": 5, "rate_limited": 3, "circuit_broken": 2},
    "latency_ms": {
      "e2e": {"p50": 2100, "p90": 4500, "p99": 8200, "avg": 2800, "count": 100},
      "worker_llm": {"p50": 1200, "p90": 3000, "p99": 5500, "avg": 1600, "count": 100}
    },
    "circuit_breaker": {"state": "closed", "failure_count": 0},
    "tools": 60,
    "shutdown": {"shutting_down": false, "in_flight_requests": 1}
  },
  "memory": {"total_messages": 500, "total_users": 3},
  "retry_queue": {"pending": 0, "completed": 12, "failed": 1}
}
```

### Health Check (`GET /health`)
- Returns **200** `{"status": "healthy"}` when all subsystems are up
- Returns **503** `{"status": "degraded"}` when Orion not ready or circuit breaker is OPEN
- Includes: `orion_ready`, `memory_db`, `retry_queue`, `llm_circuit_breaker` state

### Latency Tracking
- **End-to-end**: Measured in `run_superstep()`, rolling window of 100 samples
- **Worker LLM**: Measured in `worker()`, separate rolling window of 100 samples
- **Percentiles**: p50, p90, p99, avg, count computed via `_percentiles()` helper

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues.

## 📝 License

[Your License Here]

## 🙏 Acknowledgments

- Built with [LangChain](https://www.langchain.com/) and [LangGraph](https://github.com/langchain-ai/langgraph)
- UI powered by [Gradio](https://gradio.app/)
- LLMs: [Groq](https://groq.com/) and [Google Gemini](https://deepmind.google/technologies/gemini/)

## 🐛 Troubleshooting

### Common Issues

**Issue**: Tesseract not found
- **Solution**: Install Tesseract OCR and add to PATH

**Issue**: Google Calendar authentication fails
- **Solution**: Delete `token.json` and re-authenticate

**Issue**: Email sending fails
- **Solution**: Use App Passwords for Gmail, check SMTP settings

**Issue**: Playwright browser doesn't launch
- **Solution**: Run `playwright install chromium`

### Getting Help
- Check logs in `orion.log`
- Review error messages in UI
- Ensure all required API keys are configured

## 🔮 Roadmap

### ✅ Implemented
- [x] LLM-based intent router with keyword fallback
- [x] Per-user thread isolation
- [x] Circuit breaker for LLM calls
- [x] Per-user rate limiting
- [x] Health check endpoint with subsystem status
- [x] Structured logging with dual-output
- [x] Correlation IDs for end-to-end tracing
- [x] Metrics endpoint with latency percentiles
- [x] Input validation via Pydantic models
- [x] Config validation with fail-fast startup
- [x] Graceful shutdown with drain timeout

### 🔜 Future Enhancements
- [ ] Centralized API Gateway (`/v1/chat` with bearer token auth)
- [ ] Voice input/output
- [ ] Advanced data visualization
- [ ] Database query support
- [ ] Advanced scheduling with cron
- [ ] Multi-language support

---

## 📱 Multi-Channel Access (All FREE!)

Access Orion from **anywhere** via multiple platforms - like having your own personal AI assistant!

### 🚀 Available Integrations

| Channel | Description | Setup |
|---------|-------------|-------|
| 📱 **Telegram** | Mobile + Desktop messaging | 5 min |
| 📧 **Email** | Send commands via email | 2 min |
| ⏰ **Scheduler** | Automated recurring tasks | 2 min |
| 🖥️ **Web UI** | Gradio interface | Ready! |

### Quick Start

```bash
# Start specific integrations
python main.py telegram      # Telegram bot only
python main.py gradio        # Web UI only
python main.py scheduler     # Scheduler only

# Check configuration status
python main.py info
```

### 📱 Telegram Setup (5 min)

1. **Create bot:** @BotFather → `/newbot` → Copy **BOT_TOKEN**
2. **Get your ID:** @userinfobot → Copy **User ID**
3. **Configure:**
   ```env
   TELEGRAM_BOT_TOKEN=your_token
   TELEGRAM_ALLOWED_USER_ID=your_id
   ```
4. **Run:** `python launcher.py telegram`

### 📧 Email Bot (2 min)

Send emails with subject `ORION: your command` and get responses!

```env
EMAIL_ADDRESS=you@gmail.com
EMAIL_PASSWORD=your_app_password
```

### ⏰ Scheduled Tasks

```bash
# Add a daily task
python integrations/scheduler.py --add "Morning Brief" "Check my emails and summarize" daily 09:00

# List tasks
python integrations/scheduler.py --list
```

### 🖥️ Gradio Web UI

Beautiful web interface to chat with Orion from any browser!

```bash
# Basic start
python integrations/gradio_ui.py

# With authentication (recommended for cloud)
python integrations/gradio_ui.py --auth username:password

# Create a public shareable link
python integrations/gradio_ui.py --share

# Custom port
python integrations/gradio_ui.py --port 7860
```

Access at: `http://localhost:7860`

---

## ☁️ Deploy to Oracle Cloud VM (FREE Forever)

Run Orion 24/7 on Oracle Cloud's **Always Free** tier - completely FREE, not a trial!

### Why Oracle Cloud Free Tier?
| Feature | Oracle Free | AWS/GCP/Azure Free |
|---------|-------------|-------------------|
| Duration | ♾️ Forever | 12-month trial |
| RAM | Up to 24 GB | 1 GB |
| Storage | 200 GB total | Limited |
| Always On | ✅ Yes | ❌ Sleep after idle |
| Network | ✅ Full access | ✅ Full access |

### 🚀 Step-by-Step Deployment

#### Step 1: Create Oracle Cloud Account
1. Go to [cloud.oracle.com/free](https://www.oracle.com/cloud/free/)
2. Click **"Start for Free"**
3. Complete signup (requires credit card for verification - you won't be charged)
4. Wait for account activation (can take 15-30 minutes)

#### Step 2: Create VM Instance
1. Go to **Compute → Instances → Create Instance**
2. Configure:
   - **Name:** `orion-server`
   - **Compartment:** (default)
   - **Image:** Ubuntu 22.04 (click "Change Image" → Ubuntu → 22.04)
   - **Shape:** Click "Change Shape" → **Ampere** → `VM.Standard.A1.Flex`
     - OCPUs: 2 (free up to 4)
     - Memory: 12 GB (free up to 24 GB)
   - **Networking:** Create new VCN or use existing
   - **Add SSH keys:** Generate or upload your SSH public key

3. Click **Create** and wait for instance to be running

#### Step 3: Configure Firewall
1. Go to **Networking → Virtual Cloud Networks** → Select your VCN
2. Click **Security Lists** → **Default Security List**
3. Click **Add Ingress Rules**:
   - **Source CIDR:** `0.0.0.0/0`
   - **Destination Port Range:** `7860` (for Gradio)
   - Click **Add**

#### Step 4: SSH into VM and Install
Copy your VM's **Public IP** from the instance details, then:

```bash
# SSH into VM (replace with your IP)
ssh ubuntu@YOUR_VM_IP

# Update system
sudo apt update && sudo apt upgrade -y

# Install Python 3.11 and dependencies
sudo apt install -y python3.11 python3.11-venv python3.11-dev git

# Install system dependencies for Playwright and OCR
sudo apt install -y wget tesseract-ocr tesseract-ocr-eng poppler-utils

# Clone your repository
git clone https://github.com/YOUR_USERNAME/Orion-AI_Personal-Assistant.git
cd Orion-AI_Personal-Assistant

# Create virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# Install Python dependencies
pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright (for browser automation)
playwright install chromium
playwright install-deps chromium
```

#### Step 5: Configure Environment Variables
```bash
# Create .env file
nano .env
```

Add your API keys:
```env
# Required
GROQ_API_KEY=your_groq_api_key
GEMINI_API_KEY=your_gemini_api_key
SERPER_API_KEY=your_serper_api_key

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_ALLOWED_USER_ID=your_telegram_user_id

# Email (Gmail with App Password)
EMAIL_ADDRESS=your_email@gmail.com
EMAIL_PASSWORD=your_gmail_app_password
IMAP_SERVER=imap.gmail.com
SMTP_SERVER=smtp.gmail.com

# Push Notifications (optional)
NTFY_TOPIC=your_ntfy_topic

# Data directory
ORION_DATA_DIR=/home/ubuntu/Orion-AI_Personal-Assistant/data
```

Save with `Ctrl+X`, then `Y`, then `Enter`.

#### Step 6: Test Run
```bash
# Activate venv and test
source .venv/bin/activate
python app_both.py
```

Access at: `http://YOUR_VM_IP:7860`

Test Telegram bot by sending `/start` to your bot.

#### Step 7: Setup Systemd Service (Auto-start)
```bash
# Create service file
sudo nano /etc/systemd/system/orion.service
```

Paste this content:
```ini
[Unit]
Description=Orion AI Assistant
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/Orion-AI_Personal-Assistant
Environment="PATH=/home/ubuntu/Orion-AI_Personal-Assistant/.venv/bin:/usr/bin"
EnvironmentFile=/home/ubuntu/Orion-AI_Personal-Assistant/.env
ExecStart=/home/ubuntu/Orion-AI_Personal-Assistant/.venv/bin/python app_both.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Save and enable:
```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable orion

# Start the service
sudo systemctl start orion

# Check status
sudo systemctl status orion

# View logs
sudo journalctl -u orion -f
```

### ✅ What's Working

| Feature | Status |
|---------|--------|
| 🌐 Gradio Web UI | ✅ `http://YOUR_IP:7860` |
| 🤖 Telegram Bot | ✅ Polling mode |
| 📬 Email Bot | ✅ IMAP monitoring |
| ⏰ Scheduler | ✅ Background tasks |
| 🧠 Persistent Memory | ✅ SQLite in data/ |
| 🔄 Auto-restart | ✅ Systemd |

### 🔧 Useful Commands
```bash
# Check service status
sudo systemctl status orion

# Restart service
sudo systemctl restart orion

# View live logs
sudo journalctl -u orion -f

# Stop service
sudo systemctl stop orion

# Update code
cd ~/Orion-AI_Personal-Assistant
git pull
sudo systemctl restart orion
```

---

## 🛠️ Technology Stack & Tradeoffs

### Tech Used — and Why

| Technology | Purpose | Why This Choice |
|-----------|---------|-----------------|
| **Python 3.8+** | Core language | LangChain/LangGraph ecosystem is Python-native. Rich async support for multi-channel I/O |
| **LangGraph** | Agent orchestration | StateGraph with `worker→tools→evaluator→END` pattern. Built-in checkpointing, cycle handling, and state management. Better than raw LangChain agents for multi-step tasks |
| **LangChain** | Tool framework | Standardized `BaseTool` interface for 60 tools. `ChatGroq` wrapper handles API calls, retries, and structured output |
| **Groq (LLM Provider)** | LLM inference | Free tier with generous limits: 1K RPD for `llama-4-scout-17b` (worker), 14.4K RPD for `llama-3.1-8b-instant` (router). Fastest inference speeds available |
| **llama-4-scout-17b-16e** | Worker + evaluator LLM | Best free-tier model for tool calling. 30K context window, good instruction following |
| **llama-3.1-8b-instant** | Intent router LLM | 14,400 RPD (14× worker quota). 8B is sufficient for "classify into 1 of 9 categories". Separate quota = zero conflict with worker |
| **Pydantic** | Input/output validation | Already a LangChain dependency (zero new deps). Type-safe structured output from LLM (`RouterClassification`), input validation (`ChatRequest`), config validation |
| **SQLite** | Conversation memory + retry queue | Zero-config, file-based, perfect for single-user personal assistant. WAL mode for concurrent reads. No server process to manage |
| **FastAPI** | HTTP endpoints | `/health`, `/metrics`, `/telegram/webhook`. Async-native, auto-generates OpenAPI docs, already used by Telegram integration |
| **Gradio** | Web UI | One-line chat interface with file upload, session stats, export. No frontend build step required |
| **Playwright** | Browser automation | 7 browser tools (navigate, click, extract, fill). Lazy-loaded — Orion works fine without it (53 tools instead of 60) |
| **threading.Lock** | Concurrency safety | Circuit breaker + in-flight counter need thread safety. `threading.Lock` works in both sync (`worker()`) and async (`run_superstep()`) contexts |
| **stdlib logging + JSON** | Structured logging | Dual-output (console + JSON) with `**context` kwargs. Zero new dependencies — extends existing Logger singleton |

### Tech NOT Used — and Why Not

| Technology | Why Excluded | When We'd Add It | Migration Path |
|-----------|-------------|-------------------|----------------|
| **PostgreSQL** | SQLite is correct for single-user, low-concurrency workloads. Postgres adds connection management overhead with no benefit at scale=1 | When concurrent writes exceed SQLite's single-writer lock (~10+ concurrent users) | Interface is already query-based — swap DB driver, no schema change |
| **Redis** | In-memory `Dict[str, list]` for rate limiting and `MemorySaver` for checkpoints work fine for single-process deployment. Redis requires a running server | Multi-process or multi-node deployment needing shared state | Same key format (`user:{id}`). Swap `RateLimiter` dict for `Redis INCR + EXPIRE`. Swap `MemorySaver` for `RedisSaver` (same interface) |
| **Kafka / RabbitMQ** | SQLite retry queue handles personal-assistant throughput (~5 msg/min). Message brokers add operational complexity (broker, consumers, monitoring) | >100 msg/sec throughput or multi-consumer processing | Queue interface (`push`, `pop`, `ack`) stays the same — backend swap only |
| **Celery** | All long-running work uses async coroutines. Celery adds broker dependency + worker processes + monitoring infra with no benefit at current scale | When tool execution time exceeds HTTP timeout budget | Already async — Celery workers would wrap existing tool functions |
| **structlog / loguru** | Existing Logger handles dual-output (console + JSON) with `**context` kwargs. Adding a library would change every call site or require maintaining two systems | Team project with 10+ services needing consistent log pipeline | Migration is a one-file change (`core/utils.py`) |
| **Prometheus** | JSON `/metrics` endpoint is directly consumable by humans, scripts, and monitoring tools. Prometheus needs a running server + scrape config + Grafana | Multi-instance deployment needing metrics aggregation | Add `/metrics/prometheus` endpoint (~20 lines) or use `json_exporter` sidecar |
| **Docker Compose (multi-service)** | Splitting a personal assistant into microservices is over-engineering. Monolith with clean module boundaries is correct for single-team | When teams independently deploy components (org structure drives service boundaries) | Module boundaries already exist (`core/`, `agents/`, `tools/`, `integrations/`) |
| **Vector DB / RAG** | Not needed for current functionality. It's a feature addition, not an architectural upgrade | When conversation history exceeds keyword-search usefulness | Add Chroma/Pinecone for semantic memory search. Could index `ConversationMemory` |
| **JWT / OAuth** | Telegram provides built-in authentication (`chat_id`). Adding auth to a personal bot is security theater | API gateway serving multiple external clients | FastAPI's `Depends(HTTPBearer())` with bearer tokens. 20-line addition |
| **Load Testing (locust)** | Good practice but not a code change. Can be added later as a standalone script | Before production deployment at scale | Write `locustfile.py` targeting `/v1/chat` endpoint |

### Design Philosophy

> **"Designed for scale, deployed for one."**

The multi-user patterns (thread isolation, per-user rate limits, circuit breaker) are **correctness requirements**, not scaling features. The abstractions are built so that scaling is a **backend swap, not an architecture rewrite**:

```
RateLimiter(key="user:123")     →  Same interface, swap dict for Redis INCR
MemorySaver()                   →  Same interface, swap for RedisSaver()
SQLite retry queue              →  Same push/pop interface, swap for Redis Streams
thread_id = f"{user_id}_{ch}"   →  Already multi-user aware, no change needed
CircuitBreaker()                →  Already user-agnostic, no change needed
ChatRequest                     →  Already channel-agnostic validation
```

---

**Made with ❤️ for productivity enthusiasts**
