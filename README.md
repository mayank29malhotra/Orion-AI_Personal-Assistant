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
- **☁️ Cloud Ready**: Deploy anywhere (Oracle Cloud Free, Docker, VPS)
- **📋 Pending Request Queue**: Queries are saved when bot is down, processed when back online
- **💓 Keep-Alive System**: Built-in self-ping for always-on deployment

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

**Made with ❤️ for productivity enthusiasts**
