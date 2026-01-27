---
title: Orion AI Assistant
emoji: 🌟
colorFrom: purple
colorTo: blue
sdk: gradio
sdk_version: "5.23.3"
python_version: "3.11"
app_file: app_both.py
pinned: false
---

# 🌟 Orion AI Personal Assistant

An advanced AI-powered personal assistant with **35+ tools** across multiple categories including email management, calendar integration, document processing, web automation, and much more!

## ✨ Features

### 🎯 Core Capabilities
- **Intelligent Task Execution**: Uses LangGraph workflow with worker-evaluator pattern
- **Persistent Memory**: Remembers conversations across sessions (SQLite-based)
- **Rate Limiting**: Smart cooldowns to protect free tier API limits
- **Auto-Retry**: Failed requests automatically retry with notifications
- **Error Handling**: Robust retry logic and comprehensive error reporting
- **Tool Usage Tracking**: Monitor AI's tool usage in real-time
- **Export Conversations**: Save your chat history in JSON format

### 🆕 New Features
- **🧠 Conversation Memory**: Orion remembers your previous conversations
- **⏱️ Rate Limiting**: Automatic throttling for LLM free tier limits
- **🔄 Auto-Retry Queue**: Failed requests retry automatically (2 attempts, 5 min apart)
- **📢 Multi-Channel Notifications**: Get notified on all channels if something fails
- **☁️ HuggingFace Spaces Ready**: Persistent storage works with `/data` directory
- **📋 Pending Request Queue**: Queries are saved when bot is down, processed when back online
- **💓 Keep-Alive System**: Built-in self-ping + GitHub Actions cron to prevent HF sleep

### 🔧 35+ Powerful Tools

#### 📧 Email Management
- **Send Emails**: Send emails with attachments via SMTP
- **Read Emails**: Fetch and read recent emails via IMAP
- Supports Gmail, Outlook, and other email providers

#### 📅 Calendar Integration
- **Google Calendar Integration**: Create and manage calendar events
- **List Upcoming Events**: View your schedule for the next N days
- OAuth2 authentication for secure access

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
│
├── core/                      # 🧠 Core application logic
│   ├── __init__.py           # Package exports with lazy loading
│   ├── config.py             # Configuration management (Config class)
│   ├── utils.py              # Logger, Cache, RateLimiter classes
│   ├── memory.py             # ConversationMemory, FailedRequestQueue, NotificationManager
│   └── agent.py              # Main Orion class with LangGraph workflow
│
├── tools/                     # 🔧 All 35+ tools organized by category
│   ├── __init__.py           # Package exports
│   ├── loader.py             # Tool aggregator (get_all_tools)
│   ├── browser.py            # Playwright web automation (lazy import)
│   ├── calendar.py           # Google Calendar CRUD operations
│   ├── documents.py          # PDF, OCR, CSV, Excel, JSON, Markdown, QR
│   ├── email_tools.py        # Send/receive emails via SMTP/IMAP
│   ├── search.py             # Web search, Wikipedia, Python REPL
│   ├── tasks_notes.py        # Task and note management
│   └── utils.py              # Screenshot, notifications, file ops
│
├── integrations/              # 🔌 Multi-channel integrations
│   ├── __init__.py           # Package exports
│   ├── telegram.py           # Telegram bot integration
│   ├── gradio_ui.py          # Gradio web interface
│   ├── email_bot.py          # Email-based interaction
│   └── scheduler.py          # Background task scheduler
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
1. **Worker Agent**: Uses LLM with tools to execute tasks
2. **Tool Node**: Executes selected tools
3. **Evaluator Agent**: Assesses completion and provides feedback
4. **Memory System**: Persists conversation state

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
- Model selection
- Rate limiting
- Cache TTL
- Logging level

## 🛡️ Security & Best Practices

- **Sandboxed Environment**: File operations restricted to sandbox directory
- **API Key Protection**: Never commit `.env` file
- **Rate Limiting**: Built-in protection against API overuse
- **Error Handling**: Comprehensive try-catch blocks with logging
- **SSL Verification**: Configurable for corporate proxies

## 📊 Monitoring & Logging

### Logging
- All operations logged to `orion.log`
- Console output for real-time monitoring
- Configurable log levels: DEBUG, INFO, WARNING, ERROR

### Statistics Tracking
- Messages sent counter
- Tools used counter
- Session duration tracking

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

Future enhancements:
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

## ☁️ Deploy to HuggingFace Spaces (Free)

Run Orion for free on HuggingFace Spaces with automatic GitHub sync!

### 🚀 Quick Setup (5 min)

#### Step 1: Create HuggingFace Space
1. Go to [huggingface.co/spaces](https://huggingface.co/spaces)
2. Click **"Create new Space"**
3. Name: `orion-ai`, SDK: **Gradio**, Hardware: **CPU Basic** (free)

#### Step 2: Set Up GitHub Auto-Sync
Add these **GitHub Secrets** (Repo → Settings → Secrets → Actions):

| Secret | Value |
|--------|-------|
| `HF_TOKEN` | Your HF write token from [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) |
| `HF_USERNAME` | Your HuggingFace username |
| `HF_SPACE_NAME` | `orion-ai` |

Every push to `main` automatically deploys to HuggingFace!

#### Step 3: Set HuggingFace Secrets
In HF Space → **Settings → Variables and secrets**:

| Secret | Required | Description |
|--------|----------|-------------|
| `GROQ_API_KEY` | ✅ Yes | Groq LLM API key |
| `GEMINI_API_KEY` | ✅ Yes | Google Gemini API key |
| `SERPER_API_KEY` | ✅ Yes | Web search API key |
| `EMAIL_ADDRESS` | Optional | Your Gmail address |
| `EMAIL_PASSWORD` | Optional | Gmail App Password (not regular password!) |
| `GOOGLE_CALENDAR_TOKEN_JSON` | Optional | Paste entire `token.json` content (see below) |
| `NTFY_TOPIC` | Optional | Push notification topic |

#### Step 4: Enable Google Calendar (Optional)
1. Run locally to generate token:
   ```bash
   python -c "from tools.calendar import generate_token; generate_token()"
   ```
2. Copy the JSON output
3. Paste as `GOOGLE_CALENDAR_TOKEN_JSON` secret in HF Space

### ✅ Features on HuggingFace
- 📧 **Email**: ✅ Works (uses SMTP with App Password)
- 📅 **Calendar**: ✅ Works (with token secret)
- 🧠 **Memory**: ✅ Persistent (stored in `/data`)
- 🔍 **Web Search**: ✅ Works
- 📝 **Notes/Tasks**: ✅ Persistent

---

## ☁️ Deploy to Oracle Cloud VM (Free Forever)

Run Orion 24/7 on Oracle Cloud's **Always Free** tier and access via Telegram!

### Cost: **$0/month FOREVER** (not a trial!)

### Why Oracle Cloud?
- Google/AWS/Azure "free tiers" are 90-day or 12-month **trials**
- Oracle Cloud Always Free is **truly free forever**
- Get up to **4 ARM cores + 24GB RAM** for free!

### Quick Deployment Steps

1. **Create Oracle Cloud account** at [oracle.com/cloud/free](https://www.oracle.com/cloud/free/)

2. **Create VM:**
   - **Shape:** VM.Standard.A1.Flex (ARM - 2 OCPUs, 12GB RAM)
   - **Image:** Ubuntu 22.04
   - **Storage:** 50 GB

3. **Setup VM:**
   ```bash
   # Install dependencies
   sudo apt update && sudo apt install -y python3.11 python3.11-venv git
   
   # Clone your repo
   git clone YOUR_REPO_URL orion && cd orion
   
   # Setup Python environment
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   playwright install chromium
   ```

4. **Configure & Run:**
   ```bash
   # Create .env file with your keys
   nano .env
   
   # Set Telegram webhook (use Cloudflare Tunnel for free HTTPS)
   python telegram_integration.py --set-webhook https://your-domain/telegram/webhook
   ```

### 📖 Full Guide
See **[TELEGRAM_DEPLOYMENT.md](TELEGRAM_DEPLOYMENT.md)** for complete step-by-step instructions including:
- Oracle Cloud VM setup
- Cloudflare Tunnel setup (free HTTPS)
- Systemd service configuration
- Security best practices

---

**Made with ❤️ for productivity enthusiasts**
