# 🌟 Orion AI Personal Assistant

An advanced AI-powered personal assistant with **35+ tools** across multiple categories including email management, calendar integration, document processing, web automation, and much more!

## ✨ Features

### 🎯 Core Capabilities
- **Intelligent Task Execution**: Uses LangGraph workflow with worker-evaluator pattern
- **Memory Persistence**: Maintains conversation context across sessions
- **Error Handling**: Robust retry logic and comprehensive error reporting
- **Tool Usage Tracking**: Monitor AI's tool usage in real-time
- **Export Conversations**: Save your chat history in JSON format

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
- **Push Notifications**: Send notifications via Pushover
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
- **Push Notifications**: Pushover tokens from [Pushover.net](https://pushover.net/)

### Running Orion

```bash
python app.py
```

The Gradio interface will open automatically in your browser at `http://localhost:7860`

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
Orion-AI_Personal-Assistant/
├── app.py                  # Gradio UI application
├── orion.py               # Main Orion class with LangGraph workflow
├── tools_enhanced.py      # All 35+ tools organized by category
├── config.py              # Configuration management
├── utils.py               # Logging, caching, rate limiting
├── requirements.txt       # Python dependencies
├── .env.example          # Environment variables template
└── sandbox/              # Working directory for files
    ├── notes/            # Stored notes
    ├── tasks/            # Task storage
    ├── screenshots/      # Screenshot storage
    └── temp/             # Temporary files
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
- [ ] Slack/Discord integration
- [ ] Advanced data visualization
- [ ] Database query support
- [ ] SMS integration (Twilio)
- [ ] Advanced scheduling with cron
- [ ] Multi-language support

---

**Made with ❤️ for productivity enthusiasts**
