# Orion AI — Feature Reference

> Quick reference of all capabilities, tools, configuration, and usage examples.

---

## 60 Tools Across 9 Categories

### Productivity Tools (12 tools)
| Tool | Description |
|------|-------------|
| 📧 `send_email` | Send emails with attachments via SMTP |
| 📧 `read_recent_emails` | Read recent emails via IMAP |
| 📅 `create_calendar_event` | Create Google Calendar events |
| 📅 `list_calendar_events` | List upcoming calendar events |
| ✅ `create_task` | Create tasks with due dates and priorities |
| ✅ `list_tasks` | List all tasks (pending/completed) |
| ✅ `complete_task` | Mark tasks as completed |
| 📝 `create_note` | Create notes in Markdown format |
| 📝 `search_notes` | Search notes by keyword |
| 📸 `take_screenshot` | Capture screenshots |
| 📱 `send_push_notification` | Push notifications via NTFY |
| 🔲 `generate_qr_code` | Generate QR codes from text/URLs |

### Document Processing / Media (15 tools)
| Tool | Description |
|------|-------------|
| 📄 `read_pdf` | Extract text from PDF files |
| 📄 `create_pdf` | Generate PDF from text |
| 🔍 `extract_text_from_image` | OCR — Image to text |
| 📊 `read_csv` | Read and analyze CSV files |
| 📊 `read_excel` | Process Excel files |
| 📋 `read_json_file` | Read JSON files |
| 📋 `write_json_file` | Write JSON files |
| 📋 `csv_to_json` | Convert CSV to JSON |
| 📝 `markdown_to_html` | Convert Markdown to HTML |
| 📝 `html_to_markdown` | Convert HTML to Markdown |
| 🎬 `search_youtube` | Search YouTube videos |
| 🎬 `get_youtube_transcript` | Get video transcripts |
| 🎵 `play_audio` | Play audio files |
| 🖼️ `download_image` | Download images from URL |
| 📁 `read_file_content` / `write_file_content` | File I/O |

### Travel (10 tools)
| Tool | Description |
|------|-------------|
| ✈️ `search_flights` | Search flights between cities |
| 🚆 `get_pnr_status` | Indian Railways PNR status |
| 🚆 `get_train_schedule` | Train schedule lookup |
| 🚆 `get_seat_availability` | Seat availability check |
| 🚆 `get_live_train_status` | Live train tracking |
| 🗺️ `parse_location` | Geocode addresses |
| 📏 `get_distance` | Distance between locations |
| 🌤️ `get_weather` | Current weather data |
| 🌤️ `get_forecast` | Weather forecast |
| 💱 `convert_currency` | Currency conversion |

### Research (8 tools)
| Tool | Description |
|------|-------------|
| 🔍 `web_search` | Google Serper web search |
| 📚 `wikipedia_search` | Wikipedia articles |
| 📖 `define_word` | Dictionary definitions |
| 🌐 `browser_search` | Browser-based search |
| 📰 `get_news` | Latest news headlines |
| 🧮 `wolfram_alpha` | Computational answers |
| 📊 `google_trends` | Trending topics |
| 🔗 `fetch_url` | Fetch webpage content |

### Developer (7 tools)
| Tool | Description |
|------|-------------|
| 🐍 `python_repl` | Execute Python code |
| 💻 `github_get_repo_info` | GitHub repository info |
| 💻 `github_list_pull_requests` | List GitHub PRs |
| 💻 `github_create_issue` | Create GitHub issues |
| 💻 `github_list_issues` | List GitHub issues |
| 💻 `github_get_file_content` | Read files from repos |
| 💻 `github_search_repos` | Search GitHub repositories |

### Browser (7 tools — Playwright)
| Tool | Description |
|------|-------------|
| 🌐 `navigate_browser` | Navigate to URL |
| 🖱️ `click_element` | Click page elements |
| 📋 `get_elements` | Get DOM elements |
| 📄 `current_webpage` | Get current page info |
| 📝 `extract_text` | Extract page text |
| 🔗 `extract_hyperlinks` | Extract page links |
| ✏️ `fill_text` | Fill form fields |

### Communication (2 tools)
`send_email`, `read_recent_emails`

### System (4 tools)
`take_screenshot`, `send_push_notification`, `read_file_content`, `write_file_content`

---

## Architecture

### Core Components

| Component | File | Purpose |
|-----------|------|---------|
| **Config** | `core/config.py` | Centralized configuration, env variable management, startup validation |
| **Utilities** | `core/utils.py` | Logger (dual-output), Cache (TTL), RateLimiter, CircuitBreaker |
| **Models** | `core/models.py` | Pydantic input/output validation (`ChatRequest`, `HealthResponse`, `MetricsResponse`) |
| **Agent** | `core/agent.py` | Orion class — LangGraph StateGraph with worker-evaluator pattern |
| **Router** | `agents/router.py` | LLM intent classification with keyword fallback |
| **Memory** | `core/memory.py` | SQLite conversation memory, retry queue, notification manager |
| **Tools** | `tools/*.py` | 60 tools organized into 14 tool modules |
| **Integrations** | `integrations/*.py` | Telegram, Gradio, Email Bot, Scheduler |

### Key Patterns

- **Intent Routing**: LLM classifies queries into 9 categories; only category-relevant tools are bound to the worker LLM
- **Circuit Breaker**: CLOSED → OPEN → HALF_OPEN state machine wrapping all LLM calls
- **Per-User Rate Limiting**: Independent rate limit buckets (10 req/min) per user
- **Thread Isolation**: `thread_id = f"{user_id}_{channel}"` — each user × channel gets its own LangGraph thread
- **Structured Logging**: Dual-output (console + JSON) with correlation IDs traced end-to-end
- **Graceful Shutdown**: In-flight request tracking, drain timeout, clean resource cleanup

---

## Configuration

### Environment Variables
```env
# Required API Keys
GROQ_API_KEY=your_groq_api_key
GEMINI_API_KEY=your_gemini_api_key
SERPER_API_KEY=your_serper_api_key

# Email
EMAIL_ADDRESS=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_ALLOWED_USER_ID=your_user_id

# Calendar
GOOGLE_CALENDAR_CREDENTIALS=path/to/credentials.json

# Models
WORKER_MODEL=meta-llama/llama-4-scout-17b-16e-instruct
ROUTER_MODEL=llama-3.1-8b-instant

# Tuning
USER_REQUESTS_PER_MINUTE=10
LOG_LEVEL=INFO
CACHE_TTL_SECONDS=300
```

---

## Usage Examples

### Email Management
```
"Send an email to john@example.com with subject 'Hello' and body 'How are you?'"
"Show me my last 5 unread emails"
```

### Calendar
```
"Create a calendar event 'Team Meeting' tomorrow at 2 PM for 1 hour"
"Show me my calendar for the next 7 days"
```

### Task Management
```
"Create a high priority task 'Finish report' due on 2026-01-25"
"Show me all my pending tasks"
"Mark task #1 as completed"
```

### Notes
```
"Create a note titled 'Meeting Notes' with content about today's discussion"
"Find notes containing 'meeting'"
```

### Document Processing
```
"Extract text from document.pdf in the sandbox folder"
"Extract text from the image screenshot.png"
"Show me the first 10 rows of sales_data.csv"
"Convert data.csv to JSON format"
```

### Developer
```
"Show me the open pull requests for langchain-ai/langchain"
"Run this Python code: print(sum(range(100)))"
```

### QR Code
```
"Generate a QR code for https://example.com"
```

---

## Getting Started

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

2. **Configure Environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Install Tesseract OCR** (for OCR features)

4. **Run**:
   ```bash
   python main.py telegram    # Telegram bot
   python main.py gradio      # Web UI
   python main.py test        # Connection test
   python main.py info        # Show config
   ```

---

## Support

- **SETUP.md** — Installation guide
- **README.md** — Full documentation
- **ARCHITECTURE.md** — Technical deep-dive
- **orion.log** — Runtime logs
- **.env.example** — All configuration options
